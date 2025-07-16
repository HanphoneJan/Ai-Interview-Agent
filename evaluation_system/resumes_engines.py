# evaluation_system/resumes_engines.py

import time
from typing import Dict, Any, Optional
from alibabacloud_docmind_api20220711.client import Client as DocMindClient
from alibabacloud_tea_openapi.models import Config
from alibabacloud_docmind_api20220711.models import SubmitDocParserJobAdvanceRequest, QueryDocParserStatusRequest, \
    GetDocParserResultRequest
from alibabacloud_tea_util.models import RuntimeOptions
import logging
import json
import requests
import os
from dotenv import load_dotenv  # 添加dotenv库用于加载环境变量

# 加载.env文件中的环境变量
load_dotenv()

# 配置日志
logger = logging.getLogger(__name__)


class ResumeParser:
    """阿里云文档解析(大模型版)API封装类，用于解析简历文档"""

    def __init__(self, region_id: str = "cn-hangzhou", endpoint: str = "docmind-api.cn-hangzhou.aliyuncs.com"):
        """
        初始化解析器

        Args:
            region_id: 阿里云区域ID
            endpoint: API端点
        """
        self.region_id = region_id
        self.endpoint = endpoint
        self.client = self._init_client()

    def _init_client(self) -> DocMindClient:
        """初始化阿里云API客户端"""
        try:
            # 从环境变量中获取AccessKey
            access_key_id = os.getenv("ALI_ACCESS_KEY_ID")
            access_key_secret = os.getenv("ALI_ACCESS_KEY_SECRET")

            if not access_key_id or not access_key_secret:
                raise ValueError("未找到环境变量中的ALI_ACCESS_KEY_ID或ALI_ACCESS_KEY_SECRET")

            config = Config(
                access_key_id=access_key_id,
                access_key_secret=access_key_secret,
                region_id=self.region_id,
                endpoint=self.endpoint
            )
            return DocMindClient(config)
        except Exception as e:
            logger.error(f"初始化客户端失败: {e}")
            raise

    def upload_file(self, file_path: str, file_name: Optional[str] = None) -> Dict[str, Any]:
        """
        上传本地文件到阿里云文档解析API

        Args:
            file_path: 本地文件路径
            file_name: 自定义文件名，若不提供则使用原文件名

        Returns:
            包含业务订单号的响应数据
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"文件不存在: {file_path}")

        # 确定文件名
        if not file_name:
            file_name = os.path.basename(file_path)

        try:
            request = SubmitDocParserJobAdvanceRequest(
                file_url_object=open(file_path, "rb"),
                file_name=file_name,
                file_name_extension=file_name.split(".")[-1] if "." in file_name else ""
            )
            runtime = RuntimeOptions()
            response = self.client.submit_doc_parser_job_advance(request, runtime)
            logger.info(f"文件上传成功，订单号: {response.body.data.id}")
            return response.body.to_map()
        except Exception as e:
            logger.error(f"文件上传失败: {e}")
            raise

    def check_status(self, job_id: str) -> Dict[str, Any]:
        """
        检查文档解析任务状态

        Args:
            job_id: 业务订单号

        Returns:
            包含任务状态的响应数据
        """
        try:
            request = QueryDocParserStatusRequest(id=job_id)
            response = self.client.query_doc_parser_status(request)
            status = response.body.data.status
            logger.info(f"任务 {job_id} 状态: {status}")
            return response.body.to_map()
        except Exception as e:
            logger.error(f"查询任务状态失败: {e}")
            raise

    def get_result(self, job_id: str, layout_step_size: int = 100, layout_num: int = 0) -> Dict[str, Any]:
        """
        获取文档解析结果

        Args:
            job_id: 业务订单号
            layout_step_size: 每次获取的布局块数量
            layout_num: 起始布局块位置

        Returns:
            文档解析结果
        """
        try:
            request = GetDocParserResultRequest(
                id=job_id,
                layout_step_size=layout_step_size,
                layout_num=layout_num
            )
            response = self.client.get_doc_parser_result(request)
            logger.info(f"获取任务 {job_id} 结果成功")
            return response.body.to_map()
        except Exception as e:
            logger.error(f"获取解析结果失败: {e}")
            raise

    def parse_resume(self, file_path: str, max_retries: int = 10, retry_interval: int = 5) -> Dict[str, Any]:
        """
        完整的简历解析流程：上传-等待-获取结果

        Args:
            file_path: 简历文件路径
            max_retries: 最大重试次数
            retry_interval: 重试间隔(秒)

        Returns:
            解析后的简历内容
        """
        # 1. 上传文件
        upload_response = self.upload_file(file_path)
        job_id = upload_response["Data"]["Id"]

        # 2. 等待解析完成
        retries = 0
        status = "Processing"

        while retries < max_retries and status in ["Init", "Processing"]:
            if retries > 0:
                time.sleep(retry_interval)

            status_response = self.check_status(job_id)
            status = status_response["Data"]["Status"]
            retries += 1

            if status == "Success":
                logger.info(f"任务 {job_id} 解析成功")
                break
            elif status == "Fail":
                error_msg = status_response.get("Message", "解析失败，未提供详细信息")
                raise Exception(f"任务 {job_id} 解析失败: {error_msg}")

        if retries >= max_retries:
            raise TimeoutError(f"等待任务 {job_id} 解析超时")

        # 3. 获取解析结果
        result = self.get_result(job_id)
        return result


def parse_local_resume(file_path: str) -> Dict[str, Any]:
    """
    解析本地简历文件的便捷函数

    Args:
        file_path: 简历文件路径

    Returns:
        解析后的简历内容
    """
    parser = ResumeParser()
    return parser.parse_resume(file_path)




class XunfeiEvaluator:
    """讯飞API封装类，用于评价简历内容"""

    def __init__(self):
        """初始化讯飞评价器"""
        # 从环境变量中获取 API 密钥
        self.api_key = f"Bearer {os.getenv('XF_SPARK_RPO')}"
        self.api_url = "https://spark-api-open.xf-yun.com/v1/chat/completions"  # 讯飞Spark API地址

        # 验证环境变量
        if not self.api_key:
            raise ValueError("请配置环境变量 XF_API_KEY")

    def evaluate_resume(self, resume_content: str) -> dict:
        """
        调用讯飞API评价简历

        Args:
            resume_content: 简历文本内容

        Returns:
            讯飞API返回的评价结果
        """
        # 构造评价提示词
        prompt = f"""请从以下几个方面评价这份简历：
        1. 整体结构和逻辑性
        2. 个人信息完整性
        3. 工作/教育经历描述的清晰度
        4. 技能与岗位匹配度
        5. 存在的问题和改进建议
        
        简历内容：
        {resume_content}"""

        # 构造请求体
        body = {
            "model": "Pro",
            "user": "user_id",
            "messages": [{"role": "user", "content": prompt}],
            # 下面是可选参数
            "stream": True,
            "tools": [
                {
                    "type": "web_search",
                    "web_search": {
                        "enable": True,
                        "search_mode": "deep"
                    }
                }
            ]
        }

        # 构造请求头
        headers = {
            'Authorization': self.api_key,
            'content-type': "application/json"
        }

        full_response = ""  # 存储返回结果
        isFirstContent = True  # 首帧标识

        try:
            # 发送请求
            response = requests.post(url=self.api_url, json=body, headers=headers, stream=True)
            response.raise_for_status()  # 检查HTTP错误状态

            for chunks in response.iter_lines():
                # 打印返回的每帧内容
                if chunks and '[DONE]' not in str(chunks):
                    data_org = chunks[6:]
                    chunk = json.loads(data_org)
                    text = chunk['choices'][0]['delta']

                    # 判断最终结果状态并输出
                    if 'content' in text and '' != text['content']:
                        content = text["content"]
                        if isFirstContent:
                            isFirstContent = False
                        print(content, end="")
                        full_response += content

            result = {"answer": full_response}
            logger.info("简历评价成功")
            return result

        except Exception as e:
            logger.error(f"调用讯飞API失败: {str(e)}")
            raise

# 示例用法
if __name__ == "__main__":
    try:
        # 替换为实际的简历文件路径
        resume_path = r"E:\document-git\document-online\工作\个人简历-电子科技大学-韩子健.pdf"
        result = parse_local_resume(resume_path)

        # 提取解析结果中的Markdown内容
        resume_text = ""
        if "Data" in result and "layouts" in result["Data"]:
            for layout in result["Data"]["layouts"]:
                markdown_content = layout.get("markdownContent", "")
                resume_text += markdown_content + "\n\n"
                print(f"Markdown内容:\n{markdown_content}")
                print("-" * 50)
        else:
            print("未找到解析结果中的Markdown内容")
            exit(1)

        # 调用讯飞API进行简历评价
        evaluator = XunfeiEvaluator()
        evaluation = evaluator.evaluate_resume(resume_text)

        # 提取并打印评价结果
        if "payload" in evaluation and "choices" in evaluation["payload"]:
            evaluation_text = evaluation["payload"]["choices"][0]["text"][0]["content"]
            print("\n" + "=" * 50)
            print("简历评价结果:")
            print(evaluation_text)
        else:
            print("未获取到有效的评价结果")

    except Exception as e:
        logger.error(f"简历解析出错: {e}")