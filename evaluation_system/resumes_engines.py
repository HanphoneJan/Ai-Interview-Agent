import time
from typing import Dict, Any, Optional, Tuple
from alibabacloud_docmind_api20220711.client import Client as DocMindClient
from alibabacloud_tea_openapi.models import Config
from alibabacloud_docmind_api20220711.models import SubmitDocParserJobAdvanceRequest, QueryDocParserStatusRequest, \
    GetDocParserResultRequest
from alibabacloud_tea_util.models import RuntimeOptions
import logging
import json
import requests
import os
from dotenv import load_dotenv

# 加载.env文件中的环境变量
load_dotenv()

# 配置日志
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


class ResumeParser:
    """阿里云文档解析(大模型版)API封装类，用于解析简历文档"""

    def __init__(self, region_id: str = "cn-hangzhou", endpoint: str = "docmind-api.cn-hangzhou.aliyuncs.com"):
        """初始化解析器"""
        self.region_id = region_id
        self.endpoint = endpoint
        self.client = self._init_client()

    def _init_client(self) -> DocMindClient:
        """初始化阿里云API客户端"""
        try:
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
        """上传本地文件到阿里云文档解析API"""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"文件不存在: {file_path}")

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
        """检查文档解析任务状态"""
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
        """获取文档解析结果（支持分页）"""
        try:
            request = GetDocParserResultRequest(
                id=job_id,
                layout_step_size=layout_step_size,
                layout_num=layout_num
            )
            response = self.client.get_doc_parser_result(request)
            logger.debug(f"获取任务 {job_id} 第{layout_num//layout_step_size + 1}页结果成功")
            return response.body.to_map()
        except Exception as e:
            logger.error(f"获取解析结果失败: {e}")
            raise

    def parse_resume(self, file_path: str, max_retries: int = 10, retry_interval: int = 5) -> Tuple[
        Dict[str, Any], str]:
        """完整的简历解析流程：上传-等待-获取结果（修复核心问题）"""
        # 1. 上传文件
        upload_response = self.upload_file(file_path)
        job_id = upload_response["Data"]["Id"]

        # 2. 等待解析完成（修复：状态判断大小写匹配API返回值）
        retries = 0
        status = "init"  # 初始状态设为小写，匹配API返回格式

        while retries < max_retries and status in ["init", "processing"]:  # 改为小写状态值
            if retries > 0:
                time.sleep(retry_interval)

            status_response = self.check_status(job_id)
            status = status_response["Data"]["Status"].lower()  # 统一转为小写避免大小写问题
            retries += 1

            if status == "success":
                logger.info(f"任务 {job_id} 解析成功")
                break
            elif status == "fail":
                error_msg = status_response.get("Message", "解析失败，未提供详细信息")
                raise Exception(f"任务 {job_id} 解析失败: {error_msg}")

        if retries >= max_retries:
            raise TimeoutError(f"等待任务 {job_id} 解析超时")

        # 3. 获取所有分页解析结果（修复：处理分页，避免内容遗漏）
        all_layouts = []
        layout_num = 0
        layout_step_size = 100  # 每页获取100条布局数据

        while True:
            result_page = self.get_result(job_id, layout_step_size=layout_step_size, layout_num=layout_num)
            # 增加分页结果调试信息
            logger.debug(f"第{layout_num // layout_step_size + 1}页解析结果结构: {list(result_page.keys())}")

            # 关键修复：API返回的是复数形式"layouts"而非单数"layout"
            if "Data" in result_page and "layouts" in result_page["Data"]:
                page_layouts = result_page["Data"]["layouts"]  # 修复字段名为复数形式
                logger.debug(f"第{layout_num // layout_step_size + 1}页获取到{len(page_layouts)}条布局数据")
                all_layouts.extend(page_layouts)

                # 若当前页数据小于分页大小，说明已获取全部内容
                if len(page_layouts) < layout_step_size:
                    break
                layout_num += layout_step_size  # 继续获取下一页
            else:
                logger.warning(f"第{layout_num // layout_step_size + 1}页未找到有效layouts数据，结构为: {result_page}")
                break

        # 4. 提取简历文本内容（支持多字段提取，避免内容丢失）
        resume_text = ""
        # 增加布局总数调试信息
        logger.debug(f"共获取到{len(all_layouts)}条布局数据，开始提取文本内容")

        for idx, layout in enumerate(all_layouts):
            # 打印每条布局数据的字段结构（调试用）
            layout_fields = list(layout.keys())
            logger.debug(f"第{idx + 1}条布局数据包含字段: {layout_fields}")

            # 优先提取markdown内容，若无则提取普通文本（根据API返回调整字段）
            markdown_content = layout.get("markdownContent", "")
            text_content = layout.get("text", "")  # 修复：API中实际文本字段是"text"而非"content"

            # 增加单条内容提取调试
            logger.debug(f"第{idx + 1}条布局：markdown内容长度={len(markdown_content)}，text内容长度={len(text_content)}")

            resume_text += markdown_content + text_content + "\n\n"

        # 增加最终文本长度调试
        logger.debug(f"提取完成，总文本长度为{len(resume_text)}字符")

        if not resume_text.strip():
            # 详细调试信息：当未提取到内容时触发
            error_details = (
                f"未提取到有效简历内容！详细排查：\n"
                f"- 布局数据总数：{len(all_layouts)}\n"
                f"- 最后3条布局字段（若存在）：{[list(layout.keys()) for layout in all_layouts[-3:]] if all_layouts else '无'}\n"
                f"- 可能的字段名不匹配，请检查API返回的实际字段名"
            )
            logger.error(error_details)
            raise ValueError("未从解析结果中提取到有效的简历内容。请查看日志排查字段名是否匹配或数据是否为空")

        return {"Data": {"layout": all_layouts}}, resume_text  # 返回整合后的结果


