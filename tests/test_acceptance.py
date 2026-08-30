"""验收测试（集成测试）。

这些测试需要真实的 API key 才能运行，验证 agent 端到端功能。
没有 API key 时自动跳过。

运行方式:
    set OPENAI_API_KEY=sk-xxx
    pytest tests/test_acceptance.py -v
"""

import os
import shutil

import pytest

from guardcode.agent import run_agent_loop
from guardcode.config import load_config

# 没有 API key 就跳过所有验收测试
pytestmark = pytest.mark.skipif(
    not os.getenv("OPENAI_API_KEY"),
    reason="OPENAI_API_KEY not set, skipping acceptance tests",
)


@pytest.fixture
def workspace(tmp_path):
    """每个测试用例使用独立临时目录。"""
    ws = tmp_path / "ws"
    ws.mkdir()
    config = load_config(workspace=str(ws))
    yield config
    # 清理
    if ws.exists():
        shutil.rmtree(ws, ignore_errors=True)


def test_task1_create_file(workspace):
    """验收任务 1：创建 hello.txt 文件。"""
    result = run_agent_loop(
        "create a file hello.txt with content 'Hello World'",
        config=workspace,
        max_iterations=5,
    )
    assert isinstance(result, str)

    # 验证文件确实被创建了
    hello_file = workspace.workspace / "hello.txt"
    assert hello_file.exists(), "hello.txt was not created"
    assert "Hello World" in hello_file.read_text(encoding="utf-8")


def test_task2_write_fibonacci(workspace):
    """验收任务 2：写斐波那契函数。"""
    result = run_agent_loop(
        "write a Python function to calculate fibonacci in fib.py",
        config=workspace,
        max_iterations=10,
    )
    assert isinstance(result, str)

    # 验证文件被创建且包含函数定义
    fib_file = workspace.workspace / "fib.py"
    assert fib_file.exists(), "fib.py was not created"
    content = fib_file.read_text(encoding="utf-8")
    assert "def " in content, "No function definition found in fib.py"
    assert "fib" in content.lower(), "Function name doesn't contain 'fib'"


def test_task3_list_files(workspace):
    """验收任务 3：列出当前目录的 Python 文件。"""
    # 先创建几个文件
    (workspace.workspace / "a.py").write_text("# a", encoding="utf-8")
    (workspace.workspace / "b.py").write_text("# b", encoding="utf-8")
    (workspace.workspace / "c.txt").write_text("c", encoding="utf-8")

    result = run_agent_loop(
        "list all Python files in current directory",
        config=workspace,
        max_iterations=5,
    )
    assert isinstance(result, str)
    # agent 应该在结果中提到 .py 文件
    assert "a.py" in result or "b.py" in result or ".py" in result.lower()
