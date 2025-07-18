"""
人脸表情分析引擎模块
封装讯飞人脸特征分析表情WebAPI接口
"""
import json

import cv2
import numpy as np
import requests
import time
import hashlib
import base64
import logging
from typing import Dict, Union
from pathlib import Path
import os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()
logger = logging.getLogger(__name__)


class FacialExpressionAnalyzer:
    """人脸表情分析引擎"""

    def __init__(self):
        """
        初始化分析器
        从环境变量中读取配置:
        - XF_APP_ID: 讯飞应用ID
        - XF_API_KEY: 讯飞API密钥
        """
        self.URL = "http://tupapi.xfyun.cn/v1/expression"
        self.APPID = os.getenv("XF_APP_ID")
        self.API_KEY = os.getenv("XF_API_KEY")

        if not self.APPID or not self.API_KEY:
            raise ValueError("缺少必要的环境变量配置: XF_APP_ID 和 XF_API_KEY")

        logger.info("人脸表情分析引擎初始化完成")

    def _generate_headers(self, image_name: str, image_url: str = None) -> Dict[str, str]:
        """
        生成API请求头
        :param image_name: 图片名称
        :param image_url: 图片URL(可选)
        :return: 请求头字典
        """
        cur_time = str(int(time.time()))
        param = {
            "image_name": image_name,
            "image_url": image_url
        }
        param_json = json.dumps(param, ensure_ascii=False)

        param_base64 = base64.b64encode(param_json.encode('utf-8')).decode('utf-8')

        # 计算校验和
        m = hashlib.md5()
        m.update((self.API_KEY + cur_time + param_base64).encode('utf-8'))
        checksum = m.hexdigest()

        headers = {
            'X-CurTime': cur_time,
            'X-Param': param_base64,
            'X-Appid': self.APPID,
            'X-CheckSum': checksum,
            'Content-Type': 'application/json'
        }
        return headers

    def analyze_by_url(self, image_url: str, image_name: str = "image.jpg") -> Dict[str, Union[str, dict]]:
        """
        通过URL分析图片表情
        :param image_url: 图片URL
        :param image_name: 图片名称(可选)
        :return: 分析结果字典
        """
        try:
            headers = self._generate_headers(image_name, image_url)
            response = requests.post(self.URL, headers=headers)
            response.raise_for_status()

            result = response.json()
            logger.debug(f"API响应: {result}")

            return {
                "success": True,
                "data": result,
                "message": "分析成功"
            }
        except requests.exceptions.RequestException as e:
            logger.error(f"请求失败: {e}")
            return {
                "success": False,
                "error": f"请求失败: {str(e)}",
                "status_code": getattr(e.response, 'status_code', None)
            }
        except Exception as e:
            logger.error(f"分析失败: {e}")
            return {
                "success": False,
                "error": f"分析失败: {str(e)}"
            }

    def analyze_by_file(self, file_path: Union[str, Path]) -> Dict[str, Union[str, dict]]:
        """
        通过本地文件分析图片表情
        :param file_path: 图片文件路径
        :return: 分析结果字典
        """
        try:
            file_path = Path(file_path)
            if not file_path.exists():
                raise FileNotFoundError(f"文件不存在: {file_path}")

            # 检查文件大小(不超过800KB)
            if file_path.stat().st_size > 800 * 1024:
                raise ValueError("图片大小超过800KB限制")

            with open(file_path, 'rb') as f:
                image_data = f.read()

            headers = self._generate_headers(file_path.name)
            response = requests.post(self.URL, headers=headers, data=image_data)
            response.raise_for_status()

            result = response.json()
            logger.debug(f"API响应: {result}")

            return {
                "success": True,
                "data": result,
                "message": "分析成功"
            }
        except FileNotFoundError as e:
            logger.error(f"文件错误: {e}")
            return {
                "success": False,
                "error": str(e)
            }
        except requests.exceptions.RequestException as e:
            logger.error(f"请求失败: {e}")
            return {
                "success": False,
                "error": f"请求失败: {str(e)}",
                "status_code": getattr(e.response, 'status_code', None)
            }
        except Exception as e:
            logger.error(f"分析失败: {e}")
            return {
                "success": False,
                "error": f"分析失败: {str(e)}"
            }

    def analyze_frame(self, frame: np.ndarray) -> Dict[str, Union[str, dict]]:
        """
        分析视频帧中的人脸表情
        :param frame: OpenCV读取的视频帧(numpy.ndarray)
        :return: 分析结果字典
        """
        try:
            # 将OpenCV帧(BRG格式)转换为JPEG字节流
            _, buffer = cv2.imencode('.jpg', frame)
            image_bytes = buffer.tobytes()

            # 生成随机文件名
            image_name = f"frame_{int(time.time() * 1000)}.jpg"

            # 生成请求头
            headers = self._generate_headers(image_name)

            # 发送请求
            response = requests.post(self.URL, headers=headers, data=image_bytes)
            response.raise_for_status()

            result = response.json()
            logger.debug(f"表情分析API响应: {result}")

            # 解析响应中的表情数据
            emotions = self._parse_expression_result(result)
            return {
                "success": True,
                "data": emotions,
                "message": "表情分析成功"
            }

        except requests.exceptions.RequestException as e:
            logger.error(f"API请求失败: {e}")
            return {
                "success": False,
                "error": f"API请求失败: {str(e)}",
                "status_code": getattr(e.response, 'status_code', None)
            }
        except Exception as e:
            logger.error(f"表情分析失败: {e}")
            return {
                "success": False,
                "error": f"表情分析失败: {str(e)}"
            }

    def _parse_expression_result(self, result: Dict) -> Dict:
        """
        解析API返回的表情结果
        :param result: API原始响应
        :return: 解析后的表情数据
        """
        # 根据讯飞API实际返回格式进行解析
        # 以下为示例实现，需根据实际API文档调整
        if result.get("code") != 0:
            logger.warning(f"API返回非成功状态: {result.get('desc')}")
            return {}

        emotions = {}
        if "data" in result and "face" in result["data"]:
            for face_idx, face in enumerate(result["data"]["face"]):
                emotions[f"face_{face_idx}"] = {
                    "expression": face.get("expression", "unknown"),
                    "confidence": face.get("confidence", 0.0),
                    "location": face.get("location", {})
                }

        return emotions
# 示例用法
if __name__ == "__main__":
    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    try:
        analyzer = FacialExpressionAnalyzer()

        # 示例1: 通过URL分析
        print("通过URL分析示例:")
        url_result = analyzer.analyze_by_url(
            image_url="https://th.bing.com/th/id/R.b9a4a88c9d007037e694137fca4e8e56?rik=%2f%2fvXyTd4uGUTjA&riu=http%3a%2f%2fviapi-test.oss-cn-shanghai.aliyuncs.com%2fviapi-3.0domepic%2ffacebody%2fFaceTidyup%2fFaceTidyup5.png&ehk=5zFCdzXfz6xXQukCobwXTQMxTL4jhvcMODaE%2fmwyg0E%3d&risl=&pid=ImgRaw&r=0",
            image_name="test.jpg"
        )
        print(json.dumps(url_result, indent=2, ensure_ascii=False))

        # 示例2: 通过文件分析
        print("\n通过文件分析示例:")
        file_result = analyzer.analyze_by_file(r"E:\document-git\document-online\test.jpg")  # 替换为实际图片路径
        print(json.dumps(file_result, indent=2, ensure_ascii=False))

    except Exception as e:
        logger.error(f"引擎初始化失败: {e}")