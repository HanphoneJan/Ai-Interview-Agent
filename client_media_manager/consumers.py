from channels.generic.websocket import AsyncWebsocketConsumer
import json
import logging
import base64

from evaluation_system.audio_recognize_engines import recognize
from evaluation_system.video_analyze_engines import analyze_video  # 新增视频分析引擎导入
from evaluation_system.pipelines import live_evaluation_pipeline
from .services import process_live_stream

logger = logging.getLogger(__name__)


class LiveStreamConsumer(AsyncWebsocketConsumer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.session_id = None
        self.buffer = {}  # 存储媒体块的缓冲区

    async def connect(self):
        self.session_id = self.scope["url_route"]["kwargs"].get("session_id")
        if not self.session_id:
            await self.close(code=4000)
            return

        # 初始化会话缓冲区
        self.buffer[self.session_id] = {"audio": [], "video": []}

        await self.accept()
        logger.info(f"WebSocket连接已建立，会话ID: {self.session_id}")

    async def receive(self, text_data=None, bytes_data=None):
        try:
            if text_data:
                data = json.loads(text_data)
                message_type = data.get("type")

                if message_type == "media_chunk":
                    session_id = data["session_id"]
                    media_type = data["media_type"]
                    chunk_id = data.get("chunk_id")  # 媒体块ID，用于重组
                    is_last = data.get("is_last", False)  # 是否是最后一个块

                    # 处理Base64编码的媒体数据
                    if "chunk" in data:
                        chunk = base64.b64decode(data["chunk"])
                    else:
                        logger.error(f"媒体块缺少数据字段，session_id: {session_id}")
                        return

                    # 存储媒体块到缓冲区
                    self.buffer[session_id][media_type].append(chunk)

                    # 如果是最后一个块或达到一定大小，处理数据
                    if is_last or len(self.buffer[session_id][media_type]) >= 5:
                        combined_data = b"".join(self.buffer[session_id][media_type])
                        self.buffer[session_id][media_type] = []  # 清空缓冲区

                        # 处理不同类型的媒体数据
                        if media_type == "audio":
                            # 语音数据处理
                            result = await recognize(combined_data)
                            if result["success"]:
                                speech_text = result["text"]
                                logger.info(f"语音识别结果: {speech_text[:50]}...")

                                # 调用实时评估流水线
                                feedback = await live_evaluation_pipeline(
                                    session_id, combined_data, media_type
                                )
                                await self.send(text_data=json.dumps({
                                    "feedback": feedback,
                                    "speech_text": speech_text
                                }))
                        elif media_type == "video":
                            # 视频数据处理
                            analysis = await analyze_video(combined_data)
                            if analysis["success"]:
                                logger.info(f"视频分析结果: {analysis['data'][:50]}...")

                                # 调用实时评估流水线
                                feedback = await live_evaluation_pipeline(
                                    session_id, combined_data, media_type
                                )
                                await self.send(text_data=json.dumps({
                                    "feedback": feedback,
                                    "video_analysis": analysis["data"]
                                }))

                        # 通用媒体流处理
                        await process_live_stream(session_id, combined_data, media_type)

                elif message_type == "control":
                    control_action = data.get("action", "未知操作")
                    logger.info(f"收到控制信令: {control_action}")
                    # 处理控制信令，如开始/停止录制等

            elif bytes_data:
                # 处理原始二进制数据
                logger.warning("收到原始二进制数据，建议使用Base64编码通过text_data发送")
                # 可以添加二进制数据处理逻辑

        except json.JSONDecodeError as e:
            logger.error(f"JSON解析失败: {str(e)}")
        except Exception as e:
            logger.error(f"接收WebSocket数据出错: {str(e)}", exc_info=True)

    async def disconnect(self, close_code):
        logger.info(f"WebSocket连接已断开，会话ID: {self.session_id}，关闭代码: {close_code}")
        # 清理会话缓冲区
        if self.session_id in self.buffer:
            del self.buffer[self.session_id]