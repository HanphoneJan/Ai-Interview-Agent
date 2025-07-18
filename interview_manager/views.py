# interview_manager/views.py
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework.views import APIView

from user_manager.models import User
from rest_framework.permissions import IsAuthenticated
from evaluation_system.models import ResponseMetadata, ResponseAnalysis, AnswerEvaluation, OverallInterviewEvaluation, \
    ResumeEvaluation
from .models import InterviewScenario, InterviewSession, InterviewQuestion
from .serializers import InterviewScenarioSerializer, InterviewSessionSerializer, InterviewQuestionSerializer
from evaluation_system.serializers import ResponseMetadataSerializer, ResponseAnalysisSerializer, \
    AnswerEvaluationSerializer, OverallInterviewEvaluationSerializer, ResumeEvaluationSerializer


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


class UserInterviewDataView(APIView):
    permission_classes = [IsAuthenticated]  # 需要认证才能访问
    def get(self,request):
        # 获取当前用户

        user = request.user

        # 筛选出当前用户的所有面试会话
        interview_sessions = InterviewSession.objects.filter(user=user)

        # 初始化一个空列表来存储最终的数据
        interview_data = []

        # 遍历每个面试会话
        for session in interview_sessions:
            # 序列化面试会话
            session_serializer = InterviewSessionSerializer(session)

            # 获取与当前会话相关的所有面试问题
            interview_questions = InterviewQuestion.objects.filter(session=session)
            question_serializer = InterviewQuestionSerializer(interview_questions, many=True)

            # 获取每个问题的回答元数据、分析和评估
            questions_data = []
            for question in interview_questions:
                # 获取回答元数据
                response_metadata = ResponseMetadata.objects.filter(question=question).first()
                metadata_serializer = ResponseMetadataSerializer(response_metadata) if response_metadata else None

                # 获取分析结果
                response_analysis = ResponseAnalysis.objects.filter(metadata=response_metadata).first() if response_metadata else None
                analysis_serializer = ResponseAnalysisSerializer(response_analysis) if response_analysis else None

                # 获取评估结果
                answer_evaluations = AnswerEvaluation.objects.filter(question=question)
                evaluation_serializer = AnswerEvaluationSerializer(answer_evaluations, many=True) if answer_evaluations.exists() else None

                questions_data.append({
                    'question': InterviewQuestionSerializer(question).data,
                    'response_metadata': metadata_serializer.data if metadata_serializer else None,
                    'response_analysis': analysis_serializer.data if analysis_serializer else None,
                    'evaluations': evaluation_serializer.data if evaluation_serializer else []
                })

            # 获取面试会话对应的面试场景
            scenario = session.scenario
            scenario_serializer = InterviewScenarioSerializer(scenario)

            # 获取整体评估
            overall_evaluation = OverallInterviewEvaluation.objects.filter(session=session).first()
            overall_eval_serializer = OverallInterviewEvaluationSerializer(overall_evaluation) if overall_evaluation else None

            # 获取简历评估
            resume_evaluation = ResumeEvaluation.objects.filter(user=user).first()
            resume_eval_serializer = ResumeEvaluationSerializer(resume_evaluation) if resume_evaluation else None

            # 组合数据
            session_data = {
                'session': session_serializer.data,
                'scenario': scenario_serializer.data,
                'questions': questions_data,
                'overall_evaluation': overall_eval_serializer.data if overall_eval_serializer else None,
                'resume_evaluation': resume_eval_serializer.data if resume_eval_serializer else None
            }

            # 将组合好的数据添加到最终列表中
            interview_data.append(session_data)

        return Response(interview_data, status=status.HTTP_200_OK)