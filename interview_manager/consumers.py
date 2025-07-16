from channels.generic.websocket import AsyncWebsocketConsumer
import json
import logging
import base64
import cv2
import tempfile
import os
import asyncio

from evaluation_system.audio_recognize_engine import recognize
from evaluation_system.facial_engine import FacialExpressionAnalyzer  # 导入表情分析引擎
from evaluation_system.pipelines import live_evaluation_pipeline
from interview_manager.services import process_live_stream

logger = logging.getLogger(__name__)


class LiveStreamConsumer(AsyncWebsocketConsumer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.session_id = None
        self.buffer = {}  # 存储媒体块的缓冲区
        self.facial_analyzer = FacialExpressionAnalyzer()  # 初始化表情分析引擎
        self.last_analyze_time = 0  # 上次分析时间，用于定时控制
        self.analysis_interval = 1  # 表情分析时间间隔（秒）

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
                            # 视频数据处理：定时转图片并分析表情
                            analysis = await self._process_video(combined_data)

                            if analysis["success"]:
                                logger.info(f"视频表情分析结果: 共分析{len(analysis['data'])}帧")

                                # 调用实时评估流水线
                                feedback = await live_evaluation_pipeline(
                                    session_id, combined_data, media_type
                                )
                                await self.send(text_data=json.dumps({
                                    "feedback": feedback,
                                    "video_analysis": analysis["data"]
                                }))
                            else:
                                await self.send(text_data=json.dumps({
                                    "error": analysis["error"],
                                    "media_type": "video"
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

    async def _process_video(self, video_bytes):
        """处理视频数据，定时抽取帧并分析表情"""
        try:
            # 创建临时文件存储视频数据（OpenCV需要文件路径读取）
            with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as f:
                f.write(video_bytes)
                temp_video_path = f.name

            # 打开视频文件
            cap = cv2.VideoCapture(temp_video_path)
            if not cap.isOpened():
                raise Exception("无法解析视频数据，请检查格式是否正确")

            # 获取视频帧率，用于控制抽帧频率
            fps = cap.get(cv2.CAP_PROP_FPS)
            if fps <= 0:
                fps = 30  # 默认为30fps
            frame_interval = int(fps * self.analysis_interval)  # 每隔指定秒数抽一帧
            frame_count = 0
            emotion_results = []

            # 循环读取视频帧
            while cap.isOpened():
                ret, frame = cap.read()
                if not ret:
                    break  # 视频读取完毕

                # 按时间间隔抽帧
                if frame_count % frame_interval == 0:
                    # 处理当前帧：转为JPEG并分析
                    frame_result = await self._analyze_frame(frame)
                    emotion_results.append({
                        "frame_index": frame_count,
                        "timestamp": frame_count / fps,  # 计算时间戳（秒）
                        "analysis": frame_result
                    })

                frame_count += 1

            # 释放资源
            cap.release()
            os.unlink(temp_video_path)  # 删除临时视频文件

            return {
                "success": True,
                "data": emotion_results,
                "message": f"成功处理视频，共分析{len(emotion_results)}帧"
            }

        except Exception as e:
            logger.error(f"视频处理失败: {str(e)}", exc_info=True)
            # 清理临时文件
            if 'temp_video_path' in locals() and os.path.exists(temp_video_path):
                os.unlink(temp_video_path)
            return {
                "success": False,
                "error": f"视频处理失败: {str(e)}"
            }

    async def _analyze_frame(self, frame):
        """分析单帧图片中的表情"""
        # 将OpenCV帧转为JPEG格式
        _, img_encoded = cv2.imencode('.jpg', frame)
        if not _:
            return {"success": False, "error": "帧编码失败"}

        # 创建临时图片文件
        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as f:
            f.write(img_encoded.tobytes())
            temp_img_path = f.name

        # 在线程池中执行同步的表情分析方法（避免阻塞事件循环）
        loop = asyncio.get_event_loop()
        analyze_result = await loop.run_in_executor(
            None,
            self.facial_analyzer.analyze_by_file,
            temp_img_path
        )

        # 清理临时文件
        os.unlink(temp_img_path)
        return analyze_result