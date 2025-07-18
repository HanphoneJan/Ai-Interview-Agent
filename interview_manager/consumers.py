from channels.generic.websocket import AsyncWebsocketConsumer
import json
import logging
import base64
import cv2
import tempfile
import os
import asyncio

from django.db import models
from django.utils import timezone
from asgiref.sync import sync_to_async

from evaluation_system.audio_recognize_engine import recognize
from evaluation_system.facial_engine import FacialExpressionAnalyzer
from evaluation_system.pipelines import live_evaluation_pipeline
from interview_manager.services import process_live_stream
from evaluation_system.evaluate_engine import spark_ai_engine
from evaluation_system.audio_generate_engine import synthesize
from interview_manager.utils import send_audio_to_client

from interview_manager.models import InterviewSession, InterviewQuestion
from evaluation_system.models import ResponseMetadata, ResponseAnalysis, AnswerEvaluation, OverallInterviewEvaluation

logger = logging.getLogger(__name__)


class LiveStreamConsumer(AsyncWebsocketConsumer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.session_id = None
        self.buffer = {}
        self.facial_analyzer = FacialExpressionAnalyzer()
        self.last_analyze_time = 0
        self.analysis_interval = 1
        self.history = []
        self.current_question = None

    async def connect(self):
        self.session_id = self.scope["url_route"]["kwargs"].get("session_id")
        if not self.session_id:
            await self.close(code=4000)
            return

        try:
            # 使用 sync_to_async 包装同步的数据库操作
            self.session = await sync_to_async(InterviewSession.objects.get)(id=self.session_id)
        except InterviewSession.DoesNotExist:
            await self.close(code=4001)
            return

        self.buffer[self.session_id] = {"audio": [], "video": []}

        await self.accept()
        logger.info(f"WebSocket连接已建立，会话ID: {self.session_id}")

        await self.generate_and_send_question()

    async def receive(self, text_data=None, bytes_data=None):
        try:
            if text_data:
                data = json.loads(text_data)
                message_type = data.get("type")

                if message_type == "media_chunk":
                    session_id = data["session_id"]
                    media_type = data["media_type"]
                    chunk_id = data.get("chunk_id")
                    is_last = data.get("is_last", False)

                    if "chunk" in data:
                        chunk = base64.b64decode(data["chunk"])
                    else:
                        logger.error(f"媒体块缺少数据字段，session_id: {session_id}")
                        return

                    self.buffer[session_id][media_type].append(chunk)

                    if is_last or len(self.buffer[session_id][media_type]) >= 5:
                        combined_data = b"".join(self.buffer[session_id][media_type])
                        self.buffer[session_id][media_type] = []

                        if media_type == "audio":
                            result = await recognize(combined_data)
                            if result["success"]:
                                speech_text = result["text"]
                                logger.info(f"语音识别结果: {speech_text[:50]}...")

                                self.history.append({"role": "user", "content": speech_text})

                                feedback = await live_evaluation_pipeline(
                                    session_id, combined_data, media_type
                                )
                                await self.send(text_data=json.dumps({
                                    "feedback": feedback,
                                    "speech_text": speech_text
                                }))

                                # 使用 sync_to_async 包装同步的数据库操作
                                current_question = await sync_to_async(InterviewQuestion.objects.filter(session=self.session).latest)('asked_at')
                                metadata = await sync_to_async(ResponseMetadata.objects.create)(
                                    question=current_question,
                                    audio_duration=None  # 这里需要根据实际情况计算音频时长
                                )
                                analysis = await sync_to_async(ResponseAnalysis.objects.create)(
                                    metadata=metadata,
                                    speech_text=speech_text,
                                    facial_expression="",  # 这里需要根据实际情况填充表情分析结果
                                    body_language=""  # 这里需要根据实际情况填充肢体语言分析结果
                                )

                                await self.evaluate_and_generate_question(speech_text, analysis)

                        elif media_type == "video":
                            analysis = await self._process_video(combined_data)

                            if analysis["success"]:
                                logger.info(f"视频表情分析结果: 共分析{len(analysis['data'])}帧")

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

                        await process_live_stream(session_id, combined_data, media_type)

                elif message_type == "control":
                    control_action = data.get("action", "未知操作")
                    logger.info(f"收到控制信令: {control_action}")

            elif bytes_data:
                logger.warning("收到原始二进制数据，建议使用Base64编码通过text_data发送")

        except json.JSONDecodeError as e:
            logger.error(f"JSON解析失败: {str(e)}")
        except Exception as e:
            logger.error(f"接收WebSocket数据出错: {str(e)}", exc_info=True)

    async def disconnect(self, close_code):
        logger.info(f"WebSocket连接已断开，会话ID: {self.session_id}，关闭代码: {close_code}")
        if self.session_id in self.buffer:
            del self.buffer[self.session_id]

    async def _process_video(self, video_bytes):
        try:
            with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as f:
                f.write(video_bytes)
                temp_video_path = f.name

            cap = cv2.VideoCapture(temp_video_path)
            if not cap.isOpened():
                raise Exception("无法解析视频数据，请检查格式是否正确")

            fps = cap.get(cv2.CAP_PROP_FPS)
            if fps <= 0:
                fps = 30
            frame_interval = int(fps * self.analysis_interval)
            frame_count = 0
            emotion_results = []

            while cap.isOpened():
                ret, frame = cap.read()
                if not ret:
                    break

                if frame_count % frame_interval == 0:
                    frame_result = await self._analyze_frame(frame)
                    emotion_results.append({
                        "frame_index": frame_count,
                        "timestamp": frame_count / fps,
                        "analysis": frame_result
                    })

                frame_count += 1

            cap.release()
            os.unlink(temp_video_path)

            return {
                "success": True,
                "data": emotion_results,
                "message": f"成功处理视频，共分析{len(emotion_results)}帧"
            }

        except Exception as e:
            logger.error(f"视频处理失败: {str(e)}", exc_info=True)
            if 'temp_video_path' in locals() and os.path.exists(temp_video_path):
                os.unlink(temp_video_path)
            return {
                "success": False,
                "error": f"视频处理失败: {str(e)}"
            }

    async def _analyze_frame(self, frame):
        _, img_encoded = cv2.imencode('.jpg', frame)
        if not _:
            return {"success": False, "error": "帧编码失败"}

        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as f:
            f.write(img_encoded.tobytes())
            temp_img_path = f.name

        loop = asyncio.get_event_loop()
        analyze_result = await loop.run_in_executor(
            None,
            self.facial_analyzer.analyze_by_file,
            temp_img_path
        )

        os.unlink(temp_img_path)
        return analyze_result

    async def generate_and_send_question(self):
        # 使用 sync_to_async 包装同步的数据库操作
        question_count = await sync_to_async(InterviewQuestion.objects.filter(session=self.session).count)()

        question_query = "请生成一个面试问题"
        response = spark_ai_engine.generate_response(question_query, self.history)
        if response["success"]:
            self.current_question = response["content"]
            self.history.append({"role": "assistant", "content": self.current_question})

            # 使用 sync_to_async 包装同步的数据库操作
            question = await sync_to_async(InterviewQuestion.objects.create)(
                session=self.session,
                question_text=self.current_question,
                question_number=question_count + 1
            )

            await self.send(text_data=json.dumps({
                "question": self.current_question
            }))

            audio_result = await synthesize(self.current_question)
            if audio_result["success"]:
                audio_data = audio_result["audio_data"]
                await send_audio_to_client(self.session_id, audio_data)

    async def evaluate_and_generate_question(self, speech_text, analysis):
        evaluation_query = f"请评估这个面试回答：{speech_text}"
        evaluation_response = spark_ai_engine.generate_response(evaluation_query, self.history)
        if evaluation_response["success"]:
            evaluation_text = evaluation_response["content"]
            score = 0  # 这里需要根据实际情况计算评分

            # 使用 sync_to_async 包装同步的数据库操作
            current_question = await sync_to_async(InterviewQuestion.objects.filter(session=self.session).latest)('asked_at')
            await sync_to_async(AnswerEvaluation.objects.create)(
                question=current_question,
                analysis=analysis,
                evaluation_text=evaluation_text,
                score=score
            )

            new_question_query = "请生成一个新的面试问题"
            new_question_response = spark_ai_engine.generate_response(new_question_query, self.history)
            if new_question_response["success"]:
                new_question_text = new_question_response["content"]
                self.current_question = new_question_text
                self.history.append({"role": "assistant", "content": new_question_text})

                # 使用 sync_to_async 包装同步的数据库操作
                question_count = await sync_to_async(InterviewQuestion.objects.filter(session=self.session).count)()
                await sync_to_async(InterviewQuestion.objects.create)(
                    session=self.session,
                    question_text=new_question_text,
                    question_number=question_count + 1
                )

                await self.send(text_data=json.dumps({
                    "question": new_question_text
                }))

                audio_result = await synthesize(new_question_text)
                if audio_result["success"]:
                    audio_data = audio_result["audio_data"]
                    await send_audio_to_client(self.session_id, audio_data)
            else:
                await self.send(text_data=json.dumps({
                    "error": new_question_response["error"]
                }))
        else:
            await self.send(text_data=json.dumps({
                "error": evaluation_response["error"]
            }))