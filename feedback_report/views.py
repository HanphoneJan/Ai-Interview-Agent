from rest_framework import viewsets, permissions
from .models import FeedbackReport
from .serializers import FeedbackReportSerializer

class FeedbackReportViewSet(viewsets.ModelViewSet):
    """反馈报告管理API"""
    queryset = FeedbackReport.objects.all()
    serializer_class = FeedbackReportSerializer
    permission_classes = [permissions.IsAuthenticated]