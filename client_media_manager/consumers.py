# client_media_manager/consumers.py
from channels.generic.websocket import AsyncWebsocketConsumer
import json
import logging
from .services import process_live_stream

logger = logging.getLogger(__name__)

class LiveStreamConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        await self.accept()
        logger.info(f"WebSocket连接已建立，会话ID: {self.scope['url_route']['kwargs']['session_id']}")

    async def receive(self, text_data):
        """接收前端发送的媒体数据（二进制或JSON）"""
        try:
            data = json.loads(text_data)
            if data["type"] == "media_chunk":
                # 处理实时媒体数据块
                await process_live_stream(
                    session_id=data["session_id"],
                    chunk=data["chunk"],
                    media_type=data["media_type"]
                )
            elif data["type"] == "control":
                # 处理控制信令
                pass
        except Exception as e:
            logger.error(f"接收WebSocket数据出错: {e}")

    async def disconnect(self, close_code):
        logger.info(f"WebSocket连接已断开，会话ID: {self.scope['url_route']['kwargs']['session_id']}，关闭代码: {close_code}")