from django.shortcuts import render
from django.contrib.auth import get_user_model
from chats.models import ChatModel
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from chats.models import ChatNotification
import json
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
# Create your views here.


User = get_user_model()


def index(request):
    users = User.objects.exclude(username=request.user.username)
    return render(request, 'index.html', context={'users': users})


def chatPage(request, username):
    user_obj = User.objects.get(username=username)
    users = User.objects.exclude(username=request.user.username)

    if request.user.id > user_obj.id:
        thread_name = f'chat_{request.user.id}-{user_obj.id}'
    else:
        thread_name = f'chat_{user_obj.id}-{request.user.id}'
    message_objs = ChatModel.objects.filter(thread_name=thread_name)
    return render(request, 'main_chat.html', context={'user': user_obj, 'users': users, 'messages': message_objs})


def mark_notifications_seen(request):
    """Mark all notifications as seen for the current user"""
    user = request.user
    notifications = ChatNotification.objects.filter(user=user, is_seen=False)
    notifications.update(is_seen=True)

    # Notify the user's WebSocket connection that notifications have been seen
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        f'{user.id}',
        {
            'type': 'send_notification',
            'value': json.dumps({
                'unseen_notifications': [],
                'unseen_count': 0
            })
        }
    )

    return JsonResponse({'success': True})

from django.http import HttpResponse
import os

def sw_file(request):
    # Define the correct path to your service worker file
    sw_file_path = 'static/js/sw.js'

    # Check if the file exists
    if os.path.exists(sw_file_path):
        with open(sw_file_path, 'r') as sw_file:
            content = sw_file.read()
        response = HttpResponse(content, content_type="application/javascript")
        response['Service-Worker-Allowed'] = '/'  # Allow the service worker to control the entire site
        return response
    else:
        return HttpResponse('Service Worker file not found', status=404)