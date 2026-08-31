"""验收测试（集成测试）。

这些测试需要真实的 API key 才能运行，验证 agent 端到端功能。
没有 API key 时自动跳过。

运行方式:
    set OPENAI_API_KEY=sk-xxx
    pytest tests/test_acceptance.py -v
"""

import os
import shutil
from pathlib import Path

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
    config.workspace = str(ws)  # 确保用临时目录，不被 .guardcode.json 覆盖
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
    hello_file = Path(workspace.workspace) / "hello.txt"
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
    fib_file = Path(workspace.workspace) / "fib.py"
    assert fib_file.exists(), "fib.py was not created"
    content = fib_file.read_text(encoding="utf-8")
    assert "def " in content, "No function definition found in fib.py"
    assert "fib" in content.lower(), "Function name doesn't contain 'fib'"


def test_task3_list_files(workspace):
    """验收任务 3：列出当前目录的 Python 文件。"""
    # 先创建几个文件
    ws_path = Path(workspace.workspace)
    (ws_path / "a.py").write_text("# a", encoding="utf-8")
    (ws_path / "b.py").write_text("# b", encoding="utf-8")
    (ws_path / "c.txt").write_text("c", encoding="utf-8")

    result = run_agent_loop(
        "list all Python files in current directory",
        config=workspace,
        max_iterations=5,
    )
    assert isinstance(result, str)
    # agent 应该在结果中提到 .py 文件
    assert "a.py" in result or "b.py" in result or ".py" in result.lower()


# ──────────────────────────────────────────────────────────
# Phase 3 验收测试：智能化功能
# ──────────────────────────────────────────────────────────


@pytest.fixture
def workspace_with_low_threshold(tmp_path):
    """使用低上下文阈值的临时工作区，用于触发压缩。"""
    ws = tmp_path / "ws"
    ws.mkdir()
    config = load_config(workspace=str(ws))
    config.workspace = str(ws)
    # 设置很低的阈值，使得少量消息就能触发压缩
    config.context.max_context_size = 2000
    config.verbose = True  # 开启 verbose 以观察压缩日志
    yield config
    if ws.exists():
        shutil.rmtree(ws, ignore_errors=True)


def test_task4_long_conversation(workspace_with_low_threshold):
    """验收任务 4：长对话压缩效果。

    构造需要多次迭代的任务，观察上下文压缩是否生效。
    预期：agent 读取多个文件后，上下文超过阈值触发压缩，
    压缩后 agent 仍能正常完成任务。
    """
    config = workspace_with_low_threshold
    ws_path = Path(config.workspace)

    # 创建多个有内容的文件，使读取后上下文膨胀
    for i in range(5):
        (ws_path / f"module_{i}.py").write_text(
            f"# Module {i}\n"
            f"def func_{i}():\n"
            f"    return {i}\n"
            f"\n"
            f"VALUE = {i} * 100\n"
            f"data = ['item{j}' for j in range({i + 3})]\n",
            encoding="utf-8",
        )

    result = run_agent_loop(
        "Read all module_*.py files, then create a summary.py file "
        "that imports all modules and prints their func results.",
        config=config,
        max_iterations=20,
    )
    assert isinstance(result, str)

    # 验证 summary.py 被创建
    summary_file = ws_path / "summary.py"
    assert summary_file.exists(), "summary.py was not created"

    # 验证 summary.py 包含导入语句
    content = summary_file.read_text(encoding="utf-8")
    assert "import" in content or "from" in content, (
        "summary.py should contain import statements"
    )


def test_task5_test_driven_repair(workspace):
    """验收任务 5：测试驱动修复。

    准备有 bug 的代码 + 失败的测试，让 agent 修复。
    预期流程：list_files → read → write → run pytest → 修复 → 再测试
    """
    ws_path = Path(workspace.workspace)

    # 创建有 bug 的 calculator.py（add 函数错误地做了减法）
    (ws_path / "calculator.py").write_text(
        "def add(a, b):\n"
        "    return a - b  # BUG: should be a + b\n"
        "\n"
        "def subtract(a, b):\n"
        "    return a - b\n"
        "\n"
        "def multiply(a, b):\n"
        "    return a * b\n",
        encoding="utf-8",
    )

    # 创建测试文件
    (ws_path / "test_calculator.py").write_text(
        "from calculator import add, subtract, multiply\n"
        "\n"
        "def test_add():\n"
        "    assert add(2, 3) == 5\n"
        "\n"
        "def test_subtract():\n"
        "    assert subtract(5, 3) == 2\n"
        "\n"
        "def test_multiply():\n"
        "    assert multiply(3, 4) == 12\n",
        encoding="utf-8",
    )

    result = run_agent_loop(
        "fix the bug in calculator.py, tests are in test_calculator.py",
        config=workspace,
        max_iterations=15,
    )
    assert isinstance(result, str)

    # 验证 bug 已修复
    calc_file = ws_path / "calculator.py"
    content = calc_file.read_text(encoding="utf-8")
    # add 函数应该返回 a + b，而不是 a - b
    assert "a + b" in content, "add() function was not fixed to use a + b"

    # 验证测试能通过
    import subprocess
    test_result = subprocess.run(
        ["python", "-m", "pytest", str(ws_path / "test_calculator.py"), "-v"],
        capture_output=True,
        text=True,
        cwd=str(ws_path),
        timeout=30,
    )
    assert test_result.returncode == 0, (
        f"Tests should pass after fix. Output:\n{test_result.stdout}\n{test_result.stderr}"
    )


def test_task6_tdd_workflow(workspace):
    """验收任务 6：TDD 流程。

    在空工作区中让 agent 实现一个 stack，观察是否采用 TDD。
    预期：先写测试，再写实现，最后运行测试验证。
    """
    result = run_agent_loop(
        "implement a stack data structure with push, pop, and peek methods "
        "in Python. Use test-driven development: write tests first, "
        "then implement the stack.",
        config=workspace,
        max_iterations=20,
    )
    assert isinstance(result, str)

    ws_path = Path(workspace.workspace)

    # 验证测试文件被创建
    test_files = list(ws_path.glob("test_*.py")) + list(ws_path.glob("*_test.py"))
    assert len(test_files) > 0, "No test file was created (TDD: tests should come first)"

    # 验证 stack 实现文件被创建
    py_files = [f for f in ws_path.glob("*.py") if not f.name.startswith("test_")]
    assert len(py_files) > 0, "No implementation file was created"

    # 验证实现包含 push/pop/peek
    impl_content = ""
    for f in py_files:
        impl_content += f.read_text(encoding="utf-8")
    assert "push" in impl_content.lower(), "Stack implementation should have push"
    assert "pop" in impl_content.lower(), "Stack implementation should have pop"
    assert "peek" in impl_content.lower(), "Stack implementation should have peek"

    # 验证测试能通过
    import subprocess
    test_result = subprocess.run(
        ["python", "-m", "pytest", str(ws_path), "-v"],
        capture_output=True,
        text=True,
        cwd=str(ws_path),
        timeout=30,
    )
    assert test_result.returncode == 0, (
        f"Tests should pass. Output:\n{test_result.stdout}\n{test_result.stderr}"
    )
