import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth.models import User
from django.utils import timezone
from chats.models import ChatModel, UserProfileModel, ChatNotification, ChatFile
from django.db import transaction
from groups.models import Group,GroupNotification,GroupMessage


class PersonalChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        my_id = self.scope['user'].id
        other_user_id = self.scope['url_route']['kwargs']['id']

        # Create room name based on user IDs
        if int(my_id) > int(other_user_id):
            self.room_name = f'{my_id}-{other_user_id}'
        else:
            self.room_name = f'{other_user_id}-{my_id}'

        self.room_group_name = f'chat_{self.room_name}'

        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

        # Set user as online
        await self.set_online_status(self.scope['user'].username, True)

        await self.accept()

    async def disconnect(self, close_code):
        # Leave room group
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

        # Set user as offline
        await self.set_online_status(self.scope['user'].username, False)

    # Receive message from WebSocket
    async def receive(self, text_data=None, bytes_data=None):
        data = json.loads(text_data)
        message = data.get('message', '')
        username = data.get('username', '')
        receiver = data.get('receiver', '')

        # Check for message type and file data
        message_type = data.get('type', 'text')  # Default is text
        file_data = data.get('file_data', None)  # For file uploads

        # Variables to store chat object and modified message
        chat_obj = None
        file_id = None

        # Save message to database and create notification
        if message_type == 'text':
            # For regular text messages
            chat_obj = await self.save_message(username, self.room_group_name, message, receiver)
        elif message_type == 'file' and file_data:
            # For file messages - save file info to ChatFile model and reference in message
            file_id = await self.save_file(username, self.room_group_name, file_data)

            # Include file_id in the message for later retrieval
            file_message = f"Sent a file: {file_data.get('filename', 'unknown')} [file_id:{file_id}]"
            chat_obj = await self.save_message(username, self.room_group_name, file_message, receiver, file_id)

        # Send message to room group
        message_data = {
            'type': 'chat_message',
            'message': message if message_type == 'text' else chat_obj.message if chat_obj else "File message",
            'username': username,
            'message_type': message_type,
            'file_data': file_data,
            'message_id': chat_obj.id if chat_obj else None,
            'timestamp': timezone.now().isoformat()
        }

        await self.channel_layer.group_send(
            self.room_group_name,
            message_data
        )
        other_user_id = self.scope['url_route']['kwargs']['id']
        user = await self.get_user(other_user_id)
        if user and user.username == receiver:
            other_user = await self.get_user(other_user_id)
        if other_user and other_user.username == receiver:
            unseen_notifications = await self.get_unseen_notifications(other_user_id)
            await self.channel_layer.group_send(
                f'{other_user_id}',
                {
                    'type': 'send_notification',
                    'value': json.dumps({
                        'unseen_notifications': unseen_notifications,
                        'unseen_count': len(unseen_notifications)
                    })
                }
            )
            await self.channel_layer.group_send(
                f'{other_user_id}',
                {
                    'type': 'send_single_notification',
                    'notification': {
                        'sender_username': username,
                        'message_preview': message[:50] + '...' if len(message) > 50 else message
                    }
                }
            )
    # Receive message from room group
    async def chat_message(self, event):
        # Send message to WebSocket
        await self.send(text_data=json.dumps({
            'message': event.get('message', ''),
            'username': event.get('username', ''),
            'message_type': event.get('message_type', 'text'),
            'file_data': event.get('file_data', None),
            'timestamp': event.get('timestamp', timezone.now().isoformat())
        }))

    async def typing_status(self, event):
        """
        Send typing status to WebSocket
        """
        await self.send(text_data=json.dumps({
            'type': 'typing',
            'username': event['username'],
            'is_typing': event['is_typing']
        }))

    async def mark_read(self, event):
        """
        Mark messages as read
        """
        thread_name = event.get('thread_name', self.room_group_name)
        username = event['username']

        # Update database
        await self.mark_messages_read(thread_name, username)

        # Send read status to both users
        await self.send(text_data=json.dumps({
            'type': 'read_status',
            'thread_name': thread_name,
            'read_by': username
        }))

    @database_sync_to_async
    def save_message(self, username, thread_name, message, receiver, file_id=None):
        """
        Save message to database and create notification
        """
        # Create chat message
        chat_obj = ChatModel.objects.create(
            sender=username,
            message=message,
            thread_name=thread_name
        )

        # Create notification if the receiver exists
        other_user_id = self.scope['url_route']['kwargs']['id']
        try:
            user = User.objects.get(id=other_user_id)
            if receiver == user.username:
                ChatNotification.objects.create(chat=chat_obj, user=user)
        except User.DoesNotExist:
            pass

        return chat_obj

    @database_sync_to_async
    def save_file(self, username, thread_name, file_data):
        """
        Save file information to ChatFile model
        """
        user = self.scope['user']

        # Create a new file entry
        chat_file = ChatFile.objects.create(
            file=file_data.get('file_url', ''),  # URL to the uploaded file
            filename=file_data.get('filename', 'unknown'),
            file_type=file_data.get('file_type', 'application/octet-stream'),
            uploader=user,
            thread_name=thread_name
        )

        return chat_file.id

    @database_sync_to_async
    def get_user(self, user_id):
        """
        Get user by ID
        """
        try:
            return User.objects.get(id=user_id)
        except User.DoesNotExist:
            return None

    @database_sync_to_async
    def get_unseen_notifications(self, user_id):
        """
        Get unseen notifications for a user
        """
        notifications = ChatNotification.objects.filter(
            user_id=user_id, is_seen=False
        ).select_related('chat')

        unseen_list = []
        for notification in notifications:
            # Extract sender username
            sender = notification.chat.sender
            if isinstance(sender, str):
                # If it's already a string, use it directly
                sender_username = sender
            else:
                # If it's a User object, get the username
                sender_username = sender.username if hasattr(sender, 'username') else str(sender)

            timestamp = notification.chat.timestamp.isoformat() if hasattr(notification.chat, 'timestamp') else ''

            unseen_list.append({
                'sender_username': sender_username,
                'timestamp': timestamp,
                'message_preview': notification.chat.message[:50] + '...' if len(
                    notification.chat.message) > 50 else notification.chat.message
            })

        return unseen_list

    @database_sync_to_async
    def set_online_status(self, username, is_online):
        """
        Set user's online status
        """
        try:
            with transaction.atomic():
                user = User.objects.select_for_update().get(username=username)
                userprofile, created = UserProfileModel.objects.select_for_update().get_or_create(
                    user=user,
                    defaults={'online_status': is_online}
                )
                userprofile.online_status = is_online
                userprofile.save(update_fields=['online_status'])

                # Broadcast online status change to all users
                # This will be handled by the channel layer in the actual implementation
        except Exception as e:
            print(f"Error updating online status: {str(e)}")

    @database_sync_to_async
    def mark_messages_read(self, thread_name, reader_username):
        """
        Mark all messages in a thread as read by a specific user
        """
        try:
            user = User.objects.get(username=reader_username)

            # Find all notifications for this user in this thread and mark them as seen
            notifications = ChatNotification.objects.filter(
                user=user,
                is_seen=False,
                chat__thread_name=thread_name
            )

            for notification in notifications:
                notification.is_seen = True
                notification.save(update_fields=['is_seen'])

            return True
        except User.DoesNotExist:
            return False


class NotificationConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        # Get user ID from WebSocket scope
        my_id = self.scope['user'].id
        self.room_group_name = f'{my_id}'

        # Add the user to the group based on their ID
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

        # Accept the WebSocket connection
        await self.accept()

        # Send initial notifications upon connection
        unseen_notifications = await self.get_unseen_notifications(my_id)
        await self.send(text_data=json.dumps({
            'unseen_notifications': unseen_notifications,
            'unseen_count': len(unseen_notifications)
        }))

    async def disconnect(self, code):
        # Remove the user from the group when disconnecting
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    async def send_notification(self, event):
        # Get unseen notifications data from the event
        data = json.loads(event.get('value'))
        unseen_notifications = data.get('unseen_notifications', [])
        unseen_count = len(unseen_notifications)  # Count of unseen notifications

        # Send both the unseen notifications and the count to the user
        await self.send(text_data=json.dumps({
            'unseen_notifications': unseen_notifications,
            'unseen_count': unseen_count  # Include the count of unseen messages
        }))

    async def send_single_notification(self, event):
        await self.send(text_data=json.dumps({
            'notification': event['notification']
        }))

    # Function to fetch unseen notifications
    @database_sync_to_async
    def get_unseen_notifications(self, user_id):
        notifications = ChatNotification.objects.filter(
            user_id=user_id, is_seen=False
        ).select_related('chat')

        unseen_list = []
        for notification in notifications:
            # Extract sender username
            sender_username = notification.chat.sender
            if isinstance(sender_username, str):
                # If it's already a string, use it directly
                sender = sender_username
            else:
                # If it's a User object, get the username
                sender = sender_username.username if hasattr(sender_username, 'username') else str(sender_username)

            timestamp = notification.chat.timestamp.isoformat() if hasattr(notification.chat, 'timestamp') else ''

            unseen_list.append({
                'sender_username': sender,
                'timestamp': timestamp,
                'message_preview': notification.chat.message[:50] + '...' if len(
                    notification.chat.message) > 50 else notification.chat.message
            })

        return unseen_list


class OnlineStatusConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.room_group_name = 'user'
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

        await self.accept()

    async def receive(self, text_data=None, bytes_data=None):
        data = json.loads(text_data)
        username = data['username']
        connection_type = data['type']
        await self.change_online_status(username, connection_type)

    async def send_onlineStatus(self, event):
        data = json.loads(event.get('value'))
        username = data['username']
        online_status = data['status']
        await self.send(text_data=json.dumps({
            'username': username,
            'online_status': online_status
        }))

    async def disconnect(self, message):
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    @database_sync_to_async
    def change_online_status(self, username, c_type):
        try:
            with transaction.atomic():
                user = User.objects.select_for_update().get(username=username)
                userprofile, created = UserProfileModel.objects.select_for_update().get_or_create(
                    user=user,
                    defaults={'online_status': False}  # Set default if creating new
                )
                userprofile.online_status = (c_type == 'open')
                userprofile.save(update_fields=['online_status'])
        except Exception as e:
            print(f"Error updating online status: {str(e)}")


class GroupChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.group_id = self.scope['url_route']['kwargs']['group_id']
        self.user = self.scope['user']
        self.room_group_name = f'group_{self.group_id}'

        # Verify user is member of the group
        if not await self.is_group_member():
            await self.close()
            return

        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

        await self.accept()

    async def disconnect(self, close_code):
        # Leave room group
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
            message = data.get('message', '').strip()
            sender_id = data.get('sender')
            message_type = data.get('type', 'text')  # Default is text
            file_data = data.get('file_data', None)  # For file uploads

            if not message and message_type == 'text':
                return

            # Variables to store message object and file id
            message_obj = None
            file_id = None

            # Handle different message types
            if message_type == 'text':
                # Save regular text message
                message_obj = await self.save_group_message(message, sender_id)
            elif message_type == 'file' and file_data:
                # Save file info and create a message about it
                file_id = await self.save_group_file(file_data, sender_id)
                file_message = f"Sent a file: {file_data.get('filename', 'unknown')} [file_id:{file_id}]"
                message_obj = await self.save_group_message(file_message, sender_id, file_id)

            if not message_obj:
                return

            # Create notifications for all group members except sender
            await self.create_notifications(message_obj)

            # Send notifications to all group members who are online
            await self.send_notifications_to_members(message_obj)

            # Broadcast message to all group members in the room
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'chat_message',
                    'message': message_obj.content,
                    'sender': {
                        'id': self.user.id,
                        'username': self.user.username
                    },
                    'message_type': message_type,
                    'file_data': file_data,
                    'message_id': message_obj.id,
                    'timestamp': message_obj.timestamp.isoformat()
                }
            )

        except Exception as e:
            print(f"Error processing message: {str(e)}")

    async def chat_message(self, event):
        # Send message to WebSocket
        await self.send(text_data=json.dumps({
            'message': event['message'],
            'sender': event['sender'],
            'message_type': event.get('message_type', 'text'),
            'file_data': event.get('file_data', None),
            'message_id': event.get('message_id'),
            'timestamp': event['timestamp']
        }))

    async def typing_status(self, event):
        """
        Send typing status to WebSocket
        """
        await self.send(text_data=json.dumps({
            'type': 'typing',
            'username': event['username'],
            'is_typing': event['is_typing']
        }))

    async def mark_read(self, event):
        """
        Mark messages as read
        """
        group_id = event.get('group_id', self.group_id)
        username = event['username']

        # Update database
        await self.mark_messages_read(group_id, username)

        # Send read status to all group members
        await self.send(text_data=json.dumps({
            'type': 'read_status',
            'group_id': group_id,
            'read_by': username
        }))

    @database_sync_to_async
    def is_group_member(self):
        """Check if user is a member of the group"""
        return Group.objects.filter(
            id=self.group_id,
            members=self.user
        ).exists()

    @database_sync_to_async
    def save_group_message(self, message, sender_id, file_id=None):
        """Save message to database"""
        return GroupMessage.objects.create(
            group_id=self.group_id,
            sender_id=sender_id,
            content=message,
            file_id=file_id
        )

    @database_sync_to_async
    def save_group_file(self, file_data, sender_id):
        """
        Save file information to a model (assuming there's a GroupFile model)
        """
        # Assuming we have a GroupFile model similar to ChatFile
        group_file = GroupFile.objects.create(
            file=file_data.get('file_url', ''),
            filename=file_data.get('filename', 'unknown'),
            file_type=file_data.get('file_type', 'application/octet-stream'),
            uploader_id=sender_id,
            group_id=self.group_id
        )
        return group_file.id

    @database_sync_to_async
    def create_notifications(self, message_obj):
        """Create notifications for all group members except sender"""
        group = Group.objects.get(id=self.group_id)
        members = group.members.exclude(id=self.user.id)

        notifications = []
        for member in members:
            notifications.append(
                GroupNotification(
                    group=group,
                    user=member,
                    message=message_obj,
                    is_seen=False
                )
            )

        if notifications:
            GroupNotification.objects.bulk_create(notifications)

        return members.values_list('id', flat=True)

    @database_sync_to_async
    def mark_messages_read(self, group_id, username):
        """
        Mark all notifications in a group as read by a specific user
        """
        try:
            user = User.objects.get(username=username)

            # Find all notifications for this user in this group and mark them as seen
            notifications = GroupNotification.objects.filter(
                user=user,
                group_id=group_id,
                is_seen=False
            )

            for notification in notifications:
                notification.is_seen = True
                notification.save(update_fields=['is_seen'])

            return True
        except User.DoesNotExist:
            return False

    @database_sync_to_async
    def get_unseen_group_notifications(self, user_id):
        """
        Get unseen group notifications for a user
        """
        notifications = GroupNotification.objects.filter(
            user_id=user_id, is_seen=False
        ).select_related('message')

        unseen_list = []
        for notification in notifications:
            # Get sender information
            sender = notification.message.sender
            sender_username = sender.username if hasattr(sender, 'username') else str(sender)

            group_name = notification.group.name if hasattr(notification.group,
                                                            'name') else f"Group {notification.group.id}"

            timestamp = notification.message.timestamp.isoformat() if hasattr(notification.message, 'timestamp') else ''

            unseen_list.append({
                'sender_username': sender_username,
                'group_id': notification.group.id,
                'group_name': group_name,
                'timestamp': timestamp,
                'message_preview': notification.message.content[:50] + '...' if len(
                    notification.message.content) > 50 else notification.message.content
            })

        return unseen_list

    async def send_notifications_to_members(self, message_obj):
        """
        Send notifications to all group members who are online
        """
        # Get the group and members (excluding sender)
        group = await self.get_group()
        members = await self.get_group_members_except_sender()

        # Create a message preview for notification
        message_preview = message_obj.content[:50] + '...' if len(message_obj.content) > 50 else message_obj.content

        # Send notification to each member's personal notification channel
        for member in members:
            # Send to member's notification channel
            await self.channel_layer.group_send(
                f'{member.id}',  # Member's notification channel
                {
                    'type': 'send_notification',
                    'value': json.dumps({
                        'unseen_notifications': await self.get_unseen_group_notifications(member.id),
                        'unseen_count': await self.get_unseen_notification_count(member.id)
                    })
                }
            )

            # Also send single notification for real-time popup
            await self.channel_layer.group_send(
                f'{member.id}',
                {
                    'type': 'send_single_notification',
                    'notification': {
                        'sender_username': self.user.username,
                        'group_id': group.id,
                        'group_name': group.name,
                        'message_preview': message_preview
                    }
                }
            )

    @database_sync_to_async
    def get_group(self):
        """Get group object"""
        return Group.objects.get(id=self.group_id)

    @database_sync_to_async
    def get_group_members_except_sender(self):
        """Get all group members except the message sender"""
        group = Group.objects.get(id=self.group_id)
        return list(group.members.exclude(id=self.user.id))

    @database_sync_to_async
    def get_unseen_notification_count(self, user_id):
        """Get count of unseen notifications for a user"""
        return GroupNotification.objects.filter(
            user_id=user_id, is_seen=False
        ).count()