class XunfeiEvaluator:
    """讯飞API封装类，用于评价简历内容"""

    def __init__(self):
        """初始化讯飞评价器"""
        api_key = os.getenv('XF_SPARK_RPO')
        if not api_key:
            raise ValueError("请配置环境变量 XF_SPARK_RPO")

        self.api_key = f"Bearer {api_key}"
        self.api_url = "https://spark-api-open.xf-yun.com/v1/chat/completions"
        self.max_retries = 3
        self.retry_delay = 2

    def evaluate_resume(self, resume_content: str) -> dict:
        """调用讯飞API评价简历"""
        prompt = f"""请从以下几个方面评价这份简历：
        1. 整体结构和逻辑性
        2. 个人信息完整性
        3. 工作/教育经历描述的清晰度
        4. 技能与岗位匹配度
        5. 存在的问题和改进建议

        最后，请给出一个0-10的评分和一个总结性评价分析，格式必须符合以下示例：评分：8.5。总结性分析评价：xxxx。

        简历内容：
        {resume_content}"""

        body = {
            "model": "Pro",
            "user": "user_id",
            "messages": [{"role": "user", "content": prompt}],
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

        headers = {
            'Authorization': self.api_key,
            'content-type': "application/json"
        }

        for attempt in range(self.max_retries):
            try:
                full_response = ""
                isFirstContent = True

                response = requests.post(
                    url=self.api_url,
                    json=body,
                    headers=headers,
                    stream=True,
                    timeout=30
                )
                response.raise_for_status()

                for chunks in response.iter_lines():
                    if chunks and '[DONE]' not in str(chunks):
                        data_org = chunks[6:]
                        try:
                            chunk = json.loads(data_org)
                            text = chunk['choices'][0]['delta']

                            if 'content' in text and text['content']:
                                content = text["content"]
                                if isFirstContent:
                                    isFirstContent = False
                                logger.debug(content)
                                full_response += content

                        except json.JSONDecodeError as e:
                            logger.warning(f"JSON解析错误: {e}")
                            continue

                score = None
                summary = None
                lines = full_response.split('\n')
                for line in lines:
                    if "评分：" in line:
                        try:
                            score_text = line.split("评分：")[-1].strip()
                            # 关键修改：使用float()而非int()，并保留两位小数
                            score = round(float(score_text), 1)
                            print(f"提取到分数: {score}")
                        except ValueError as e:
                            print(f"解析分数失败: {e}, 原始文本: {line}")
                            score = 0  # 设置默认值

                    elif "总结性分析评价：" in line:
                        # 提取冒号后的所有内容（包括换行符）
                        summary_start = line.index("总结性分析评价：") + len("总结性分析评价：")
                        summary = line[summary_start:].strip()

                        # 如果总结内容跨越多行，继续收集后续行
                        next_idx = lines.index(line) + 1
                        while next_idx < len(lines):
                            summary += "\n" + lines[next_idx].strip()
                            next_idx += 1

                if score is None:
                    score = 0
                if not summary:
                    summary = "无有效评价"

                result = {
                    "answer": full_response,
                    "score": score,
                    "summary": summary
                }
                logger.info("简历评价成功")
                return result

            except Exception as e:
                logger.warning(f"讯飞API调用失败 (尝试 {attempt + 1}/{self.max_retries}): {str(e)}")
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay)
                else:
                    raise Exception(f"讯飞API调用失败，已达到最大重试次数: {str(e)}")


def evaluate_resume_file(file_path: str) -> Dict[str, Any]:
    """完整的简历解析和评价流程"""
    try:
        parser = ResumeParser()
        evaluator = XunfeiEvaluator()

        logger.info(f"开始解析简历文件: {file_path}")
        result, resume_text = parser.parse_resume(file_path)
        logger.info(f"简历解析完成，共提取{len(resume_text)}字符")

        logger.info("开始评价简历内容...")
        evaluation = evaluator.evaluate_resume(resume_text)
        logger.info(f"简历评价完成，得分: {evaluation.get('score')}")

        return {
            "parse_result": resume_text,
            "evaluation": evaluation
        }

    except Exception as e:
        logger.error(f"简历处理流程失败: {e}")
        raise


if __name__ == "__main__":
    try:
        resume_path = r"E:\document-git\document-online\工作\个人简历-电子科技大学-韩子健.pdf"

        start_time = time.time()
        evaluate_result = evaluate_resume_file(resume_path)
        end_time = time.time()

        print("\n" + "=" * 50)
        print(f"处理完成，耗时: {end_time - start_time:.2f}秒")
        print(f"简历得分: {evaluate_result['evaluation']['score']}")
        print("总结评价:")
        print(evaluate_result['evaluation']['summary'])
        # print(evaluate_result['evaluation']['answer'])
        # print(evaluate_result['parse_result'])

    except Exception as e:
        logger.error(f"主程序出错: {e}")