from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    ResponseAnalysisViewSet,
    AnswerEvaluationViewSet,
    OverallInterviewEvaluationViewSet
)

router = DefaultRouter()
router.register(r'response-analysis', ResponseAnalysisViewSet)
router.register(r'answer-evaluations', AnswerEvaluationViewSet)
router.register(r'overall-evaluations', OverallInterviewEvaluationViewSet)

urlpatterns = [
    path('', include(router.urls)),
]