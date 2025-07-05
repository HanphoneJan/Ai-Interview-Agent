from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import FeedbackReportViewSet

router = DefaultRouter()
router.register(r'feedback-reports', FeedbackReportViewSet)

urlpatterns = [
    path('', include(router.urls)),
]