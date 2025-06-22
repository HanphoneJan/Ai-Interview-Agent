from rest_framework import serializers
from .models import ResponseAnalysis, AnswerEvaluation, OverallInterviewEvaluation
from multimodal_data.models import ResponseMetadata
from interview_scenarios.models import InterviewQuestion, InterviewSession
from accounts.models import User


class ResponseAnalysisSerializer(serializers.ModelSerializer):
    metadata = serializers.PrimaryKeyRelatedField(
        queryset=ResponseMetadata.objects.all()
    )

    class Meta:
        model = ResponseAnalysis
        fields = '__all__'


class AnswerEvaluationSerializer(serializers.ModelSerializer):
    question = serializers.PrimaryKeyRelatedField(
        queryset=InterviewQuestion.objects.all()
    )
    analysis = serializers.PrimaryKeyRelatedField(
        queryset=ResponseAnalysis.objects.all()
    )
    user = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all()
    )

    class Meta:
        model = AnswerEvaluation
        fields = '__all__'


class OverallInterviewEvaluationSerializer(serializers.ModelSerializer):
    session = serializers.PrimaryKeyRelatedField(
        queryset=InterviewSession.objects.all()
    )
    user = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all()
    )

    class Meta:
        model = OverallInterviewEvaluation
        fields = '__all__'