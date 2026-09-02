"""压缩实验的场景数据生成器"""

import json
from typing import Any


def create_file_intensive_messages() -> list[dict[str, Any]]:
    """模拟文件读写密集型任务的消息历史"""
    messages = [
        {"role": "system", "content": "You are GuardCode Agent" * 50},
        {"role": "user", "content": "Refactor the codebase"},
    ]
    
    # 模拟 10 次文件读取
    for i in range(10):
        messages.append({
            "role": "assistant",
            "content": f"Reading file {i}",
            "tool_calls": [{
                "id": f"call_{i}",
                "type": "function",
                "function": {
                    "name": "read_file",
                    "arguments": json.dumps({"path": f"src/module_{i}.py"})
                }
            }]
        })
        messages.append({
            "role": "tool",
            "tool_call_id": f"call_{i}",
            "content": json.dumps({
                "success": True,
                "result": f"def function_{i}():\n    pass\n" + "    # comment\n" * 100,
                "error": "",
                "_tool_name": "read_file",
                "_path": f"src/module_{i}.py"
            })
        })
    
    # 模拟 5 次文件修改
    for i in range(5):
        messages.append({
            "role": "assistant",
            "content": f"Writing file {i}",
            "tool_calls": [{
                "id": f"call_write_{i}",
                "type": "function",
                "function": {
                    "name": "write_file",
                    "arguments": json.dumps({
                        "path": f"src/module_{i}.py",
                        "content": "def refactored():\n    return True\n" + "    # new code\n" * 100
                    })
                }
            }]
        })
        messages.append({
            "role": "tool",
            "tool_call_id": f"call_write_{i}",
            "content": json.dumps({
                "success": True,
                "result": f"Successfully wrote to src/module_{i}.py",
                "error": "",
                "_tool_name": "write_file",
                "_path": f"src/module_{i}.py"
            })
        })
    
    return messages


def create_command_intensive_messages() -> list[dict[str, Any]]:
    """模拟命令执行密集型任务的消息历史"""
    messages = [
        {"role": "system", "content": "You are GuardCode Agent" * 50},
        {"role": "user", "content": "Run tests and fix issues"},
    ]
    
    # 模拟 15 次命令执行
    for i in range(15):
        messages.append({
            "role": "assistant",
            "content": f"Running test {i}",
            "tool_calls": [{
                "id": f"call_{i}",
                "type": "function",
                "function": {
                    "name": "run_command",
                    "arguments": json.dumps({"command": f"pytest tests/test_{i}.py -v"})
                }
            }]
        })
        messages.append({
            "role": "tool",
            "tool_call_id": f"call_{i}",
            "content": json.dumps({
                "success": i % 3 != 0,
                "result": f"Test output for test_{i}\n" + "." * 200 + f"\n{'PASSED' if i % 3 != 0 else 'FAILED'}",
                "error": "" if i % 3 != 0 else "AssertionError: expected True",
                "exit_code": 0 if i % 3 != 0 else 1,
                "_tool_name": "run_command"
            })
        })
    
    return messages


