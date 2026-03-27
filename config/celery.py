import os
from celery import Celery
from celery.schedules import crontab

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

app = Celery('config')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

# Scheduled tasks
app.conf.beat_schedule = {
    'cleanup-old-messages-daily': {
        'task': 'chat.tasks.cleanup_old_messages',
        'schedule': crontab(hour=0, minute=0),  # runs every midnight
    },
}