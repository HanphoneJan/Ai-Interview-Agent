# multimodal_data/models.py
from django.db import models
from interview_scenarios.models import InterviewQuestion

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

    def get_total_duration(self):
        """计算音频和视频其中的更长的时长"""
        total = None
        if self.audio_duration and self.video_duration:
            if self.audio_duration > self.video_duration:
                total = self.audio_duration
            else:
                total = self.video_duration
        elif self.audio_duration:
            total = self.audio_duration
        elif self.video_duration:
            total = self.video_duration
        return total

class LiveStreamChunk(models.Model):
    """存储实时媒体流数据块"""
    session_id = models.CharField(max_length=255)
    media_type = models.CharField(max_length=10, choices=[('audio', 'Audio'), ('video', 'Video')])
    chunk_data = models.BinaryField()
    received_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Chunk for session {self.session_id} - {self.media_type}"