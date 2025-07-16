from django.core.exceptions import ValidationError
from django.db import models
from interview_manager.models import InterviewQuestion, InterviewSession
from user_manager.models import User

class ResponseMetadata(models.Model):
    """存储回答的元数据（不存储实际音视频文件）"""
    question = models.ForeignKey(
        InterviewQuestion,
        on_delete=models.CASCADE,
        related_name='response_metadata'
    )
    audio_duration = models.DurationField(null=True, blank=True)  # 音频时长
    video_duration = models.DurationField(null=True, blank=True)  # 视频时长
    upload_timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Response Meta for Q{self.question.question_number}"


class LiveStreamChunk(models.Model):
    """存储实时媒体流数据块"""
    session_id = models.CharField(max_length=255)
    media_type = models.CharField(max_length=10, choices=[('audio', 'Audio'), ('video', 'Video')])
    chunk_data = models.BinaryField()
    received_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Chunk for session {self.session_id} - {self.media_type}"

class ResponseAnalysis(models.Model):
    """存储多模态分析结果（语音文本、表情特征等）"""
    metadata = models.OneToOneField(
        ResponseMetadata,
        on_delete=models.CASCADE,
        related_name='analysis'
    )
    speech_text = models.TextField()  # 语音转文字结果
    facial_expression = models.TextField()  # 表情分析结果
    body_language = models.TextField()  # 肢体语言分析结果
    analysis_timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Analysis for Q{self.metadata.question.question_number}"

class AnswerEvaluation(models.Model):
    """单问题回答评估"""
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
    evaluation_text = models.TextField()  # 评估文本
    score = models.FloatField(default=0)  # 单项评分
    evaluated_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Evaluation for Q{self.question.question_number}"

class OverallInterviewEvaluation(models.Model):
    """面试整体评估"""
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

    # 各项能力评分（1-10分）
    professional_knowledge = models.PositiveIntegerField(default=0)
    skill_match = models.PositiveIntegerField(default=0)
    language_expression = models.PositiveIntegerField(default=0)
    logical_thinking = models.PositiveIntegerField(default=0)
    stress_response = models.PositiveIntegerField(default=0)
    # 新增评分项
    personality = models.PositiveIntegerField(default=0)  # 性格特质评分
    motivation = models.PositiveIntegerField(default=0)  # 求职动机评分
    value = models.PositiveIntegerField(default=0)  # 价值观匹配度评分
    resume = models.PositiveIntegerField(default=0)  # 简历真实性与匹配度评分

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Overall Evaluation for Session {self.session.id}"

    def clean(self):
        # 确保各项能力评分在1-10分之间（包含新增字段）
        score_fields = [
            'professional_knowledge', 'skill_match', 'language_expression',
            'logical_thinking', 'stress_response', 'personality',
            'motivation', 'value', 'resume'
        ]
        for field in score_fields:
            value = getattr(self, field)
            if value < 1 or value > 10:
                raise ValidationError({field: '评分必须在1-10分之间'})

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)