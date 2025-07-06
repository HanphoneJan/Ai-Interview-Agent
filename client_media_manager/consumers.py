# client_media_manager/consumers.py
from channels.generic.websocket import AsyncWebsocketConsumer
import json
import logging
from .services import process_live_stream

logger = logging.getLogger(__name__)

class LiveStreamConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        await self.accept()
        self.session_id = self.scope["url_route"]["kwargs"]["session_id"]
        self.group_name = f"session_{self.session_id}"
        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name
        )
        logger.info(f"WebSocket连接已建立，会话ID: {self.session_id}")

    async def receive(self, text_data):
        """接收前端发送的媒体数据（二进制或JSON）"""
        try:
            data = json.loads(text_data)
            message_type = data.get("type")

            if message_type == "media_chunk":
                # 处理实时媒体数据块
                await process_live_stream(
                    session_id=data["session_id"],
                    chunk=data["chunk"],
                    media_type=data["media_type"]
                )
            elif message_type == "control":
                # 处理控制信令
                pass
            elif message_type == "offer":
                # 处理SDP Offer
                await self.channel_layer.group_send(
                    self.group_name,
                    {
                        "type": "send_offer",
                        "offer": data["offer"],
                        "sender": self.channel_name
                    }
                )
            elif message_type == "answer":
                # 处理SDP Answer
                await self.channel_layer.group_send(
                    self.group_name,
                    {
                        "type": "send_answer",
                        "answer": data["answer"],
                        "sender": self.channel_name
                    }
                )
            elif message_type == "candidate":
                # 处理ICE Candidate
                await self.channel_layer.group_send(
                    self.group_name,
                    {
                        "type": "send_candidate",
                        "candidate": data["candidate"],
                        "sender": self.channel_name
                    }
                )
        except Exception as e:
            logger.error(f"接收WebSocket数据出错: {e}")

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.group_name,
            self.channel_name
        )
        logger.info(f"WebSocket连接已断开，会话ID: {self.session_id}，关闭代码: {close_code}")

    async def send_offer(self, event):
        """向对端发送SDP Offer"""
        await self.send(text_data=json.dumps({
            "type": "offer",
            "offer": event["offer"],
            "sender": event["sender"]
        }))

    async def send_answer(self, event):
        """向对端发送SDP Answer"""
        await self.send(text_data=json.dumps({
            "type": "answer",
            "answer": event["answer"],
            "sender": event["sender"]
        }))

    async def send_candidate(self, event):
        """向对端发送ICE Candidate"""
        await self.send(text_data=json.dumps({
            "type": "candidate",
            "candidate": event["candidate"],
            "sender": event["sender"]
        }))