import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth.models import User
from .models import Room, Message, UserProfile


class ChatConsumer(AsyncWebsocketConsumer):

    async def connect(self):
        self.room_name = self.scope['url_route']['kwargs']['room_name']
        self.room_group_name = f'chat_{self.room_name}'
        self.user = self.scope['user']

        # Reject anonymous users
        if not self.user.is_authenticated:
            await self.close()
            return

        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

        # Mark user as online
        await self.set_user_online(True)

        # Accept the WebSocket connection
        await self.accept()

        # Notify others that user joined
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'user_status',
                'user': self.user.username,
                'status': 'online'
            }
        )

        async def disconnect(self, close_code):
            # Mark user as offline
            await self.set_user_online(False)

            # Notify others that user left
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'user_status',
                    'user': self.user.username,
                    'status': 'offline'
                }
            )

            # Leave room group
            await self.channel_layer.group_discard(
                self.room_group_name,
                self.channel_name
            )

        async def receive(self, text_data):
            data = json.loads(text_data)
            message_type = data.get('type', 'message')

            if message_type == 'message':
                content = data.get('content', '')

                # Save message to database
                message = await self.save_message(content)

                # Broadcast message to room group
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        'type': 'chat_message',
                        'message': content,
                        'sender': self.user.username,
                        'timestamp': str(message.timestamp),
                        'message_id': message.id
                    }
                )

        # Handler — receives broadcast and sends to WebSocket
        async def chat_message(self, event):
            await self.send(text_data=json.dumps({
                'type': 'message',
                'message': event['message'],
                'sender': event['sender'],
                'timestamp': event['timestamp'],
                'message_id': event['message_id']
            }))

        # Handler — online/offline status broadcast
        async def user_status(self, event):
            await self.send(text_data=json.dumps({
                'type': 'status',
                'user': event['user'],
                'status': event['status']
            }))

    # ---- Database helpers ----

    @database_sync_to_async
    def save_message(self, content):
        room = Room.objects.get(name=self.room_name)
        message = Message.objects.create(
            room=room,
            sender=self.user,
            content=content
        )
        return message

    @database_sync_to_async
    def set_user_online(self, status):
        profile, _ = UserProfile.objects.get_or_create(user=self.user)
        profile.is_online = status
        profile.save()