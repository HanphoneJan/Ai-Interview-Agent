# interview_manager/routing.py
from django.urls import path
from .consumers import InterviewConsumer

websocket_urlpatterns = [
    path('ws/interview/<str:session_id>/', InterviewConsumer.as_asgi()),
]