from django.db import models
from django.db.models import JSONField

from user_manager.models import User


class InterviewScenario(models.Model):
    """
    面试场景模型，存储不同技术领域的岗位面试场景配置信息。
    """
    name = models.CharField(max_length=200)
    technology_field = models.CharField(max_length=200)
    description = models.TextField()
    is_real_time = models.BooleanField(default=False)  # 是否为实时面试
    media_config = JSONField(
        default=dict,
        help_text="媒体配置（分辨率、码率等）"
    )
    def __str__(self):
        return self.name

class InterviewSession(models.Model):
    """
    面试会话模型，记录一次完整的面试过程。
    """
    # 添加用户关联
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        default=1  # 设置默认用户ID（需确保该用户存在）
    )
    scenario = models.ForeignKey(InterviewScenario, on_delete=models.CASCADE)
    start_time = models.DateTimeField(auto_now_add=True)
    end_time = models.DateTimeField(null=True, blank=True)
    total_questions = models.PositiveIntegerField(default=0)
    is_finished = models.BooleanField(default=False)

    def __str__(self):
        return f"Interview Session {self.id} - {self.scenario.name}"

class InterviewQuestion(models.Model):
    """
    面试问题模型，存储每次提出的问题。
    """
    session = models.ForeignKey(InterviewSession, on_delete=models.CASCADE)
    question_text = models.TextField()
    question_number = models.PositiveIntegerField()
    asked_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Question {self.question_number} in Session {self.session.id}: {self.question_text}"