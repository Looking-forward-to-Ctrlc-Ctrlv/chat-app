import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth.models import User
from django.utils import timezone
from chats.models import ChatModel, UserProfileModel, ChatNotification, ChatFile
from django.db import transaction


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