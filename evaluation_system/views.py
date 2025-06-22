from rest_framework import viewsets, permissions
from .models import ResponseAnalysis, AnswerEvaluation, OverallInterviewEvaluation
from .serializers import ResponseAnalysisSerializer, AnswerEvaluationSerializer, OverallInterviewEvaluationSerializer

class ResponseAnalysisViewSet(viewsets.ModelViewSet):
    """响应分析结果管理API"""
    queryset = ResponseAnalysis.objects.all()
    serializer_class = ResponseAnalysisSerializer
    permission_classes = [permissions.IsAuthenticated]

class AnswerEvaluationViewSet(viewsets.ModelViewSet):
    """单问题评估管理API"""
    queryset = AnswerEvaluation.objects.all()
    serializer_class = AnswerEvaluationSerializer
    permission_classes = [permissions.IsAuthenticated]

class OverallInterviewEvaluationViewSet(viewsets.ModelViewSet):
    """整体面试评估管理API"""
    queryset = OverallInterviewEvaluation.objects.all()
    serializer_class = OverallInterviewEvaluationSerializer
    permission_classes = [permissions.IsAuthenticated]