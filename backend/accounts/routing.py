# chat/routing.py
from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    # ✅ Changed \w+ to \d+ to match numeric telegram_id
    re_path(r'ws/chat/(?P<user_id>\d+)/$', consumers.ChatConsumer.as_asgi()),
]