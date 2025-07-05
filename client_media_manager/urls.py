# client_media_manager/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ResponseMetadataViewSet
from .consumers import LiveStreamConsumer

router = DefaultRouter()
router.register(r'response-metadata', ResponseMetadataViewSet)

websocket_urlpatterns = [
    path('ws/live-stream/<str:session_id>/', LiveStreamConsumer.as_asgi()),
]

urlpatterns = [
    path('', include(router.urls)),
    path('ws/', include(websocket_urlpatterns)),
]