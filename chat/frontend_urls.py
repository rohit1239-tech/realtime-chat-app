from django.urls import path
from . import frontend_views

urlpatterns = [
    path('', frontend_views.index, name='index'),
    path('login/', frontend_views.login_page, name='login'),
    path('register/', frontend_views.register_page, name='register'),
    path('chat/', frontend_views.chat_home, name='chat-home'),
    path('chat/<str:room_name>/', frontend_views.chat_room, name='chat-room'),
    path('dm/<str:username>/', frontend_views.dm_page, name='dm-page'),
    path('admin-panel/', frontend_views.admin_panel, name='admin-panel'),
]