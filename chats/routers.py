from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    # Personal chat consumer - using the pattern shown in the 404 error
    re_path(r'ws/(?P<id>\d+)/$', consumers.PersonalChatConsumer.as_asgi()),

    # Online status consumer - using the pattern shown in the 404 error
    re_path(r'ws/online/$', consumers.OnlineStatusConsumer.as_asgi()),

    # Notification consumer - using the pattern shown in the 404 error
    re_path(r'ws/notify/$', consumers.NotificationConsumer.as_asgi()),
]