import json
from urllib.parse import unquote
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth.models import User
from rest_framework_simplejwt.tokens import AccessToken
from .models import Room, Message, UserProfile


class ChatConsumer(AsyncWebsocketConsumer):

    async def connect(self):
        raw_room_name = self.scope['url_route']['kwargs']['room_name']
        self.room_name = unquote(raw_room_name)  # handles spaces & special chars
        self.room_group_name = f'chat_{self.room_name}'.replace(' ', '_')

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
        if hasattr(self, 'room_group_name'):
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

            await self.broadcast_message(message, content)
            await self.notify_offline_members(content)
        elif message_type == 'broadcast_message':
            content = data.get('content', '')
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'chat_message',
                    'message': content,
                    'sender': self.user.username,
                    'timestamp': data.get('timestamp'),
                    'message_id': data.get('message_id'),
                    'attachment_url': data.get('attachment_url'),
                    'attachment_name': data.get('attachment_name'),
                    'attachment_type': data.get('attachment_type'),
                    'is_image': data.get('is_image', False),
                }
            )
            await self.notify_offline_members(
                content or data.get('attachment_name') or 'Attachment'
            )

    async def broadcast_message(self, message, content):
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'chat_message',
                'message': content,
                'sender': self.user.username,
                'timestamp': str(message.timestamp),
                'message_id': message.id,
                'attachment_url': message.attachment.url if message.attachment else None,
                'attachment_name': message.attachment.name.rsplit('/', 1)[-1] if message.attachment else None,
                'attachment_type': message.attachment.name.rsplit('.', 1)[-1].lower() if message.attachment and '.' in message.attachment.name else None,
                'is_image': (
                    message.attachment.name.rsplit('.', 1)[-1].lower() in {'jpg', 'jpeg', 'png', 'gif', 'webp', 'bmp', 'svg'}
                    if message.attachment and '.' in message.attachment.name else False
                ),
            }
        )

    async def chat_message(self, event):
        await self.send(text_data=json.dumps({
            'type': 'message',
            'message': event['message'],
            'sender': event['sender'],
            'timestamp': event['timestamp'],
            'message_id': event['message_id'],
            'attachment_url': event.get('attachment_url'),
            'attachment_name': event.get('attachment_name'),
            'attachment_type': event.get('attachment_type'),
            'is_image': event.get('is_image', False),
        }))

    async def user_status(self, event):
        await self.send(text_data=json.dumps({
            'type': 'status',
            'user': event['user'],
            'status': event['status']
        }))

    async def notify_offline_members(self, content):
        try:
            from chat.tasks import send_message_notification
            members = await self.get_room_members()
            for member in members:
                if member.id != self.user.id:
                    send_message_notification(
                        self.user.username,
                        self.room_name,
                        content,
                        member.id
                    )
        except Exception:
            pass

    @database_sync_to_async
    def get_user_from_token(self):
        try:
            query_string = self.scope.get('query_string', b'').decode()
            params = dict(
                p.split('=') for p in query_string.split('&') if '=' in p
            )
            token_key = params.get('token')
            if not token_key:
                return None
            access_token = AccessToken(token_key)
            return User.objects.get(id=access_token['user_id'])
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

    @database_sync_to_async
    def get_room_members(self):
        room = Room.objects.get(name=self.room_name)
        return list(room.members.all())
