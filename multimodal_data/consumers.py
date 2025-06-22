# multimodal_data/consumers.py
from channels.generic.websocket import AsyncWebsocketConsumer
import json
from .services import process_live_stream

class LiveStreamConsumer(AsyncWebsocketConsumer):
    async def receive(self, text_data):
        """接收前端发送的媒体数据（二进制或JSON）"""
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