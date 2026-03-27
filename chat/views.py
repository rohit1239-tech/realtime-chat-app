from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from django.contrib.auth.models import User
from .models import Room, Message, UserProfile
from .serializers import RoomSerializer, MessageSerializer, UserSerializer


class RoomListCreateView(generics.ListCreateAPIView):
    serializer_class = RoomSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Room.objects.filter(members=self.request.user)

    def perform_create(self, serializer):
        room = serializer.save(created_by=self.request.user)
        room.members.add(self.request.user)


class RoomDetailView(generics.RetrieveAPIView):
    serializer_class = RoomSerializer
    permission_classes = [permissions.IsAuthenticated]
    queryset = Room.objects.all()


class JoinRoomView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        try:
            room = Room.objects.get(pk=pk)
            room.members.add(request.user)
            return Response(
                {"message": f"Joined room '{room.name}' successfully."},
                status=status.HTTP_200_OK
            )
        except Room.DoesNotExist:
            return Response(
                {"error": "Room not found."},
                status=status.HTTP_404_NOT_FOUND
            )


class MessageListCreateView(generics.ListCreateAPIView):
    serializer_class = MessageSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        room_id = self.kwargs['pk']
        return Message.objects.filter(room_id=room_id)

    def perform_create(self, serializer):
        room_id = self.kwargs['pk']
        room = Room.objects.get(pk=room_id)
        serializer.save(sender=self.request.user, room=room)


class UserListView(generics.ListAPIView):
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return User.objects.exclude(id=self.request.user.id)