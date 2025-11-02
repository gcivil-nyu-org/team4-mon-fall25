"""
WebSocket URL routing configuration.

This module defines the WebSocket URL patterns and maps them to consumers.
"""
from django.urls import re_path
from . import consumers

# WebSocket URL patterns
websocket_urlpatterns = [
    # Group Chat WebSocket Endpoint
    # URL format: ws://domain/ws/chat/<group_id>/
    re_path(
        r'^ws/chat/(?P<group_id>[\w-]+)/$',
        consumers.ChatConsumer.as_asgi()
    ),
    # Group Movie Matching WebSocket Endpoint
    # URL format: ws://domain/ws/match/<group_code>/
    re_path(
        r'^ws/match/(?P<group_code>[\w-]+)/$',
        consumers.MatchConsumer.as_asgi()
    ),
]