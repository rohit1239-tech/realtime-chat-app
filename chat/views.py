from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.contrib.auth.models import User
from django.db.models import Count, Q, Prefetch
from .models import (
    Room, Message, UserProfile, JoinRequest, FriendRequest, DirectMessage
)
from .serializers import (
    RoomSerializer, RoomListSerializer, MessageSerializer, UserSerializer,
    JoinRequestSerializer, FriendRequestSerializer, DirectMessageSerializer
)


def get_friend_relation(user_a, user_b):
    return FriendRequest.objects.filter(
        Q(sender=user_a, receiver=user_b) |
        Q(sender=user_b, receiver=user_a)
    ).order_by('-updated_at', '-created_at').first()


def can_direct_message(user_a, user_b):
    relation = get_friend_relation(user_a, user_b)
    return relation is not None and relation.status == 'accepted'


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
        return Message.objects.filter(
            room_id=self.kwargs['pk'],
            room__members=self.request.user
        )

    def list(self, request, *args, **kwargs):
        room = Room.objects.filter(pk=self.kwargs['pk']).first()
        if not room:
            return Response({"error": "Room not found."}, status=status.HTTP_404_NOT_FOUND)
        if not room.members.filter(pk=request.user.id).exists():
            return Response(
                {"error": "You can only read messages in rooms you joined."},
                status=status.HTTP_403_FORBIDDEN
            )
        queryset = self.get_queryset()
        queryset.exclude(sender=request.user).filter(is_read=False).update(
            is_read=True
        )
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    def perform_create(self, serializer):
        room = Room.objects.get(pk=self.kwargs['pk'])
        if not room.members.filter(pk=self.request.user.id).exists():
            raise PermissionError("You can only send messages in rooms you joined.")
        serializer.save(sender=self.request.user, room=room)

    def create(self, request, *args, **kwargs):
        try:
            return super().create(request, *args, **kwargs)
        except PermissionError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_403_FORBIDDEN)


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
            if not can_direct_message(request.user, other_user):
                relation = get_friend_relation(request.user, other_user)
                return Response(
                    {
                        "error": "Messages are allowed only after the friend request is accepted.",
                        "friendship_status": relation.status if relation else "none",
                    },
                    status=status.HTTP_403_FORBIDDEN
                )
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
            if not can_direct_message(request.user, receiver):
                relation = get_friend_relation(request.user, receiver)
                return Response(
                    {
                        "error": "Messages are allowed only after the friend request is accepted.",
                        "friendship_status": relation.status if relation else "none",
                    },
                    status=status.HTTP_403_FORBIDDEN
                )
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
            payload = serializer.data
            channel_layer = get_channel_layer()
            for user_id in {request.user.id, receiver.id}:
                async_to_sync(channel_layer.group_send)(
                    f'dm_user_{user_id}',
                    {
                        'type': 'direct_message',
                        'message': payload,
                    }
                )
            return Response(payload, status=status.HTTP_201_CREATED)
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


class RequestSummaryView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        friend_requests = FriendRequest.objects.filter(
            receiver=request.user,
            status='pending'
        ).count()
        room_requests = JoinRequest.objects.filter(
            room__created_by=request.user,
            status='pending'
        ).count()
        return Response({
            'friend_requests': friend_requests,
            'room_requests': room_requests,
            'total': friend_requests + room_requests,
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
