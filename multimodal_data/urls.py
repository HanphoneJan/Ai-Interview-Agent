from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ResponseMetadataViewSet

router = DefaultRouter()
router.register(r'response-metadata', ResponseMetadataViewSet)

urlpatterns = [
    path('', include(router.urls)),
]