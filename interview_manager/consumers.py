# interview_manager/consumers.py
import json
import logging
from channels.generic.websocket import AsyncWebsocketConsumer
from .services import get_media_servers_config

logger = logging.getLogger(__name__)


class InterviewConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        """处理WebSocket连接"""
        self.session_id = self.scope["url_route"]["kwargs"]["session_id"]
        self.group_name = f"interview_{self.session_id}"

        # 验证会话合法性
        if not await self.validate_session():
            await self.close()
            return

        # 加入会话组
        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name
        )

        await self.accept()

        # 发送媒体服务器配置给前端
        media_config = get_media_servers_config(self.session_id)
        await self.send(text_data=json.dumps({
            "type": "media_config",
            "config": media_config
        }))

    async def validate_session(self):
        """验证会话是否存在且属于当前用户"""
        # 实现会话验证逻辑
        return True

    async def receive(self, text_data):
        """处理接收的信令消息"""
        data = json.loads(text_data)
        message_type = data.get("type")

        if message_type == "offer":
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
            pass
        # 处理其他信令...

    async def send_offer(self, event):
        """向对端发送SDP Offer"""
        await self.send(text_data=json.dumps({
            "type": "offer",
            "offer": event["offer"],
            "sender": event["sender"]
        }))