from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
import json
from .models import Group, GroupMessage, GroupNotification

@login_required
@require_POST
def create_group(request):
    try:
        data = json.loads(request.body)
        group_name = data.get('name')
        member_ids = data.get('members', [])

        if not group_name:
            return JsonResponse({'error': 'Group name is required'}, status=400)

        if not isinstance(member_ids, list):
            return JsonResponse({'error': 'Members should be an array'}, status=400)

        # Ensure the creator is included in members
        if request.user.id not in member_ids:
            member_ids.append(request.user.id)

        with transaction.atomic():
            # Create the group
            group = Group.objects.create(
                name=group_name,
                created_by=request.user
            )

            # Add members
            members = User.objects.filter(id__in=member_ids)
            group.members.add(*members)

            # Create welcome message
            welcome_message = GroupMessage.objects.create(
                group=group,
                sender=request.user,
                content=f"{request.user.username} created this group"
            )

            return JsonResponse({
                'success': True,
                'group_id': group.id,
                'group_name': group.name
            })

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def get_group_messages(request, group_id):
    try:
        group = Group.objects.get(id=group_id)

        # Verify user is a member of the group
        if not group.members.filter(id=request.user.id).exists():
            raise PermissionDenied

        # Mark notifications as seen
        GroupNotification.objects.filter(
            group=group,
            user=request.user,
            is_seen=False
        ).update(is_seen=True)

        # Get messages with sender info
        messages = GroupMessage.objects.filter(group=group).select_related('sender').order_by('timestamp')

        messages_data = []
        for message in messages:
            messages_data.append({
                'id': message.id,
                'sender': {
                    'id': message.sender.id,
                    'username': message.sender.username
                },
                'content': message.content,
                'timestamp': message.timestamp.isoformat(),
                'is_current_user': message.sender.id == request.user.id
            })

        return JsonResponse({
            'group': {
                'id': group.id,
                'name': group.name,
                'created_at': group.created_at.isoformat()
            },
            'messages': messages_data
        })

    except Group.DoesNotExist:
        return JsonResponse({'error': 'Group not found'}, status=404)
    except PermissionDenied:
        return JsonResponse({'error': 'You are not a member of this group'}, status=403)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
