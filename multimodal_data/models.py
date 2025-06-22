from django.db import models
from interview_scenarios.models import InterviewQuestion
from django.utils import timezone


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