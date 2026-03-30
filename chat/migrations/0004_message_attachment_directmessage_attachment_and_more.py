from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('chat', '0003_userprofile_profile_picture'),
    ]

    operations = [
        migrations.AddField(
            model_name='directmessage',
            name='attachment',
            field=models.FileField(blank=True, null=True, upload_to='dm_attachments/'),
        ),
        migrations.AddField(
            model_name='message',
            name='attachment',
            field=models.FileField(blank=True, null=True, upload_to='message_attachments/'),
        ),
        migrations.AlterField(
            model_name='directmessage',
            name='content',
            field=models.TextField(blank=True),
        ),
        migrations.AlterField(
            model_name='message',
            name='content',
            field=models.TextField(blank=True),
        ),
    ]
