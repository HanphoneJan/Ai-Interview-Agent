# evaluation_system/serializers.py
from rest_framework import serializers
from .models import (
    ResponseMetadata,
    ResponseAnalysis,
    AnswerEvaluation,
    ResumeEvaluation,
    OverallInterviewEvaluation
)
from interview_manager.models import InterviewQuestion, InterviewSession
from user_manager.models import User

class ResponseMetadataSerializer(serializers.ModelSerializer):
    question = serializers.PrimaryKeyRelatedField(
        queryset=InterviewQuestion.objects.all()
    )

    class Meta:
        model = ResponseMetadata
        fields = '__all__'

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

    class Meta:
        model = AnswerEvaluation
        fields = '__all__'

class ResumeEvaluationSerializer(serializers.ModelSerializer):
    user = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all()
    )

    class Meta:
        model = ResumeEvaluation
        fields = '__all__'

    def validate_resume_score(self, value):
        if float(value) < 0 or float(value) > 10:
            raise serializers.ValidationError('评分必须在0-10分之间')
        return value

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

    def validate(self, data):
        # 确保各项能力评分在1-10分之间
        score_fields = [
            'professional_knowledge', 'skill_match', 'language_expression',
            'logical_thinking', 'stress_response', 'personality',
            'motivation', 'value'
        ]
        for field in score_fields:
            value = data.get(field)
            if value is not None and (float(value) < 1 or float(value)> 10):
                raise serializers.ValidationError({field: '评分必须在0-10分之间'})
        return data