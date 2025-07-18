from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from interview_manager.models import InterviewQuestion, InterviewSession
from user_manager.models import User

class ResponseMetadata(models.Model):
    """存储回答的时长等元数据（仅文本/数值信息）"""
    question = models.ForeignKey(
        InterviewQuestion,
        on_delete=models.CASCADE,
        related_name='response_metadata'
    )  # 关联当前问题
    audio_duration = models.DurationField(null=True, blank=True)  # 音频时长（数值型）
    video_duration = models.DurationField(null=True, blank=True)  # 视频时长（数值型）
    upload_timestamp = models.DateTimeField(auto_now_add=True)  # 上传时间戳

    def __str__(self):
        return f"Response Meta for Q{self.question.question_number}"


class ResponseAnalysis(models.Model):
    """存储多模态分析结果（仅文本化结果）"""
    metadata = models.OneToOneField(
        ResponseMetadata,
        on_delete=models.CASCADE,
        related_name='analysis'
    )
    speech_text = models.TextField()  # 语音转文字结果（文本）
    facial_expression = models.TextField(blank=True)  # 表情分析结果（文本化，如JSON字符串）
    body_language = models.TextField(blank=True)  # 肢体语言分析结果（文本化）
    analysis_timestamp = models.DateTimeField(auto_now_add=True)  # 分析时间

    def __str__(self):
        return f"Analysis for Q{self.metadata.question.question_number}"


class AnswerEvaluation(models.Model):
    """单问题回答的评估结果（仅文本/数值）"""
    question = models.ForeignKey(
        InterviewQuestion,
        on_delete=models.CASCADE,
        related_name='evaluations'
    )
    analysis = models.ForeignKey(
        ResponseAnalysis,
        on_delete=models.CASCADE,
        related_name='evaluations'
    )
    evaluation_text = models.TextField()  # 评估文本内容
    score = models.FloatField(default=0)  # 单项评分（数值）
    evaluated_at = models.DateTimeField(auto_now_add=True)  # 评估时间

    def __str__(self):
        return f"Evaluation for Q{self.question.question_number}"


class ResumeEvaluation(models.Model):
    """简历评估信息（仅文本/数值）"""
    user = models.OneToOneField(  # 修正：关联User而非InterviewSession
        User,
        on_delete=models.CASCADE,
        related_name='resume_evaluation'
    )
    resume_score = models.PositiveIntegerField(default=0)  # 简历评分（数值）
    resume_summary = models.TextField(blank=True, null=True)  # 简历总结（文本）

    def clean(self):
        if self.resume_score < 1 or self.resume_score > 10:
            raise ValidationError({'resume_score': '评分必须在1-10分之间'})

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


class OverallInterviewEvaluation(models.Model):
    """面试整体评估（仅文本/数值）"""
    session = models.OneToOneField(
        InterviewSession,
        on_delete=models.CASCADE,
        related_name='overall_evaluation'
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='interview_evaluations'
    )
    overall_evaluation = models.TextField()  # 整体评估文本

    # 8项能力评分（1-10分，数值型）
    professional_knowledge = models.PositiveIntegerField(default=0)
    skill_match = models.PositiveIntegerField(default=0)
    language_expression = models.PositiveIntegerField(default=0)
    logical_thinking = models.PositiveIntegerField(default=0)
    stress_response = models.PositiveIntegerField(default=0)
    personality = models.PositiveIntegerField(default=0)  # 性格特质评分
    motivation = models.PositiveIntegerField(default=0)  # 求职动机评分
    value = models.PositiveIntegerField(default=0)  # 价值观匹配度评分

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Overall Evaluation for Session {self.session.id}"

    def clean(self):
        # 确保各项能力评分在1-10分之间
        score_fields = [
            'professional_knowledge', 'skill_match', 'language_expression',
            'logical_thinking', 'stress_response', 'personality',
            'motivation', 'value'
        ]
        for field in score_fields:
            value = getattr(self, field)
            if value < 1 or value > 10:
                raise ValidationError({field: '评分必须在1-10分之间'})

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)