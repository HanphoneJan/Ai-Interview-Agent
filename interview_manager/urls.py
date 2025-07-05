from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    InterviewScenarioViewSet,
    InterviewSessionViewSet,
    InterviewQuestionViewSet
)

router = DefaultRouter()
router.register(r'scenarios', InterviewScenarioViewSet)
router.register(r'sessions', InterviewSessionViewSet)
router.register(r'questions', InterviewQuestionViewSet)

urlpatterns = [
    path('', include(router.urls)),
    # 自定义动作已通过@action整合到视图集，无需额外配置
]