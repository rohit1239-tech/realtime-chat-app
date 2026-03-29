from django.urls import path
from .views import (
    RoomListCreateView, RoomDetailView, JoinRoomView,
    MessageListCreateView, UserListView, AllRoomsView,
    RequestJoinRoomView, ManageJoinRequestView,
    DirectMessageView, UnreadCountView,
    SearchUsersView, DeleteMessageView,
)

urlpatterns = [
    path('rooms/', RoomListCreateView.as_view(), name='room-list'),
    path('rooms/<int:pk>/', RoomDetailView.as_view(), name='room-detail'),
    path('rooms/<int:pk>/join/', JoinRoomView.as_view(), name='join-room'),
    path('rooms/<int:pk>/request-join/', RequestJoinRoomView.as_view(), name='request-join'),
    path('rooms/<int:pk>/requests/', ManageJoinRequestView.as_view(), name='manage-requests'),
    path('rooms/<int:pk>/messages/', MessageListCreateView.as_view(), name='messages'),
    path('messages/<int:pk>/delete/', DeleteMessageView.as_view(), name='delete-message'),
    path('users/', UserListView.as_view(), name='user-list'),
    path('users/search/', SearchUsersView.as_view(), name='search-users'),
    path('all-rooms/', AllRoomsView.as_view(), name='all-rooms'),
    path('dm/<str:username>/', DirectMessageView.as_view(), name='direct-message'),
    path('unread/', UnreadCountView.as_view(), name='unread-count'),
]