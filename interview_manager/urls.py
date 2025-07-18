from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    InterviewScenarioViewSet,
    InterviewSessionViewSet,
    InterviewQuestionViewSet,
    UserInterviewDataView
)

router = DefaultRouter()
router.register(r'scenarios', InterviewScenarioViewSet)
router.register(r'sessions', InterviewSessionViewSet)
router.register(r'questions', InterviewQuestionViewSet)

urlpatterns = [
    path('', include(router.urls)),
    path('user-interview-data/',UserInterviewDataView.as_view(), name='user-interview-data'),
]