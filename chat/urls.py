from django.urls import path
from .views import (
    RoomListCreateView,
    RoomDetailView,
    JoinRoomView,
    MessageListCreateView,
    UserListView,
    AllRoomsView,
)

urlpatterns = [
    path('rooms/', RoomListCreateView.as_view(), name='room-list'),
    path('rooms/<int:pk>/', RoomDetailView.as_view(), name='room-detail'),
    path('rooms/<int:pk>/join/', JoinRoomView.as_view(), name='join-room'),
    path('rooms/<int:pk>/messages/', MessageListCreateView.as_view(), name='messages'),
    path('users/', UserListView.as_view(), name='user-list'),
    path('all-rooms/', AllRoomsView.as_view(), name='all-rooms'),
]