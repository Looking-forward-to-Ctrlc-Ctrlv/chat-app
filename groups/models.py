from django.contrib.auth.models import User
from django.db import models

from chats.models import ChatFile


class Group(models.Model):
    name = models.CharField(max_length=100)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_groups')
    members = models.ManyToManyField(User, related_name='group_memberships')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    def get_last_message(self):
        return self.messages.last()

class GroupMessage(models.Model):
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(User, on_delete=models.CASCADE)
    content = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)
    # Optional: Add file support similar to your personal chat
    file = models.ForeignKey(ChatFile, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        ordering = ['timestamp']

    def __str__(self):
        return f"{self.sender.username} in {self.group.name}: {self.content[:20]}"

class GroupNotification(models.Model):
    group = models.ForeignKey(Group, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    message = models.ForeignKey(GroupMessage, on_delete=models.CASCADE)
    is_seen = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Notification for {self.user.username} about {self.group.name}"


class GroupFile(models.Model):
    """
    Model for storing files shared in group chats
    """
    file = models.FileField(upload_to='group_files/')
    filename = models.CharField(max_length=255)
    file_type = models.CharField(max_length=100)
    uploader = models.ForeignKey(User, on_delete=models.CASCADE, related_name='group_files')
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name='files')
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.filename} - {self.group.name if hasattr(self.group, 'name') else f'Group {self.group.id}'}"