# interview_manager/utils.py
from .models import InterviewSession, InterviewQuestion
from channels.layers import get_channel_layer

async def get_current_question(session_id):
    session = InterviewSession.objects.get(id=session_id)
    question_count = InterviewQuestion.objects.filter(session=session).count()
    if question_count > 0:
        return InterviewQuestion.objects.filter(session=session).order_by('-question_number').first()
    return None

async def send_audio_to_client(session_id, audio_data):
    channel_layer = get_channel_layer()
    group_name = f"interview_session_{session_id}"
    await channel_layer.group_send(
        group_name,
        {
            "type": "send_audio",
            "audio_data": audio_data
        }
    )