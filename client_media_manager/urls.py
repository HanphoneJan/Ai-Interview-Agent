# client_media_manager/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ResponseMetadataViewSet
from .routing import websocket_urlpatterns  # 正确导入

router = DefaultRouter()
router.register(r'response-metadata', ResponseMetadataViewSet)

urlpatterns = [
    path('', include(router.urls)),
]