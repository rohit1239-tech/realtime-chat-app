from rest_framework import serializers
from django.contrib.auth.models import User
from django.db.models import Q
from pathlib import Path
from .models import (
    Room, Message, UserProfile, JoinRequest, FriendRequest, DirectMessage
)


class UserSerializer(serializers.ModelSerializer):
    is_online = serializers.SerializerMethodField()
    profile_picture_url = serializers.SerializerMethodField()
    friendship_status = serializers.SerializerMethodField()
    incoming_friend_request_id = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            'id', 'username', 'email', 'is_online', 'profile_picture_url',
            'friendship_status', 'incoming_friend_request_id'
        )

    def get_is_online(self, obj):
        try:
            return obj.profile.is_online
        except UserProfile.DoesNotExist:
            return False

    def get_profile_picture_url(self, obj):
        try:
            request = self.context.get('request')
            profile_picture = obj.profile.profile_picture
            if not profile_picture:
                return None
            if request:
                return request.build_absolute_uri(profile_picture.url)
            return profile_picture.url
        except UserProfile.DoesNotExist:
            return None

    def _get_relation(self, obj):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return None
        return FriendRequest.objects.filter(
            Q(sender=request.user, receiver=obj) |
            Q(sender=obj, receiver=request.user)
        ).order_by('-created_at').first()

    def get_friendship_status(self, obj):
        relation = self._get_relation(obj)
        request = self.context.get('request')
        if not relation or not request or not request.user.is_authenticated:
            return 'none'
        if relation.status == 'accepted':
            return 'friends'
        if relation.status == 'pending':
            if relation.sender_id == request.user.id:
                return 'outgoing_request'
            return 'incoming_request'
        return 'none'

    def get_incoming_friend_request_id(self, obj):
        relation = self._get_relation(obj)
        request = self.context.get('request')
        if (
            relation and request and request.user.is_authenticated and
            relation.status == 'pending' and relation.receiver_id == request.user.id
        ):
            return relation.id
        return None


class MessageSerializer(serializers.ModelSerializer):
    sender = UserSerializer(read_only=True)
    attachment_url = serializers.SerializerMethodField()
    attachment_name = serializers.SerializerMethodField()
    attachment_type = serializers.SerializerMethodField()
    is_image = serializers.SerializerMethodField()

    class Meta:
        model = Message
        fields = (
            'id', 'room', 'sender', 'content', 'attachment',
            'attachment_url', 'attachment_name', 'attachment_type',
            'is_image', 'timestamp', 'is_read'
        )
        read_only_fields = ('room', 'sender', 'timestamp')

    def validate(self, attrs):
        content = (attrs.get('content') or '').strip()
        attachment = attrs.get('attachment')
        if not content and not attachment:
            raise serializers.ValidationError(
                {'content': 'Message or attachment is required.'}
            )
        attrs['content'] = content
        return attrs

    def get_attachment_url(self, obj):
        if not obj.attachment:
            return None
        request = self.context.get('request')
        if request:
            return request.build_absolute_uri(obj.attachment.url)
        return obj.attachment.url

    def get_attachment_name(self, obj):
        if not obj.attachment:
            return None
        return Path(obj.attachment.name).name

    def get_attachment_type(self, obj):
        if not obj.attachment:
            return None
        return Path(obj.attachment.name).suffix.lstrip('.').lower() or 'file'

    def get_is_image(self, obj):
        if not obj.attachment:
            return False
        return self.get_attachment_type(obj) in {
            'jpg', 'jpeg', 'png', 'gif', 'webp', 'bmp', 'svg'
        }


class RoomSerializer(serializers.ModelSerializer):
    members = UserSerializer(many=True, read_only=True)
    created_by = UserSerializer(read_only=True)
    last_message = serializers.SerializerMethodField()
    member_count = serializers.SerializerMethodField()
    pending_requests = serializers.SerializerMethodField()

    class Meta:
        model = Room
        fields = (
            'id', 'name', 'room_type', 'members', 'created_by',
            'last_message', 'member_count', 'requires_approval',
            'pending_requests', 'created_at'
        )

    def get_last_message(self, obj):
        messages = list(obj.messages.all())
        last = messages[-1] if messages else None
        if last:
            return {
                'content': last.content,
                'sender': last.sender.username,
                'timestamp': last.timestamp
            }
        return None

    def get_member_count(self, obj):
        return obj.members.count()

    def get_pending_requests(self, obj):
        request = self.context.get('request')
        if request and obj.created_by == request.user:
            return obj.join_requests.filter(status='pending').count()
        return 0


class RoomListSerializer(serializers.ModelSerializer):
    created_by = UserSerializer(read_only=True)
    last_message = serializers.SerializerMethodField()
    member_count = serializers.SerializerMethodField()
    pending_requests = serializers.SerializerMethodField()

    class Meta:
        model = Room
        fields = (
            'id', 'name', 'room_type', 'created_by',
            'last_message', 'member_count', 'requires_approval',
            'pending_requests', 'created_at'
        )

    def get_last_message(self, obj):
        last = obj.messages.select_related('sender').order_by('-timestamp').first()
        if last:
            return {
                'content': last.content,
                'sender': last.sender.username,
                'timestamp': last.timestamp
            }
        return None

    def get_member_count(self, obj):
        return obj.members.count()

    def get_pending_requests(self, obj):
        request = self.context.get('request')
        if request and obj.created_by == request.user:
            return obj.join_requests.filter(status='pending').count()
        return 0



class JoinRequestSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    room = RoomSerializer(read_only=True)

    class Meta:
        model = JoinRequest
        fields = ('id', 'room', 'user', 'status', 'created_at')


class FriendRequestSerializer(serializers.ModelSerializer):
    sender = UserSerializer(read_only=True)
    receiver = UserSerializer(read_only=True)

    class Meta:
        model = FriendRequest
        fields = ('id', 'sender', 'receiver', 'status', 'created_at')


class DirectMessageSerializer(serializers.ModelSerializer):
    sender = UserSerializer(read_only=True)
    receiver = UserSerializer(read_only=True)
    attachment_url = serializers.SerializerMethodField()
    attachment_name = serializers.SerializerMethodField()
    attachment_type = serializers.SerializerMethodField()
    is_image = serializers.SerializerMethodField()

    class Meta:
        model = DirectMessage
        fields = (
            'id', 'sender', 'receiver', 'content', 'attachment',
            'attachment_url', 'attachment_name', 'attachment_type',
            'is_image', 'timestamp', 'is_read'
        )

    def validate(self, attrs):
        content = (attrs.get('content') or '').strip()
        attachment = attrs.get('attachment')
        if not content and not attachment:
            raise serializers.ValidationError(
                {'content': 'Message or attachment is required.'}
            )
        attrs['content'] = content
        return attrs

    def get_attachment_url(self, obj):
        if not obj.attachment:
            return None
        request = self.context.get('request')
        if request:
            return request.build_absolute_uri(obj.attachment.url)
        return obj.attachment.url

    def get_attachment_name(self, obj):
        if not obj.attachment:
            return None
        return Path(obj.attachment.name).name

    def get_attachment_type(self, obj):
        if not obj.attachment:
            return None
        return Path(obj.attachment.name).suffix.lstrip('.').lower() or 'file'

    def get_is_image(self, obj):
        if not obj.attachment:
            return False
        return self.get_attachment_type(obj) in {
            'jpg', 'jpeg', 'png', 'gif', 'webp', 'bmp', 'svg'
        }
