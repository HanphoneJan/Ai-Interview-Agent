# tests/test_resumes_engines.py
import json
import os
import pytest
import time
import re
from evaluation_system.resumes_engines import ResumeParser, parse_local_resume
import tempfile

# 使用真实的环境变量（确保在运行测试前已设置）
ALI_ACCESS_KEY_ID = os.environ.get("ALI_ACCESS_KEY_ID")
ALI_ACCESS_KEY_SECRET = os.environ.get("ALI_ACCESS_KEY_SECRET")

# 跳过测试的条件（如果没有设置凭证）
requires_credentials = pytest.mark.skipif(
    not (ALI_ACCESS_KEY_ID and ALI_ACCESS_KEY_SECRET),
    reason="需要设置ALI_ACCESS_KEY_ID和ALI_ACCESS_KEY_SECRET环境变量"
)


@pytest.fixture
def parser():
    return ResumeParser()


@pytest.fixture
def uploaded_job_id(parser):
    """上传文件并返回job_id的fixture"""
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as f:
        f.write(b"Test resume content")
        file_path = f.name

    try:
        response = parser.upload_file(file_path)
        assert "Data" in response and "Id" in response["Data"]
        yield response["Data"]["Id"]
    finally:
        os.unlink(file_path)


@requires_credentials
def test_real_upload_file(parser):
    """测试文件上传功能"""
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as f:
        f.write(b"I am Hanphone.And you?")
        file_path = f.name
        file_name = os.path.basename(file_path)

    try:
        response = parser.upload_file(file_path, file_name)

        assert isinstance(response, dict), "响应不是字典类型"
        assert "Data" in response, "响应中缺少Data字段"
        assert "Id" in response["Data"], "Data字段中缺少Id字段"

        job_id = response["Data"]["Id"]
        assert isinstance(job_id, str), "Job ID不是字符串类型"

        uuid_pattern = r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
        if re.match(uuid_pattern, job_id):
            assert True, "Job ID格式符合UUID规范"

        print(f"成功上传文件，Job ID: {job_id}")
        print(response)
    finally:
        os.unlink(file_path)


@requires_credentials
@pytest.fixture
def job_status(parser, uploaded_job_id):
    """获取并返回任务状态的fixture"""
    time.sleep(2)
    response = parser.check_status(uploaded_job_id)
    assert "Data" in response and "Status" in response["Data"]
    status = response["Data"]["Status"]
    print(f"任务状态: {status}")
    return status


@requires_credentials
@pytest.mark.dependency(depends=["job_status"])
def test_real_get_result(parser, uploaded_job_id, job_status):
    """获取解析结果的测试"""
    status = job_status
    if status.lower() != "success":
        print(f"当前状态: {status}，等待任务完成...")
        max_attempts = 5
        for attempt in range(max_attempts):
            time.sleep(5)
            status = parser.check_status(uploaded_job_id)["Data"]["Status"]
            print(f"尝试 {attempt + 1}/5 - 当前状态: {status}")
            if status.lower() == "success":
                print("任务已成功完成")
                break
            elif status.lower() == "fail":
                pytest.fail(f"任务失败: {parser.check_status(uploaded_job_id).get('Message', '未知错误')}")
        else:
            pytest.fail(f"任务未在规定时间内完成，最终状态: {status}")
    else:
        print("任务已处于成功状态，直接获取结果")

    print("正在获取解析结果...")
    response = parser.get_result(uploaded_job_id)
    print(f"获取结果响应: {json.dumps(response, ensure_ascii=False, indent=2)}")

    assert "Data" in response, "响应中缺少Data字段"
    assert "layouts" in response["Data"], "Data字段中缺少layouts字段"
    assert isinstance(response["Data"]["layouts"], list), "layouts字段不是列表类型"
    assert len(response["Data"]["layouts"]) > 0, "layouts列表为空"


@requires_credentials
def test_real_parse_resume(parser):
    """测试完整解析流程"""
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as f:
        f.write(b"I am Hanphone.And you?")
        file_path = f.name

    try:
        result = parser.parse_resume(file_path, max_retries=10, retry_interval=3)
        assert "Data" in result, "结果中缺少Data字段"
        assert "layouts" in result["Data"], "Data字段中缺少layouts字段"
        print(result)
        has_markdown = any(
            layout.get("markdownContent") and layout["markdownContent"].strip()
            for layout in result["Data"]["layouts"]
        )
        assert has_markdown, "未找到有效的Markdown内容"

    finally:
        os.unlink(file_path)