import base64

from channels.generic.websocket import AsyncWebsocketConsumer
import json
import logging
from asgiref.sync import sync_to_async
from .models import InterviewSession
from .services import process_live_media, generate_initial_question, process_image_data

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

    async def receive(self, text_data=None, bytes_data=None):
        """处理接收到的消息"""
        if text_data:
            try:
                data = json.loads(text_data)
                message_type = data.get("type")

                if message_type.lower() == "audio":
                    # 处理音频数据
                    result = await process_live_media(
                        self.session_id,
                        data.get("data"),
                        data.get("timestamp"),
                        self.scope["user"].id if self.scope.get("user") else None,
                        media_type="audio"
                    )
                    await self.send(text_data=json.dumps({
                        "type": "audio_ack",
                        "success": result["success"],
                        "message": result.get("message", ""),
                        "timestamp": data.get("timestamp")
                    }))

                elif message_type.lower() == "video":
                    # 处理视频数据
                    result = await process_live_media(
                        self.session_id,
                        data.get("data"),
                        data.get("timestamp"),
                        self.scope["user"].id if self.scope.get("user") else None,
                        media_type="video"
                    )
                    await self.send(text_data=json.dumps({
                        "type": "video_ack",
                        "success": result["success"],
                        "message": result.get("message", ""),
                        "timestamp": data.get("timestamp")
                    }))

                elif message_type.lower() == "image":
                    # 处理图片数据
                    result = await process_image_data(
                        self.session_id,
                        data.get("data"),
                        data.get("timestamp")
                    )
                    await self.send(text_data=json.dumps({
                        "type": "image_ack",
                        "success": result["success"],
                        "message": result.get("message", ""),
                        "timestamp": data.get("timestamp"),
                        "analysis": result.get("data", {})
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
                    await self.send(text_data=json.dumps({
                        "type": "error",
                        "message": f"未知消息类型: {message_type}"
                    }))

            except json.JSONDecodeError as e:
                logger.error(f"JSON解析失败: {str(e)}")
                await self.send(text_data=json.dumps({
                    "error": "无效的JSON格式",
                    "type": "parse_error"
                }))
        elif bytes_data:
            logger.warning("收到原始二进制数据，应使用base64编码")
            await self.send(text_data=json.dumps({
                "type": "error",
                "message": "请使用base64编码的文本数据"
            }))

    async def disconnect(self, close_code):
        """处理WebSocket连接断开"""
        logger.info(f"WebSocket连接断开，会话ID: {self.session_id}，关闭代码: {close_code}")

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