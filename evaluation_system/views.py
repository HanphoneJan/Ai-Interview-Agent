# evaluation_system/views.py
from rest_framework import viewsets, permissions
from .models import ResponseAnalysis, AnswerEvaluation, OverallInterviewEvaluation
from .serializers import ResponseAnalysisSerializer, AnswerEvaluationSerializer, OverallInterviewEvaluationSerializer
import logging

logger = logging.getLogger(__name__)

class ResponseAnalysisViewSet(viewsets.ModelViewSet):
    """响应分析结果管理API"""
    queryset = ResponseAnalysis.objects.all()
    serializer_class = ResponseAnalysisSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        try:
            serializer.save()
            logger.info(f"创建响应分析结果: {serializer.instance}")
        except Exception as e:
            logger.error(f"创建响应分析结果出错: {e}")

class AnswerEvaluationViewSet(viewsets.ModelViewSet):
    """单问题评估管理API"""
    queryset = AnswerEvaluation.objects.all()
    serializer_class = AnswerEvaluationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        try:
            serializer.save()
            logger.info(f"创建单问题评估: {serializer.instance}")
        except Exception as e:
            logger.error(f"创建单问题评估出错: {e}")

class OverallInterviewEvaluationViewSet(viewsets.ModelViewSet):
    """整体面试评估管理API"""
    queryset = OverallInterviewEvaluation.objects.all()
    serializer_class = OverallInterviewEvaluationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        try:
            serializer.save()
            logger.info(f"创建整体面试评估: {serializer.instance}")
        except Exception as e:
            logger.error(f"创建整体面试评估出错: {e}")