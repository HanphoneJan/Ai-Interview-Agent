# client_media_manager/routing.py
from django.urls import path
from .consumers import LiveStreamConsumer

websocket_urlpatterns = [
    path('ws/live-stream/<str:session_id>/', LiveStreamConsumer.as_asgi()),
]