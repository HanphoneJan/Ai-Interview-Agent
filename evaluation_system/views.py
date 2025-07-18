# evaluation_system/views.py
import os

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from rest_framework import viewsets, permissions, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from AiInterviewAgent import settings
from .models import ResponseAnalysis, AnswerEvaluation, OverallInterviewEvaluation, ResumeEvaluation
from .resumes_engine import evaluate_resume_file
from .serializers import ResponseAnalysisSerializer, AnswerEvaluationSerializer, OverallInterviewEvaluationSerializer, \
    ResumeEvaluationSerializer
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


class ResumeEvaluationView(APIView):
    """
    处理用户上传的简历文件，进行解析和评价，并将结果存入数据库
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):
        # 检查用户是否上传了文件
        if 'resume' not in request.FILES:
            return Response({'error': '未提供简历文件'}, status=status.HTTP_400_BAD_REQUEST)

        resume_file = request.FILES['resume']

        try:
            # 确保 MEDIA_ROOT 目录存在
            os.makedirs(settings.MEDIA_ROOT, exist_ok=True)

            # 使用 default_storage 保存文件到 MEDIA_ROOT 目录
            file_path = default_storage.save(f"resumes/{resume_file.name}", ContentFile(resume_file.read()))

            # 获取文件的完整路径
            full_file_path = os.path.join(settings.MEDIA_ROOT, file_path)

            # 确保文件存在
            if not os.path.exists(full_file_path):
                raise FileNotFoundError(f"文件未成功保存到: {full_file_path}")

            # 调用 resume_engines.py 中的函数进行简历解析和评价
            evaluation_result = evaluate_resume_file(full_file_path)

            # 提取评价分数和总结
            score = evaluation_result['evaluation']['score']
            summary = evaluation_result['evaluation']['summary']

            # 将结果存入数据库，已有数据则更新
            user = request.user
            resume_evaluation, created = ResumeEvaluation.objects.get_or_create(
                user=user,
                defaults={
                    'resume_score': score,
                    'resume_summary': summary,
                }
            )

            if not created:
                # 如果记录已存在，则更新字段
                resume_evaluation.resume_score = score
                resume_evaluation.resume_summary = summary
                resume_evaluation.save()

            # 返回成功响应
            serializer = ResumeEvaluationSerializer(resume_evaluation)
            return Response(serializer.data, status=status.HTTP_200_OK if not created else status.HTTP_201_CREATED)

        except Exception as e:
            logger.error(f"简历处理和保存失败: {e}")
            return Response({'error': '简历处理失败，请稍后重试'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        finally:
            pass
            # 可选：处理完后删除文件
            # if 'file_path' in locals() and default_storage.exists(file_path):
            #     default_storage.delete(file_path)