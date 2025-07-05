from rest_framework import serializers
from .models import InterviewScenario, InterviewSession, InterviewQuestion


class InterviewScenarioSerializer(serializers.ModelSerializer):
    class Meta:
        model = InterviewScenario
        fields = '__all__'


class InterviewSessionSerializer(serializers.ModelSerializer):
    user = serializers.PrimaryKeyRelatedField(read_only=True)  # 只读字段
    scenario = InterviewScenarioSerializer(read_only=True)
    scenario_id = serializers.IntegerField(write_only=True)

    class Meta:
        model = InterviewSession
        fields = '__all__'


class InterviewQuestionSerializer(serializers.ModelSerializer):
    session = InterviewSessionSerializer(read_only=True)
    session_id = serializers.IntegerField(write_only=True)

    class Meta:
        model = InterviewQuestion
        fields = '__all__'