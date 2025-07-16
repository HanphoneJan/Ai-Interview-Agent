from rest_framework import viewsets, permissions, mixins
from rest_framework.decorators import action
from rest_framework.response import Response

from evaluation_system.audio_generate_engines import synthesize
from .models import InterviewScenario, InterviewSession, InterviewQuestion
from .serializers import InterviewScenarioSerializer, InterviewSessionSerializer, InterviewQuestionSerializer
import random


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
        serializer.save(user=self.request.user)

    @action(detail=True, methods=['get'])
    async def next_question(self, request, pk=None):
        try:
            session = self.get_object()
        except InterviewSession.DoesNotExist:
            return Response({"error": "会话不存在"}, status=404)

        if session.user != request.user and not request.user.is_staff:
            return Response({"error": "无权限访问此会话"}, status=403)

        question_count = InterviewQuestion.objects.filter(session=session).count()

        if question_count < 5:
            question_bank = [
                "请介绍你最熟悉的项目",
                "如何解决代码中的性能瓶颈",
                "描述一次团队协作中遇到的挑战",
                "说说你对这个技术领域的理解",
                "如果你负责这个项目，会采取什么策略"
            ]

            asked_questions = InterviewQuestion.objects.filter(session=session).values_list('question_text', flat=True)
            available_questions = [q for q in question_bank if q not in asked_questions]

            next_question_text = random.choice(available_questions) if available_questions else "请分享你的职业规划"

            next_question = InterviewQuestion.objects.create(
                session=session,
                question_text=next_question_text,
                question_number=question_count + 1
            )

            # 调用语音合成模块
            audio_result = await synthesize(next_question_text)
            if audio_result["success"]:
                audio_data = audio_result["audio_data"]
                # 这里可以将音频数据传递给 client_media_manager，例如通过 WebSocket 发送
                # 假设我们有一个 send_audio_to_client 函数来处理这个逻辑
                # send_audio_to_client(session.id, audio_data)

            serializer = InterviewQuestionSerializer(next_question)
            return Response(serializer.data)
        else:
            session.is_finished = True
            session.end_time = None
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