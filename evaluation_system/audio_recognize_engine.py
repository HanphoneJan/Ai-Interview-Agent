import asyncio
import base64
import hashlib
import hmac
import json
import logging
import math
import os
import time
from datetime import datetime
from urllib.parse import urlencode
from time import mktime
from wsgiref.handlers import format_date_time

import aiohttp
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()
logger = logging.getLogger(__name__)

# 状态标识
STATUS_FIRST_FRAME = 0  # 第一帧的标识
STATUS_CONTINUE_FRAME = 1  # 中间帧标识
STATUS_LAST_FRAME = 2  # 最后一帧的标识


class Ws_Param:
    """WebSocket参数类，参考示例代码重构"""

    def __init__(self, APPID, APIKey, APISecret, AudioData):
        self.APPID = APPID
        self.APIKey = APIKey
        self.APISecret = APISecret
        self.AudioData = AudioData

        # 公共参数(common)
        self.CommonArgs = {"app_id": self.APPID}
        # 业务参数(business)，使用示例中的参数
        self.BusinessArgs = {
            "domain": "iat",
            "language": "zh_cn",
            "accent": "mandarin",
            "vinfo": 1,
            "vad_eos": 10000
        }

    def create_url(self):
        """生成鉴权URL，参考示例代码"""
        url = 'wss://ws-api.xfyun.cn/v2/iat'

        # 生成RFC1123格式的时间戳
        now = datetime.now()
        date = format_date_time(mktime(now.timetuple()))

        # 拼接字符串
        signature_origin = "host: " + "ws-api.xfyun.cn" + "\n"
        signature_origin += "date: " + date + "\n"
        signature_origin += "GET " + "/v2/iat " + "HTTP/1.1"

        # 进行hmac-sha256进行加密
        signature_sha = hmac.new(
            self.APISecret.encode('utf-8'),
            signature_origin.encode('utf-8'),
            digestmod=hashlib.sha256
        ).digest()
        signature_sha = base64.b64encode(signature_sha).decode(encoding='utf-8')

        authorization_origin = f'api_key="{self.APIKey}", algorithm="hmac-sha256", headers="host date request-line", signature="{signature_sha}"'
        authorization = base64.b64encode(authorization_origin.encode('utf-8')).decode(encoding='utf-8')

        # 将请求的鉴权参数组合为字典
        v = {
            "authorization": authorization,
            "date": date,
            "host": "ws-api.xfyun.cn"
        }

        # 拼接鉴权参数，生成url
        url = url + '?' + urlencode(v)
        return url


def get_credentials():
    """获取讯飞API凭证"""
    appid = os.getenv("XF_APP_ID")
    api_key = os.getenv("XF_APP_KEY")
    api_secret = os.getenv("XF_APP_SECRET")

    if not all([appid, api_key, api_secret]):
        raise ValueError("缺少讯飞API凭证(XF_APPID, XF_APP_KEY, XF_APP_SECRET)")
    return appid, api_key, api_secret


async def recognize(audio_data, lang="zh_cn", pd="iat"):
    """
    实时语音识别主函数
    audio_data: 16kHz 16位单声道PCM音频数据
    """
    appid, api_key, api_secret = get_credentials()
    ws_param = Ws_Param(appid, api_key, api_secret, audio_data)
    ws_url = ws_param.create_url()
    session_id = f"sid-{int(time.time() * 1000)}"

    try:
        async with aiohttp.ClientSession() as session:
            # 设置超时
            timeout = aiohttp.ClientTimeout(total=60)
            async with session.ws_connect(ws_url, timeout=timeout) as ws:
                frameSize = 8000  # 每一帧的音频大小
                intervel = 0.04  # 发送音频间隔(单位:s)
                status = STATUS_FIRST_FRAME  # 音频的状态信息

                pos = 0
                while True:
                    buf = audio_data[pos:pos + frameSize]
                    pos += frameSize

                    if not buf:
                        status = STATUS_LAST_FRAME

                    if status == STATUS_FIRST_FRAME:
                        d = {
                            "common": ws_param.CommonArgs,
                            "business": ws_param.BusinessArgs,
                            "data": {
                                "status": 0,
                                "format": "audio/L16;rate=16000",
                                "audio": base64.b64encode(buf).decode(),
                                "encoding": "raw"
                            }
                        }
                        await ws.send_json(d)
                        status = STATUS_CONTINUE_FRAME
                    elif status == STATUS_CONTINUE_FRAME:
                        d = {
                            "data": {
                                "status": 1,
                                "format": "audio/L16;rate=16000",
                                "audio": base64.b64encode(buf).decode(),
                                "encoding": "raw"
                            }
                        }
                        await ws.send_json(d)
                    elif status == STATUS_LAST_FRAME:
                        d = {
                            "data": {
                                "status": 2,
                                "format": "audio/L16;rate=16000",
                                "audio": base64.b64encode(buf).decode(),
                                "encoding": "raw"
                            }
                        }
                        await ws.send_json(d)
                        await asyncio.sleep(1)
                        break

                    await asyncio.sleep(intervel)

                # 接收识别结果
                final_result = ""
                async for msg in ws:
                    if msg.type == aiohttp.WSMsgType.TEXT:
                        data = json.loads(msg.data)
                        logger.debug(f"收到消息: {data}")

                        code = data.get("code")
                        if code != 0:
                            err_msg = data.get("message", "未知错误")
                            logger.error(f"识别错误: {err_msg}, code: {code}")
                            return {
                                "error": f"识别错误: {err_msg}",
                                "code": code,
                                "success": False
                            }

                        if "data" in data and "result" in data["data"]:
                            ws_data = data["data"]["result"]["ws"]
                            for item in ws_data:
                                for w in item["cw"]:
                                    final_result += w["w"]
                            logger.info("AI语音识别成功")
                    elif msg.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
                        break

                return {
                    "text": final_result,
                    "session_id": session_id,
                    "success": True
                }

    except aiohttp.ClientError as e:
        logger.error(f"网络错误: {e}")
        return {"error": f"网络错误: {e}", "success": False}
    except Exception as e:
        logger.error(f"未知错误: {e}")
        return {"error": f"未知错误: {e}", "success": False}


async def generate_test_audio(duration=5.0):
    """生成16kHz 16位单声道PCM测试音频"""
    import struct
    sample_rate = 16000
    num_samples = int(sample_rate * duration)
    audio_data = b""
    for i in range(num_samples):
        # 生成440Hz正弦波（测试用）
        t = i / sample_rate
        value = int(16384 * math.sin(2 * math.pi * 440 * t))
        audio_data += struct.pack("h", value)
    return audio_data


async def recognition():
    """测试语音识别功能"""
    audio_data = await generate_test_audio()
    result = await recognize(audio_data)

    print("识别结果:")
    if result["success"]:
        print(f"文本: {result['text']}")
    else:
        print(f"错误: {result.get('error', '未知错误')}")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s"
    )
    asyncio.run(recognition())