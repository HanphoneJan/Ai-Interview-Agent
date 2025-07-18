from channels.generic.websocket import AsyncWebsocketConsumer
import json
import logging
import base64
from asgiref.sync import sync_to_async
from .models import InterviewSession
from .services import process_live_media

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

        await self.accept()
        logger.info(f"WebSocket连接建立，会话ID: {self.session_id}")

    async def receive(self, text_data=None, bytes_data=None):
        """处理接收到的消息"""
        if text_data:
            try:
                data = json.loads(text_data)
                message_type = data.get("type")

                if message_type == "media":
                    # 处理媒体数据
                    result = await process_live_media(
                        self.session_id,
                        data.get("data"),
                        data.get("timestamp"),
                        data.get("userId")
                    )
                    if not result["success"]:
                        await self.send(text_data=json.dumps({
                            "error": result["error"],
                            "type": "media_processing_error"
                        }))
                elif message_type == "control":
                    # 处理控制消息
                    control_action = data.get("action")
                    logger.info(f"收到控制消息: {control_action}")
                elif message_type == "connect":
                    # 处理连接确认消息
                    logger.info("收到连接确认消息")
                    await self.send(text_data=json.dumps({
                        "type": "connect_ack",
                        "message": "连接已建立"
                    }))
                else:
                    logger.warning(f"未知消息类型: {message_type}")

            except json.JSONDecodeError as e:
                logger.error(f"JSON解析失败: {str(e)}")
                await self.send(text_data=json.dumps({
                    "error": "无效的JSON格式",
                    "type": "parse_error"
                }))
        elif bytes_data:
            logger.warning("收到原始二进制数据，应使用base64编码")

    async def disconnect(self, close_code):
        """处理WebSocket连接断开"""
        logger.info(f"WebSocket连接断开，会话ID: {self.session_id}，关闭代码: {close_code}")