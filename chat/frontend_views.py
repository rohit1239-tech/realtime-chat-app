from django.shortcuts import render

def index(request):
    return render(request, 'index.html')

def login_page(request):
    return render(request, 'login.html')

def register_page(request):
    return render(request, 'register.html')

def chat_home(request):
    return render(request, 'chat_home.html')

def chat_room(request, room_name):
    return render(request, 'chat_room.html', {'room_name': room_name})

def dm_page(request, username):
    return render(request, 'dm.html', {'other_username': username})

def admin_panel(request):
    return render(request, 'admin_panel.html')