# client_media_manager/routing.py
from django.urls import path, re_path
from .consumers import LiveStreamConsumer

websocket_urlpatterns = [
    re_path(r'^api/media/ws/live-stream/(?P<session_id>[^/]+)/$', LiveStreamConsumer.as_asgi()),
]