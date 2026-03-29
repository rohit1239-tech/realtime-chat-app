from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from django.contrib.auth.models import User
from .models import Room, Message, UserProfile, JoinRequest, DirectMessage
from .serializers import (
    RoomSerializer, MessageSerializer, UserSerializer,
    JoinRequestSerializer, DirectMessageSerializer
)


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


class AllRoomsView(generics.ListAPIView):
    serializer_class = RoomSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Room.objects.all()


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
            return Response({"error": "Room not found."}, status=404)


class MessageListCreateView(generics.ListCreateAPIView):
    serializer_class = MessageSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Message.objects.filter(room_id=self.kwargs['pk'])

    def perform_create(self, serializer):
        room = Room.objects.get(pk=self.kwargs['pk'])
        serializer.save(sender=self.request.user, room=room)


class UserListView(generics.ListAPIView):
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return User.objects.exclude(id=self.request.user.id)


class RequestJoinRoomView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        try:
            room = Room.objects.get(pk=pk)
            if room.members.filter(id=request.user.id).exists():
                return Response(
                    {"message": "You are already a member."},
                    status=status.HTTP_400_BAD_REQUEST
                )
            if not room.requires_approval:
                room.members.add(request.user)
                return Response(
                    {"message": f"Joined '{room.name}' successfully."},
                    status=status.HTTP_200_OK
                )
            join_req, created = JoinRequest.objects.get_or_create(
                room=room, user=request.user
            )
            if not created:
                return Response(
                    {"message": f"Request already {join_req.status}."},
                    status=status.HTTP_400_BAD_REQUEST
                )
            return Response(
                {"message": "Join request sent! Waiting for admin approval."},
                status=status.HTTP_201_CREATED
            )
        except Room.DoesNotExist:
            return Response({"error": "Room not found."}, status=404)


class ManageJoinRequestView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, pk):
        try:
            room = Room.objects.get(pk=pk, created_by=request.user)
            requests = JoinRequest.objects.filter(room=room, status='pending')
            serializer = JoinRequestSerializer(requests, many=True)
            return Response(serializer.data)
        except Room.DoesNotExist:
            return Response({"error": "Room not found."}, status=404)

    def post(self, request, pk):
        request_id = request.data.get('request_id')
        action = request.data.get('action')
        try:
            room = Room.objects.get(pk=pk, created_by=request.user)
            join_req = JoinRequest.objects.get(id=request_id, room=room)
            if action == 'accept':
                join_req.status = 'accepted'
                join_req.save()
                room.members.add(join_req.user)
                return Response({"message": f"Accepted {join_req.user.username}."})
            elif action == 'reject':
                join_req.status = 'rejected'
                join_req.save()
                return Response({"message": f"Rejected {join_req.user.username}."})
            else:
                return Response({"error": "Invalid action."}, status=400)
        except (Room.DoesNotExist, JoinRequest.DoesNotExist):
            return Response({"error": "Not found."}, status=404)


class DirectMessageView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, username):
        try:
            other_user = User.objects.get(username=username)
            messages = DirectMessage.objects.filter(
                sender__in=[request.user, other_user],
                receiver__in=[request.user, other_user]
            ).order_by('timestamp')
            messages.filter(
                receiver=request.user, is_read=False
            ).update(is_read=True)
            serializer = DirectMessageSerializer(messages, many=True)
            return Response(serializer.data)
        except User.DoesNotExist:
            return Response({"error": "User not found."}, status=404)

    def post(self, request, username):
        try:
            receiver = User.objects.get(username=username)
            content = request.data.get('content', '').strip()
            if not content:
                return Response({"error": "Message cannot be empty."}, status=400)
            dm = DirectMessage.objects.create(
                sender=request.user,
                receiver=receiver,
                content=content
            )
            serializer = DirectMessageSerializer(dm)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        except User.DoesNotExist:
            return Response({"error": "User not found."}, status=404)


class UnreadCountView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        unread_dms = DirectMessage.objects.filter(
            receiver=request.user, is_read=False
        ).count()
        room_unreads = []
        for room in request.user.rooms.all():
            count = Message.objects.filter(
                room=room, is_read=False
            ).exclude(sender=request.user).count()
            if count > 0:
                room_unreads.append({'room': room.name, 'count': count})
        return Response({
            'unread_dms': unread_dms,
            'room_unreads': room_unreads,
            'total': unread_dms + sum(r['count'] for r in room_unreads)
        })


class SearchUsersView(generics.ListAPIView):
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        query = self.request.query_params.get('q', '')
        if not query:
            return User.objects.none()
        return User.objects.filter(
            username__icontains=query
        ).exclude(id=self.request.user.id)[:10]


class DeleteMessageView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def delete(self, request, pk):
        try:
            message = Message.objects.get(pk=pk, sender=request.user)
            message.delete()
            return Response({"message": "Message deleted."}, status=204)
        except Message.DoesNotExist:
            return Response(
                {"error": "Not found or not your message."}, status=404
            )