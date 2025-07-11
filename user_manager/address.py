# /address.py
import os
import requests
import logging
from django.core.cache import cache

# 获取环境变量中的腾讯地图API密钥
TENCENT_MAP_KEY = os.getenv('TENCENT_MAP_KEY')

# 配置日志
logger = logging.getLogger(__name__)

# 腾讯地图API基础URL
BASE_URL = "https://apis.map.qq.com/ws/district/v1/"

# 缓存时间（秒）
CACHE_TIMEOUT = 60 * 60 * 24  # 24小时


class TencentMapService:
    """腾讯地图服务类，封装地图API调用"""

    def __init__(self, api_key=None):
        self.api_key = api_key or TENCENT_MAP_KEY
        if not self.api_key:
            raise ValueError("未配置腾讯地图API密钥")

    def get_districts(self, parent_id=None):
        """
        获取行政区划数据
        :param parent_id: 父级行政区划ID（None或空字符串表示获取省份列表）
        """
        # 验证API密钥
        if not self.api_key:
            return {
                "status": 4001,
                "message": "腾讯地图API密钥未配置",
                "result": None
            }

        # 处理parent_id为空的情况（获取省份列表）
        cache_key = f"tencent_map_district_all" if not parent_id else f"tencent_map_district_{parent_id}"

        # 尝试从缓存获取数据
        cached_data = cache.get(cache_key)
        if cached_data:
            logger.info(f"从缓存获取行政区划数据: {'省份列表' if not parent_id else parent_id}")
            return cached_data

        try:
            # 构建请求URL和参数
            url = f"{BASE_URL}getchildren"
            params = {'key': self.api_key}

            # 仅当parent_id不为空且有效时才添加id参数
            if parent_id and str(parent_id).strip():
                # 验证id格式（6位数字）
                if not str(parent_id).strip().isdigit() or len(str(parent_id).strip()) != 6:
                    logger.warning(f"无效的行政区划ID: {parent_id}")
                    return {
                        "status": 4003,
                        "message": "行政区划ID必须是6位数字",
                        "result": None
                    }
                params['id'] = str(parent_id).strip()  # 确保id无空格

            # 调用腾讯地图API
            response = requests.get(url, params=params)

            # 检查API响应状态
            if response.status_code != 200:
                logger.error(f"腾讯地图API请求失败，状态码: {response.status_code}")
                return {
                    "status": 5001,
                    "message": f"腾讯地图API请求失败，状态码: {response.status_code}",
                    "result": None
                }

            # 解析API响应
            result = response.json()

            # 检查API返回状态
            if result.get('status') != 0:
                logger.error(f"腾讯地图API返回错误: {result.get('message')} (状态码: {result.get('status')})")
                return {
                    "status": result.get('status', 5002),
                    "message": result.get('message', "腾讯地图API返回错误"),
                    "result": None
                }

            # 缓存有效数据
            cache.set(cache_key, result, CACHE_TIMEOUT)

            return result

        except Exception as e:
            logger.error(f"调用腾讯地图API异常: {str(e)}")
            return {
                "status": 5000,
                "message": "调用腾讯地图API异常",
                "result": None
            }