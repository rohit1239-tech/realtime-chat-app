from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/auth/', include('accounts.urls')),
    path('api/', include('chat.urls')),
    path('auth/', include('django.contrib.auth.urls')),  # ← add this
    path('', include('chat.frontend_urls')),
] + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)