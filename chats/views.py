from django.shortcuts import render
from django.contrib.auth import get_user_model
from django.views.decorators.csrf import csrf_exempt

from chats.models import ChatModel, ChatFile
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from chats.models import ChatNotification
import json
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from django.http import HttpResponse
import os
from groups.models import Group
# Create your views here.

User = get_user_model()


def index(request):
    users = User.objects.exclude(username=request.user.username)
    return render(request, 'index.html', context={'users': users})


def chatPage(request, username):
    user_obj = User.objects.get(username=username)
    users = User.objects.exclude(username=request.user.username)

    # Get latest messages for ALL users at once
    latest_messages = {}
    for user in users:
        uid1, uid2 = sorted([request.user.id, user.id])
        if request.user.id > user_obj.id:
            thread_name = f'chat_{request.user.id}-{user_obj.id}'
        else:
            thread_name = f'chat_{user_obj.id}-{request.user.id}'
        last_message = ChatModel.objects.filter(thread_name=thread_name).order_by('-timestamp').first()
        latest_messages[user.id] = last_message  # Store message object directly

    # Attach last message to each user object
    for user in users:
        user.last_message = latest_messages.get(user.id)
    message_objs = ChatModel.objects.filter(thread_name=thread_name)
    return render(request, 'main_chat.html', {
        'user': user_obj,
        'users': users,
        # Remove 'latest_messages' from context - no longer needed
        'messages': message_objs,
        'groups': Group.objects.filter(members=request.user),
        'thread_name': thread_name
    })




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


@login_required
@csrf_exempt
def upload_file(request):
    if request.method == 'POST' and request.FILES.get('file'):
        uploaded_file = request.FILES['file']
        thread_name = request.POST.get('thread_name')

        # Create file record
        chat_file = ChatFile.objects.create(
            file=uploaded_file,
            filename=uploaded_file.name,
            file_type=os.path.splitext(uploaded_file.name)[1],
            uploader=request.user,
            thread_name=thread_name
        )

        # Return file info as JSON
        return JsonResponse({
            'status': 'success',
            'file_id': chat_file.id,
            'filename': chat_file.filename,
            'file_url': chat_file.file.url,
            'file_type': chat_file.file_type
        })

    return JsonResponse({'status': 'error', 'message': 'Invalid request'}, status=400)


def get_file_details(request, file_id):
    """
    Get file details by file ID for chat messages
    """
    try:
        # Get the file object
        file_id = file_id - 1
        file_obj = ChatFile.objects.get(id=file_id)
        print(file_obj.filename)
        # Check if user has permission (is part of the chat thread)
        thread_name = file_obj.thread_name
        thread_id = thread_name.replace('chat_', '')
        user_ids = [int(uid) for uid in thread_id.split('-')]

        if request.user.id not in user_ids:
            return JsonResponse({'error': 'Permission denied'}, status=403)

        # Get file URL
        file_url = request.build_absolute_uri(file_obj.file.url) if hasattr(file_obj.file, 'url') else str(
            file_obj.file)
        print(file_url)

        # Return file details
        return JsonResponse({
            'file_id': file_obj.id,
            'filename': file_obj.filename,
            'file_type': file_obj.file_type,
            'file_url': file_url,
            'file_size': file_obj.file.size if hasattr(file_obj.file, 'size') else 0
        })
    except ChatFile.DoesNotExist:
        return JsonResponse({'error': 'File not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


