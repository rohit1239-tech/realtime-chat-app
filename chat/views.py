from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from django.contrib.auth.models import User
from django.db.models import Count, Q, Prefetch
from .models import (
    Room, Message, UserProfile, JoinRequest, FriendRequest, DirectMessage
)
from .serializers import (
    RoomSerializer, RoomListSerializer, MessageSerializer, UserSerializer,
    JoinRequestSerializer, FriendRequestSerializer, DirectMessageSerializer
)


class RoomListCreateView(generics.ListCreateAPIView):
    serializer_class = RoomListSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Room.objects.filter(members=self.request.user).select_related('created_by')

    def perform_create(self, serializer):
        room = serializer.save(created_by=self.request.user)
        room.members.add(self.request.user)


class RoomDetailView(generics.RetrieveAPIView):
    serializer_class = RoomSerializer
    permission_classes = [permissions.IsAuthenticated]
    queryset = Room.objects.select_related('created_by').prefetch_related('members')


class DeleteRoomView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def delete(self, request, pk):
        try:
            room = Room.objects.get(pk=pk, created_by=request.user)
            room_name = room.name
            room.delete()
            return Response(
                {"message": f"Room '{room_name}' deleted successfully."},
                status=status.HTTP_200_OK
            )
        except Room.DoesNotExist:
            return Response(
                {"error": "Room not found or you are not allowed to delete it."},
                status=status.HTTP_404_NOT_FOUND
            )


class AllRoomsView(generics.ListAPIView):
    serializer_class = RoomListSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Room.objects.select_related('created_by')


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
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def get_queryset(self):
        return Message.objects.filter(room_id=self.kwargs['pk'])

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        queryset.exclude(sender=request.user).filter(is_read=False).update(
            is_read=True
        )
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

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
    parser_classes = [JSONParser, MultiPartParser, FormParser]

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
            attachment = request.FILES.get('attachment')
            if not content and not attachment:
                return Response({"error": "Message cannot be empty."}, status=400)
            dm = DirectMessage.objects.create(
                sender=request.user,
                receiver=receiver,
                content=content,
                attachment=attachment
            )
            serializer = DirectMessageSerializer(
                dm,
                context={'request': request},
            )
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        except User.DoesNotExist:
            return Response({"error": "User not found."}, status=404)


class DirectMessageConversationListView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        messages = DirectMessage.objects.filter(
            Q(sender=request.user) | Q(receiver=request.user)
        ).select_related(
            'sender', 'receiver', 'sender__profile', 'receiver__profile'
        ).order_by('-timestamp')

        conversations = []
        seen_users = set()

        unread_counts = {
            item['sender']: item['count']
            for item in DirectMessage.objects.filter(
                receiver=request.user, is_read=False
            ).values('sender').annotate(count=Count('id'))
        }

        for message in messages:
            other_user = (
                message.receiver if message.sender_id == request.user.id
                else message.sender
            )
            if other_user.id in seen_users:
                continue

            seen_users.add(other_user.id)
            try:
                other_profile = other_user.profile
            except UserProfile.DoesNotExist:
                other_profile = None
            conversations.append({
                'type': 'dm',
                'username': other_user.username,
                'email': other_user.email,
                'is_online': other_profile.is_online if other_profile else False,
                'profile_picture_url': (
                    request.build_absolute_uri(other_profile.profile_picture.url)
                    if other_profile and other_profile.profile_picture
                    else None
                ),
                'last_message': {
                    'content': message.content,
                    'timestamp': message.timestamp,
                    'sender': message.sender.username,
                    'attachment_name': (
                        message.attachment.name.rsplit('/', 1)[-1]
                        if message.attachment else None
                    ),
                    'is_image': (
                        message.attachment.name.rsplit('.', 1)[-1].lower()
                        in {'jpg', 'jpeg', 'png', 'gif', 'webp', 'bmp', 'svg'}
                        if message.attachment and '.' in message.attachment.name
                        else False
                    ),
                },
                'unread_count': unread_counts.get(other_user.id, 0),
            })

        return Response(conversations)


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
        return User.objects.select_related('profile').filter(
            username__icontains=query
        ).exclude(id=self.request.user.id)[:10]


class SendFriendRequestView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, username):
        try:
            other_user = User.objects.get(username=username)
        except User.DoesNotExist:
            return Response({"error": "User not found."}, status=404)

        if other_user == request.user:
            return Response(
                {"error": "You cannot send a friend request to yourself."},
                status=status.HTTP_400_BAD_REQUEST
            )

        accepted_relation = FriendRequest.objects.filter(
            Q(sender=request.user, receiver=other_user, status='accepted') |
            Q(sender=other_user, receiver=request.user, status='accepted')
        ).first()
        if accepted_relation:
            return Response(
                {"message": f"You and {other_user.username} are already friends."},
                status=status.HTTP_200_OK
            )

        incoming_request = FriendRequest.objects.filter(
            sender=other_user,
            receiver=request.user,
            status='pending'
        ).first()
        if incoming_request:
            incoming_request.status = 'accepted'
            incoming_request.save(update_fields=['status', 'updated_at'])
            return Response(
                {"message": f"You and {other_user.username} are now friends."},
                status=status.HTTP_200_OK
            )

        friend_request, created = FriendRequest.objects.get_or_create(
            sender=request.user,
            receiver=other_user,
            defaults={'status': 'pending'}
        )
        if not created:
            if friend_request.status == 'pending':
                return Response(
                    {"message": "Friend request already sent."},
                    status=status.HTTP_400_BAD_REQUEST
                )
            if friend_request.status == 'rejected':
                friend_request.status = 'pending'
                friend_request.save(update_fields=['status', 'updated_at'])
                return Response(
                    {"message": "Friend request sent again."},
                    status=status.HTTP_200_OK
                )

        return Response(
            {"message": f"Friend request sent to {other_user.username}."},
            status=status.HTTP_201_CREATED
        )


class FriendRequestListView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        incoming = FriendRequest.objects.filter(
            receiver=request.user,
            status='pending'
        ).select_related('sender', 'receiver')
        serializer = FriendRequestSerializer(
            incoming, many=True, context={'request': request}
        )
        return Response(serializer.data)


class ManageFriendRequestView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        action = request.data.get('action')
        try:
            friend_request = FriendRequest.objects.get(
                pk=pk, receiver=request.user, status='pending'
            )
        except FriendRequest.DoesNotExist:
            return Response({"error": "Friend request not found."}, status=404)

        if action == 'accept':
            friend_request.status = 'accepted'
            friend_request.save(update_fields=['status', 'updated_at'])
            return Response(
                {"message": f"You are now friends with {friend_request.sender.username}."}
            )

        if action == 'reject':
            friend_request.status = 'rejected'
            friend_request.save(update_fields=['status', 'updated_at'])
            return Response(
                {"message": f"Rejected friend request from {friend_request.sender.username}."}
            )

        return Response({"error": "Invalid action."}, status=400)


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
