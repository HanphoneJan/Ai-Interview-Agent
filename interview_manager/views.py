from rest_framework import viewsets, permissions, mixins
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import InterviewScenario, InterviewSession, InterviewQuestion
from .serializers import InterviewScenarioSerializer, InterviewSessionSerializer, InterviewQuestionSerializer
import random


class InterviewScenarioViewSet(viewsets.ModelViewSet):
    """面试场景管理API"""
    queryset = InterviewScenario.objects.all()
    serializer_class = InterviewScenarioSerializer
    permission_classes = [permissions.IsAuthenticated]


class InterviewSessionViewSet(viewsets.ModelViewSet):
    """面试会话管理API（整合自定义功能）"""
    queryset = InterviewSession.objects.all()
    serializer_class = InterviewSessionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """仅返回当前用户的面试会话"""
        return self.queryset.filter(user=self.request.user)

    def perform_create(self, serializer):
        # 自动关联当前用户
        serializer.save(user=self.request.user)

    @action(detail=True, methods=['get'])
    def next_question(self, request, pk=None):
        """获取面试的下一个问题（整合到视图集中）"""
        try:
            session = self.get_object()
        except InterviewSession.DoesNotExist:
            return Response({"error": "会话不存在"}, status=404)

        # 验证用户权限
        if session.user != request.user and not request.user.is_staff:
            return Response({"error": "无权限访问此会话"}, status=403)

        # 获取已问问题数量
        question_count = InterviewQuestion.objects.filter(session=session).count()

        # 模拟生成下一个问题（实际应根据场景动态生成）
        if question_count < 5:  # 假设每个面试最多5个问题
            # 从场景中获取问题库（实际应从数据库或外部服务获取）
            question_bank = [
                "请介绍你最熟悉的项目",
                "如何解决代码中的性能瓶颈",
                "描述一次团队协作中遇到的挑战",
                "说说你对这个技术领域的理解",
                "如果你负责这个项目，会采取什么策略"
            ]

            # 避免重复问题
            asked_questions = InterviewQuestion.objects.filter(session=session).values_list('question_text', flat=True)
            available_questions = [q for q in question_bank if q not in asked_questions]

            # 选择问题（优先使用可用问题，若无则使用默认问题）
            next_question_text = random.choice(available_questions) if available_questions else "请分享你的职业规划"

            # 创建新问题
            next_question = InterviewQuestion.objects.create(
                session=session,
                question_text=next_question_text,
                question_number=question_count + 1
            )

            serializer = InterviewQuestionSerializer(next_question)
            return Response(serializer.data)
        else:
            # 面试结束，标记会话为已完成
            session.is_finished = True
            session.end_time = None  # 可根据需求设置结束时间
            session.save()
            return Response({"message": "面试已结束"}, status=200)


class InterviewQuestionViewSet(viewsets.ReadOnlyModelViewSet):
    """面试问题管理API（只读，问题由会话自动生成）"""
    queryset = InterviewQuestion.objects.all()
    serializer_class = InterviewQuestionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """仅返回当前用户的面试问题"""
        return self.queryset.filter(session__user=self.request.user)