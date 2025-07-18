# interview_manager/utils.py
import base64
import logging

from .models import InterviewSession, InterviewQuestion
from channels.layers import get_channel_layer

logger = logging.getLogger(__name__)
async def send_audio_and_text_to_client(session_id, audio_data, question_text):
    try:
        channel_layer = get_channel_layer()
        # 确保audio_data是bytes类型
        if isinstance(audio_data, str):
            audio_data = base64.b64decode(audio_data)

        await channel_layer.group_send(
            f"interview_session_{session_id}",
            {
                "type": "send_audio_and_text",
                "audio_data": audio_data,  # 发送bytes数据
                "question_text": question_text
            }
        )
        logger.info(f"已安排发送音频和文本到会话 {session_id}")
    except Exception as e:
        logger.error(f"安排发送音频和文本失败: {str(e)}", exc_info=True)


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
