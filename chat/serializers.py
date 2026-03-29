from rest_framework import serializers
from django.contrib.auth.models import User
from .models import Room, Message, UserProfile, JoinRequest, DirectMessage


class UserSerializer(serializers.ModelSerializer):
    is_online = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ('id', 'username', 'email', 'is_online')

    def get_is_online(self, obj):
        try:
            return obj.profile.is_online
        except UserProfile.DoesNotExist:
            return False


class MessageSerializer(serializers.ModelSerializer):
    sender = UserSerializer(read_only=True)

    class Meta:
        model = Message
        fields = ('id', 'room', 'sender', 'content', 'timestamp', 'is_read')
        read_only_fields = ('sender', 'timestamp')


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
        last = obj.messages.last()
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


class DirectMessageSerializer(serializers.ModelSerializer):
    sender = UserSerializer(read_only=True)
    receiver = UserSerializer(read_only=True)

    class Meta:
        model = DirectMessage
        fields = ('id', 'sender', 'receiver', 'content', 'timestamp', 'is_read')