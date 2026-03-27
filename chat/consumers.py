import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth.models import User
from rest_framework_simplejwt.tokens import AccessToken
from .models import Room, Message, UserProfile


class ChatConsumer(AsyncWebsocketConsumer):

    async def connect(self):
        self.room_name = self.scope['url_route']['kwargs']['room_name']
        self.room_group_name = f'chat_{self.room_name}'

        # Get user from JWT token in URL
        self.user = await self.get_user_from_token()

        if self.user is None:
            await self.close()
            return

        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        await self.set_user_online(True)
        await self.accept()

        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'user_status',
                'user': self.user.username,
                'status': 'online'
            }
        )

    async def disconnect(self, close_code):
        if hasattr(self, 'user') and self.user:
            await self.set_user_online(False)
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'user_status',
                    'user': self.user.username,
                    'status': 'offline'
                }
            )
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    async def receive(self, text_data):
        data = json.loads(text_data)
        message_type = data.get('type', 'message')

        if message_type == 'message':
            content = data.get('content', '')
            message = await self.save_message(content)
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

    async def chat_message(self, event):
        await self.send(text_data=json.dumps({
            'type': 'message',
            'message': event['message'],
            'sender': event['sender'],
            'timestamp': event['timestamp'],
            'message_id': event['message_id']
        }))

    async def user_status(self, event):
        await self.send(text_data=json.dumps({
            'type': 'status',
            'user': event['user'],
            'status': event['status']
        }))

    @database_sync_to_async
    def get_user_from_token(self):
        try:
            query_string = self.scope.get('query_string', b'').decode()
            params = dict(p.split('=') for p in query_string.split('&') if '=' in p)
            token_key = params.get('token')
            if not token_key:
                return None
            access_token = AccessToken(token_key)
            user = User.objects.get(id=access_token['user_id'])
            return user
        except Exception:
            return None

    @database_sync_to_async
    def save_message(self, content):
        room = Room.objects.get(name=self.room_name)
        return Message.objects.create(
            room=room,
            sender=self.user,
            content=content
        )

    @database_sync_to_async
    def set_user_online(self, status):
        profile, _ = UserProfile.objects.get_or_create(user=self.user)
        profile.is_online = status
        profile.save()