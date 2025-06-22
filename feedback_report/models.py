from django.db import models
from evaluation_system.models import OverallInterviewEvaluation

class FeedbackReport(models.Model):
    """
    反馈报告模型，存储可视化评测反馈报告的元信息。
    """
    evaluation = models.OneToOneField(OverallInterviewEvaluation, on_delete=models.CASCADE)
    report_file = models.FileField(upload_to='feedback_reports/')
    generated_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Feedback Report for Interview Session {self.evaluation.session.id}"