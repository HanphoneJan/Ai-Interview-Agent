import asyncio
import base64
import hashlib
import hmac
import json
import logging
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


class AudioGenerateParam:
    """WebSocket参数类，用于语音合成"""

    def __init__(self, APPID, APIKey, APISecret, Text):
        self.APPID = APPID
        self.APIKey = APIKey
        self.APISecret = APISecret
        self.Text = Text

        # 公共参数(common)
        self.CommonArgs = {"app_id": self.APPID}
        # 业务参数(business)，更多个性化参数可在官网查看  mp3格式
        self.BusinessArgs = {"aue": "lame", "auf": "audio/L16;rate=16000", "vcn": "x4_yezi", "tte": "utf8","sfl":1,"speed":50}
        self.Data = {"status": 2, "text": str(base64.b64encode(self.Text.encode('utf-8')), "UTF8")}

    def create_url(self):
        """生成鉴权URL"""
        url = 'wss://tts-api.xfyun.cn/v2/tts'

        # 生成RFC1123格式的时间戳
        now = datetime.now()
        date = format_date_time(mktime(now.timetuple()))

        # 拼接字符串
        signature_origin = "host: " + "ws-api.xfyun.cn" + "\n"
        signature_origin += "date: " + date + "\n"
        signature_origin += "GET " + "/v2/tts " + "HTTP/1.1"

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


async def synthesize(text):
    """
    语音合成主函数
    text: 待合成的文本
    """
    appid, api_key, api_secret = get_credentials()
    ws_param = AudioGenerateParam(appid, api_key, api_secret, text)
    ws_url = ws_param.create_url()
    session_id = f"sid-{int(time.time() * 1000)}"

    try:
        async with aiohttp.ClientSession() as session:
            # 设置超时
            timeout = aiohttp.ClientTimeout(total=60)
            async with session.ws_connect(ws_url, timeout=timeout) as ws:
                d = {
                    "common": ws_param.CommonArgs,
                    "business": ws_param.BusinessArgs,
                    "data": ws_param.Data
                }
                await ws.send_json(d)

                audio_data = b""
                async for msg in ws:
                    if msg.type == aiohttp.WSMsgType.TEXT:
                        data = json.loads(msg.data)
                        logger.debug(f"收到消息: {data}")

                        code = data.get("code")
                        if code != 0:
                            err_msg = data.get("message", "未知错误")
                            logger.error(f"合成错误: {err_msg}, code: {code}")
                            return {
                                "error": f"合成错误: {err_msg}",
                                "code": code,
                                "success": False
                            }

                        if "data" in data:
                            audio = data["data"]["audio"]
                            audio = base64.b64decode(audio)
                            audio_data += audio

                            status = data["data"]["status"]
                            if status == 2:
                                break
                logger.info("AI语音合成成功")
                return {
                    "audio_data": audio_data,
                    "session_id": session_id,
                    "success": True
                }

    except aiohttp.ClientError as e:
        logger.error(f"网络错误: {e}")
        return {"error": f"网络错误: {e}", "success": False}
    except Exception as e:
        logger.error(f"未知错误: {e}")
        return {"error": f"未知错误: {e}", "success": False}


async def synthesis_test():
    """测试语音合成功能"""
    text = "我是韩子健。"
    result = await synthesize(text)

    print("合成结果:")
    if result["success"]:
        with open('synthesized_audio.mp3', 'wb') as f:
            f.write(result["audio_data"])
        print("音频已保存为 synthesized_audio.mp3")
    else:
        print(f"错误: {result.get('error', '未知错误')}")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s"
    )
    asyncio.run(synthesis_test())