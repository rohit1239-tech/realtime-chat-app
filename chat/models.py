from django.db import models
from django.contrib.auth.models import User


class Room(models.Model):
    ROOM_TYPES = (
        ('group', 'Group'),
        ('private', 'Private'),
    )
    name = models.CharField(max_length=100, unique=True)
    room_type = models.CharField(max_length=10, choices=ROOM_TYPES, default='group')
    members = models.ManyToManyField(User, related_name='rooms', blank=True)
    created_by = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='created_rooms'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class Message(models.Model):
    room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='messages')
    content = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)

    class Meta:
        ordering = ['timestamp']

    def __str__(self):
        return f"{self.sender.username}: {self.content[:50]}"


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    is_online = models.BooleanField(default=False)
    last_seen = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username} - {'Online' if self.is_online else 'Offline'}"