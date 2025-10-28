"""
ASGI config for recommendation_sys project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/howto/deployment/asgi/
"""

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "recommendation_sys.settings")

# Initialize the Django ASGI application
# Django must be initialized before importing routing to ensure the AppRegistry is populated.
django_asgi_app = get_asgi_application()

# # Import routing and channels after initializing Django
from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.security.websocket import AllowedHostsOriginValidator
from recom_sys_app import routing

# ASGI application, handling HTTP and WebSocket
application = ProtocolTypeRouter({
    # Django's ASGI application handles traditional HTTP requests.
    "http": django_asgi_app,
    
    # WebSocket Chat Handler with Authentication and Source Verification
    "websocket": AllowedHostsOriginValidator(
        AuthMiddlewareStack(
            URLRouter(
                routing.websocket_urlpatterns
            )
        )
    ),
})