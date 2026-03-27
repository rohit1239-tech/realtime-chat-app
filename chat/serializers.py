from rest_framework import serializers
from django.contrib.auth.models import User
from .models import Room, Message, UserProfile


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

    class Meta:
        model = Room
        fields = (
            'id', 'name', 'room_type', 'members',
            'created_by', 'last_message', 'member_count', 'created_at'
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