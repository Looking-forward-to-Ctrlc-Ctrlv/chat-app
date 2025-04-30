from .views import create_group,get_group_messages
from django.urls import path, include




urlpatterns = [
    path('create/',create_group,name = 'create_group'),
    path('<int:group_id>/messages/',get_group_messages,name = 'get_group_messages')
]