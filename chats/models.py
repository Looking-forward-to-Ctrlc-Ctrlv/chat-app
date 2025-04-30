from django.db import models
from django.contrib.auth.models import User

# Create your models here.

class UserProfileModel(models.Model):
    objects = models.Manager()
    user = models.OneToOneField(to=User, on_delete=models.CASCADE)
    name = models.CharField(blank=True, null=True, max_length=100)
    online_status = models.BooleanField(default=False)

    def __str__(self) -> str:
        return self.user.username


class ChatModel(models.Model):
    objects = models.Manager()
    sender = models.CharField(max_length=100, default=None)
    message = models.TextField(null=True, blank=True)
    thread_name = models.CharField(null=True, blank=True, max_length=50)
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return self.message
    
class ChatNotification(models.Model):
    chat = models.ForeignKey(to=ChatModel, on_delete=models.CASCADE)
    user = models.ForeignKey(to=User, on_delete=models.CASCADE)
    is_seen = models.BooleanField(default=False)
    objects = models.Manager()
    def __str__(self) -> str:
        return self.user.username


class ChatFile(models.Model):
    objects = models.Manager()
    file = models.FileField(upload_to='chat_files/')
    filename = models.CharField(max_length=255)
    file_type = models.CharField(max_length=100)
    uploader = models.ForeignKey(User, on_delete=models.CASCADE, related_name='uploaded_files')
    upload_date = models.DateTimeField(auto_now_add=True)
    thread_name = models.CharField(max_length=255)

    def __str__(self):
        return f"{self.filename} ({self.file_type})"

