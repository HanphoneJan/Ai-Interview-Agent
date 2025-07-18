import base64

from channels.generic.websocket import AsyncWebsocketConsumer
import json
import logging
from asgiref.sync import sync_to_async
from .models import InterviewSession
from .services import process_live_media, generate_initial_question

logger = logging.getLogger(__name__)


class LiveStreamConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        """处理WebSocket连接建立"""
        self.session_id = self.scope["url_route"]["kwargs"].get("session_id")
        if not self.session_id:
            await self.close(code=4000)
            return

        try:
            self.session = await sync_to_async(InterviewSession.objects.get)(id=self.session_id)
        except InterviewSession.DoesNotExist:
            await self.close(code=4001)
            return

        # 先加入组，再接受连接
        await self.channel_layer.group_add(
            f"interview_session_{self.session_id}",
            self.channel_name
        )

        await self.accept()
        logger.info(f"WebSocket连接建立，会话ID: {self.session_id}")

        # 生成初始问题
        await generate_initial_question(self.session)

    # 修改消息处理函数名以匹配utils.py中的类型
    async def send_audio_and_text(self, event):
        try:
            # 将音频数据转为base64编码
            audio_data = event["audio_data"]
            if isinstance(audio_data, bytes):
                audio_data = base64.b64encode(audio_data).decode('utf-8')

            await self.send(text_data=json.dumps({
                "type": "question",
                "audio_data": audio_data,  # 现在是base64字符串
                "question_text": event["question_text"]
            }))
            logger.info(f"已发送问题和音频数据，问题长度: {len(event['question_text'])}")
        except Exception as e:
            logger.error(f"发送音频和文本失败: {str(e)}", exc_info=True)