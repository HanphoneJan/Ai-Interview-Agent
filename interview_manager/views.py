# interview_manager/views.py
from rest_framework import viewsets, permissions, status
from rest_framework.response import Response

from .models import InterviewScenario, InterviewSession, InterviewQuestion
from .serializers import InterviewScenarioSerializer, InterviewSessionSerializer, InterviewQuestionSerializer


class InterviewScenarioViewSet(viewsets.ModelViewSet):
    """面试场景管理API"""
    queryset = InterviewScenario.objects.all()
    serializer_class = InterviewScenarioSerializer
    permission_classes = [permissions.IsAuthenticated]


class InterviewSessionViewSet(viewsets.ModelViewSet):
    queryset = InterviewSession.objects.all()
    serializer_class = InterviewSessionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return self.queryset.filter(user=self.request.user)

    def perform_create(self, serializer):
        # 确保关联当前用户
        serializer.save(user=self.request.user)

    def create(self, request, *args, **kwargs):
        # 获取 scenario_id
        scenario_id = request.data.get('scenario_id')

        # 验证 scenario_id 是否存在
        if not scenario_id:
            return Response({"error": "scenario_id 是必需的"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            scenario = InterviewScenario.objects.get(id=scenario_id)
        except InterviewScenario.DoesNotExist:
            return Response({"error": f"找不到 ID 为 {scenario_id} 的面试场景"}, status=status.HTTP_404_NOT_FOUND)

        # 创建会话
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)

        # 返回包含 session_id 的响应
        headers = self.get_success_headers(serializer.data)
        return Response(
            {"session_id": serializer.instance.id},
            status=status.HTTP_201_CREATED,
            headers=headers
        )
class InterviewQuestionViewSet(viewsets.ReadOnlyModelViewSet):
    """面试问题管理API（只读，问题由会话自动生成）"""
    queryset = InterviewQuestion.objects.all()
    serializer_class = InterviewQuestionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """仅返回当前用户的面试问题"""
        return self.queryset.filter(session__user=self.request.user)