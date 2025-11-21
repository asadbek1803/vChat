# config/asgi.py - MUHIM: Import tartibiga e'tibor bering!

import os
import django

# 1️⃣ BIRINCHI: Django settings'ni sozlang
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

# 2️⃣ IKKINCHI: Django'ni setup qiling
django.setup()

# 3️⃣ UCHINCHI: Endi import qilish xavfsiz
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from accounts.routing import websocket_urlpatterns

# 4️⃣ ASGI application yaratish
application = ProtocolTypeRouter({
    'http': get_asgi_application(),
    'websocket': AuthMiddlewareStack(
        URLRouter(
            websocket_urlpatterns
        )
    ),
})

print("✅ ASGI application loaded successfully!")