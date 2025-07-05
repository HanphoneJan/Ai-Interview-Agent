from rest_framework import serializers
from .models import FeedbackReport
from evaluation_system.models import OverallInterviewEvaluation


class FeedbackReportSerializer(serializers.ModelSerializer):
    evaluation = serializers.PrimaryKeyRelatedField(
        queryset=OverallInterviewEvaluation.objects.all()
    )

    class Meta:
        model = FeedbackReport
        fields = '__all__'