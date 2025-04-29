import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from chats.models import ChatModel, UserProfileModel, ChatNotification
from django.contrib.auth.models import User
from django.db import transaction


# class PersonalChatConsumer(AsyncWebsocketConsumer):
#     async def connect(self):
#         my_id = self.scope['user'].id
#         other_user_id = self.scope['url_route']['kwargs']['id']
#         if int(my_id) > int(other_user_id):
#             self.room_name = f'{my_id}-{other_user_id}'
#         else:
#             self.room_name = f'{other_user_id}-{my_id}'
#
#         self.room_group_name = 'chat_%s' % self.room_name

#         await self.channel_layer.group_add(
#             self.room_group_name,
#             self.channel_name
#         )
#
#         await self.accept()
#
#     async def receive(self, text_data=None, bytes_data=None):
#         data = json.loads(text_data)
#         print(data)
#         message = data['message']
#         username = data['username']
#         receiver = data['receiver']
#
#         # Save the message and create notification
#         chat_obj = await self.save_message(username, self.room_group_name, message, receiver)
#
#         # Send message to room group
#         await self.channel_layer.group_send(
#             self.room_group_name,
#             {
#                 'type': 'chat_message',
#                 'message': message,
#                 'username': username,
#             }
#         )
#
#         # Also send notification to the receiver's notification group
#         other_user_id = self.scope['url_route']['kwargs']['id']
#         user = await self.get_user(other_user_id)
#         if user and user.username == receiver:
#             # Get updated unseen notifications for the receiver
#             unseen_notifications = await self.get_unseen_notifications(other_user_id)
#
#             # Send to the receiver's notification group
#             await self.channel_layer.group_send(
#                 f'{other_user_id}',
#                 {
#                     'type': 'send_notification',
#                     'value': json.dumps({
#                         'unseen_notifications': unseen_notifications,
#                         'unseen_count': len(unseen_notifications)
#                     })
#                 }
#             )
#
#     async def chat_message(self, event):
#         message = event['message']
#         username = event['username']
#
#         await self.send(text_data=json.dumps({
#             'message': message,
#             'username': username
#         }))
#
#     async def disconnect(self, code):
#         await self.channel_layer.group_discard(
#             self.room_group_name,
#             self.channel_name
#         )
#
#     @database_sync_to_async
#     def save_message(self, username, thread_name, message, receiver):
#         chat_obj = ChatModel.objects.create(
#             sender=username, message=message, thread_name=thread_name)
#         other_user_id = self.scope['url_route']['kwargs']['id']
#         get_user = User.objects.get(id=other_user_id)
#         if receiver == get_user.username:
#             ChatNotification.objects.create(chat=chat_obj, user=get_user)
#         return chat_obj
#
#     @database_sync_to_async
#     def get_user(self, user_id):
#         try:
#             return User.objects.get(id=user_id)
#         except User.DoesNotExist:
#             return None
#
#     @database_sync_to_async
#     def get_unseen_notifications(self, user_id):
#         notifications = ChatNotification.objects.filter(user_id=user_id, is_seen=False).select_related('chat')
#
#         unseen_list = []
#         for notification in notifications:
#             # Extract sender username
#             sender_username = notification.chat.sender
#             if isinstance(sender_username, str):
#                 sender = sender_username
#             else:
#                 sender = sender_username.username if hasattr(sender_username, 'username') else str(sender_username)
#
#             timestamp = notification.chat.created_at.isoformat() if hasattr(notification.chat, 'created_at') else ''
#
#             unseen_list.append({
#                 'sender_username': sender,
#                 'timestamp': timestamp,
#                 'message_preview': notification.chat.message[:50] + '...' if len(
#                     notification.chat.message) > 50 else notification.chat.message
#             })
#
#         return unseen_list



class PersonalChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        my_id = self.scope['user'].id
        other_user_id = self.scope['url_route']['kwargs']['id']
        if int(my_id) > int(other_user_id):
            self.room_name = f'{my_id}-{other_user_id}'
        else:
            self.room_name = f'{other_user_id}-{my_id}'

        self.room_group_name = f'chat_{self.room_name}'

        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

        await self.accept()

    async def receive(self, text_data=None, bytes_data=None):
        data = json.loads(text_data)
        message = data['message']
        username = data['username']
        receiver = data['receiver']

        # Save message and create notification
        chat_obj = await self.save_message(username, self.room_group_name, message, receiver)

        # Send message to chat group
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'chat_message',
                'message': message,
                'username': username,
            }
        )

        # Notify the receiver (if online)
        other_user_id = self.scope['url_route']['kwargs']['id']
        user = await self.get_user(other_user_id)
        if user and user.username == receiver:
            unseen_notifications = await self.get_unseen_notifications(other_user_id)

            # Send full unseen list
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

            # Send single real-time notification
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

    async def chat_message(self, event):
        message = event['message']
        username = event['username']

        await self.send(text_data=json.dumps({
            'message': message,
            'username': username
        }))

    async def disconnect(self, code):
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    @database_sync_to_async
    def save_message(self, username, thread_name, message, receiver):
        chat_obj = ChatModel.objects.create(
            sender=username,
            message=message,
            thread_name=thread_name
        )
        other_user_id = self.scope['url_route']['kwargs']['id']
        get_user = User.objects.get(id=other_user_id)
        if receiver == get_user.username:
            ChatNotification.objects.create(chat=chat_obj, user=get_user)
        return chat_obj

    @database_sync_to_async
    def get_user(self, user_id):
        try:
            return User.objects.get(id=user_id)
        except User.DoesNotExist:
            return None

    @database_sync_to_async
    def get_unseen_notifications(self, user_id):
        notifications = ChatNotification.objects.filter(
            user_id=user_id, is_seen=False
        ).select_related('chat')

        unseen_list = []
        for notification in notifications:
            sender = notification.chat.sender
            if not isinstance(sender, str):
                sender = sender.username if hasattr(sender, 'username') else str(sender)

            timestamp = notification.chat.created_at.isoformat() if hasattr(notification.chat, 'created_at') else ''

            unseen_list.append({
                'sender_username': sender,
                'timestamp': timestamp,
                'message_preview': notification.chat.message[:50] + '...' if len(
                    notification.chat.message) > 50 else notification.chat.message
            })

        return unseen_list



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
        notifications = ChatNotification.objects.filter(user_id=user_id, is_seen=False).select_related('chat')

        unseen_list = []
        for notification in notifications:
            # Extract sender username - the original code has a potential issue here
            sender_username = notification.chat.sender
            if isinstance(sender_username, str):
                # If it's already a string, use it directly
                sender = sender_username
            else:
                # If it's a User object, get the username
                sender = sender_username.username if hasattr(sender_username, 'username') else str(sender_username)

            timestamp = notification.chat.created_at.isoformat() if hasattr(notification.chat, 'created_at') else ''

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
        print(connection_type)
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
        self.channel_layer.group_discard(
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