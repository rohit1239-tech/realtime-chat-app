from celery import shared_task
from django.core.mail import send_mail
from django.contrib.auth.models import User
from .models import Message, Room


@shared_task
def send_message_notification(sender_username, room_name, message_content, recipient_id):
    try:
        recipient = User.objects.get(id=recipient_id)
        if not recipient.profile.is_online and recipient.email:
            send_mail(
                subject=f'New message in #{room_name}',
                message=f'{sender_username} said: {message_content}',
                from_email='noreply@chatapp.com',
                recipient_list=[recipient.email],
                fail_silently=True,
            )
    except User.DoesNotExist:
        pass


@shared_task
def cleanup_old_messages():
    from django.utils import timezone
    from datetime import timedelta
    cutoff = timezone.now() - timedelta(days=30)
    deleted, _ = Message.objects.filter(timestamp__lt=cutoff).delete()
    return f"Deleted {deleted} old messages"