def create_mixed_messages() -> list[dict[str, Any]]:
    """模拟混合型任务的消息历史"""
    messages = [
        {"role": "system", "content": "You are GuardCode Agent" * 50},
        {"role": "user", "content": "Implement feature X with tests"},
    ]
    
    # 交替进行文件操作和命令执行
    for i in range(8):
        # 读文件
        messages.append({
            "role": "assistant",
            "content": f"Reading source {i}",
            "tool_calls": [{
                "id": f"call_read_{i}",
                "type": "function",
                "function": {
                    "name": "read_file",
                    "arguments": json.dumps({"path": f"src/feature_{i}.py"})
                }
            }]
        })
        messages.append({
            "role": "tool",
            "tool_call_id": f"call_read_{i}",
            "content": json.dumps({
                "success": True,
                "result": "def old_feature():\n    pass\n" + "    # old code\n" * 80,
                "error": "",
                "_tool_name": "read_file",
                "_path": f"src/feature_{i}.py"
            })
        })
        
        # 写文件
        messages.append({
            "role": "assistant",
            "content": f"Writing source {i}",
            "tool_calls": [{
                "id": f"call_write_{i}",
                "type": "function",
                "function": {
                    "name": "write_file",
                    "arguments": json.dumps({
                        "path": f"src/feature_{i}.py",
                        "content": "def new_feature():\n    return True\n" + "    # new code\n" * 80
                    })
                }
            }]
        })
        messages.append({
            "role": "tool",
            "tool_call_id": f"call_write_{i}",
            "content": json.dumps({
                "success": True,
                "result": f"Successfully wrote to src/feature_{i}.py",
                "error": "",
                "_tool_name": "write_file",
                "_path": f"src/feature_{i}.py"
            })
        })
        
        # 运行测试
        messages.append({
            "role": "assistant",
            "content": f"Testing feature {i}",
            "tool_calls": [{
                "id": f"call_test_{i}",
                "type": "function",
                "function": {
                    "name": "run_command",
                    "arguments": json.dumps({"command": f"pytest tests/test_feature_{i}.py"})
                }
            }]
        })
        messages.append({
            "role": "tool",
            "tool_call_id": f"call_test_{i}",
            "content": json.dumps({
                "success": True,
                "result": f"Test passed for feature_{i}\n" + "." * 100,
                "error": "",
                "exit_code": 0,
                "_tool_name": "run_command"
            })
        })
    
    return messages


def create_long_conversation_messages() -> list[dict[str, Any]]:
    """模拟长对话任务（50+ 轮交互）"""
    messages = [
        {"role": "system", "content": "You are GuardCode Agent" * 50},
        {"role": "user", "content": "Build a complete web application"},
    ]
    
    for i in range(50):
        if i % 3 == 0:
            # 读文件
            messages.append({
                "role": "assistant",
                "content": f"Step {i}: Reading",
                "tool_calls": [{
                    "id": f"call_{i}",
                    "type": "function",
                    "function": {
                        "name": "read_file",
                        "arguments": json.dumps({"path": f"file_{i}.py"})
                    }
                }]
            })
            messages.append({
                "role": "tool",
                "tool_call_id": f"call_{i}",
                "content": json.dumps({
                    "success": True,
                    "result": f"# File {i}\n" + "code line\n" * 50,
                    "error": "",
                    "_tool_name": "read_file",
                    "_path": f"file_{i}.py"
                })
            })
        elif i % 3 == 1:
            # 写文件
            messages.append({
                "role": "assistant",
                "content": f"Step {i}: Writing",
                "tool_calls": [{
                    "id": f"call_{i}",
                    "type": "function",
                    "function": {
                        "name": "write_file",
                        "arguments": json.dumps({
                            "path": f"file_{i}.py",
                            "content": f"# New file {i}\n" + "new code\n" * 50
                        })
                    }
                }]
            })
            messages.append({
                "role": "tool",
                "tool_call_id": f"call_{i}",
                "content": json.dumps({
                    "success": True,
                    "result": f"Wrote file_{i}.py",
                    "error": "",
                    "_tool_name": "write_file",
                    "_path": f"file_{i}.py"
                })
            })
        else:
            # 运行命令
            messages.append({
                "role": "assistant",
                "content": f"Step {i}: Command",
                "tool_calls": [{
                    "id": f"call_{i}",
                    "type": "function",
                    "function": {
                        "name": "run_command",
                        "arguments": json.dumps({"command": f"command_{i}"})
                    }
                }]
            })
            messages.append({
                "role": "tool",
                "tool_call_id": f"call_{i}",
                "content": json.dumps({
                    "success": True,
                    "result": f"Output {i}\n" + "line\n" * 30,
                    "error": "",
                    "exit_code": 0,
                    "_tool_name": "run_command"
                })
            })
    
    return messages
