from channels.generic.websocket import AsyncWebsocketConsumer
import json
import logging
from .services import process_live_stream

logger = logging.getLogger(__name__)

class LiveStreamConsumer(AsyncWebsocketConsumer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.session_id = None  # 仅保留会话ID属性，无需group相关属性

    async def connect(self):
        # 从 scope 中获取 session_id
        self.session_id = self.scope["url_route"]["kwargs"].get("session_id")
        logger.info(f"接收到 WebSocket 连接请求，session_id: {self.session_id}")

        if not self.session_id:
            logger.error("未提供 session_id，关闭连接")
            await self.close(code=4000)
            return

        # 接受连接（注意：原代码中调用了两次accept()，这里修正为一次）
        await self.accept()
        logger.info(f"WebSocket 连接已建立，session_id: {self.session_id}")

    async def receive(self, text_data=None, bytes_data=None):
        """接收前端发送的媒体数据（二进制或JSON），增加详细调试日志"""
        try:
            # 记录接收数据的基本信息（区分文本/二进制类型）
            if text_data:
                logger.debug(
                    f"接收文本数据 | session_id: {self.session_id} | 数据长度: {len(text_data)} 字符"
                )
                try:
                    # 解析JSON前记录原始数据片段（避免敏感信息，只取前100字符）
                    raw_data_snippet = text_data[:100] + ("..." if len(text_data) > 100 else "")
                    logger.debug(f"原始文本数据片段: {raw_data_snippet}")

                    data = json.loads(text_data)
                    logger.debug(f"JSON解析成功 | 数据结构: {list(data.keys())}")  # 仅记录键名，不暴露值

                    message_type = data.get("type")
                    logger.debug(f"消息类型: {message_type} | session_id: {data.get('session_id')}")

                    if message_type == "media_chunk":
                        # 记录媒体块的关键元信息（不记录完整二进制内容）
                        chunk_info = {
                            "session_id": data.get("session_id"),
                            "media_type": data.get("media_type"),
                            "chunk_length": len(data.get("chunk", ""))  # 记录chunk长度而非内容
                        }
                        logger.debug(f"处理媒体数据块 | {chunk_info}")

                        # 处理实时媒体数据块
                        await process_live_stream(
                            session_id=data["session_id"],
                            chunk=data["chunk"],
                            media_type=data["media_type"]
                        )
                        logger.debug(f"媒体数据块处理完成 | session_id: {data['session_id']}")

                    elif message_type == "control":
                        control_action = data.get("action", "未知操作")
                        logger.debug(f"处理控制信令 | 操作: {control_action}")
                        # 可添加控制信令的响应逻辑

                    else:
                        logger.debug(f"收到未知消息类型: {message_type}")

                except json.JSONDecodeError as e:
                    # 单独捕获JSON解析错误，方便定位格式问题
                    logger.error(f"JSON解析失败 | 原始数据: {text_data[:200]} | 错误: {str(e)}")
                except KeyError as e:
                    # 捕获关键参数缺失错误
                    logger.error(f"数据缺少必要字段: {str(e)} | 数据: {list(data.keys())}")

            elif bytes_data:
                # 记录二进制数据的基本信息（长度）
                logger.debug(f"收到二进制数据 | 长度: {len(bytes_data)} 字节")
                # 如需处理二进制数据，可在此添加逻辑

            else:
                logger.debug("收到空数据，未处理")

        except Exception as e:
            # 捕获其他未预料的错误
            logger.error(f"接收WebSocket数据出错: {str(e)}", exc_info=True)  # exc_info=True 打印完整堆栈

    async def disconnect(self, close_code):
        logger.info(f"WebSocket连接已断开，会话ID: {self.session_id}，关闭代码: {close_code}")
