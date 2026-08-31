"""
测试 Agent 核心循环
"""

import json
from unittest.mock import Mock, patch, MagicMock
import pytest

from guardcode.agent import run_agent_loop, _format_assistant_message, _format_tool_result
from guardcode.config import Config


class TestFormatHelpers:
    """测试消息格式化辅助函数"""

    def test_format_assistant_message_no_tool_calls(self):
        """测试格式化无工具调用的 assistant 消息"""
        response = {
            "content": "Hello, I can help you with that.",
            "tool_calls": []
        }
        
        result = _format_assistant_message(response)
        
        assert result["role"] == "assistant"
        assert result["content"] == "Hello, I can help you with that."
        assert "tool_calls" not in result

    def test_format_assistant_message_with_tool_calls(self):
        """测试格式化带工具调用的 assistant 消息"""
        response = {
            "content": "I'll read that file for you.",
            "tool_calls": [
                {
                    "id": "call_123",
                    "name": "read_file",
                    "arguments": {"path": "test.txt"}
                }
            ]
        }
        
        result = _format_assistant_message(response)
        
        assert result["role"] == "assistant"
        assert result["content"] == "I'll read that file for you."
        assert len(result["tool_calls"]) == 1
        assert result["tool_calls"][0]["id"] == "call_123"
        assert result["tool_calls"][0]["type"] == "function"
        assert result["tool_calls"][0]["function"]["name"] == "read_file"
        # arguments 应该是 JSON 字符串
        args = json.loads(result["tool_calls"][0]["function"]["arguments"])
        assert args == {"path": "test.txt"}

    def test_format_tool_result(self):
        """测试格式化工具执行结果"""
        result = {
            "success": True,
            "result": "File content here",
            "error": ""
        }

        message = _format_tool_result("call_123", "read_file", result, {"path": "test.txt"})

        assert message["role"] == "tool"
        assert message["tool_call_id"] == "call_123"
        # content 应该是 JSON 字符串
        content = json.loads(message["content"])
        assert content["success"] is True
        assert content["result"] == "File content here"
        # 元信息
        assert content["_tool_name"] == "read_file"
        assert content["_path"] == "test.txt"

    def test_format_tool_result_no_args(self):
        """测试格式化工具结果（无参数时不应崩溃）"""
        result = {
            "success": True,
            "result": "output",
            "error": ""
        }

        message = _format_tool_result("call_456", "run_command", result)

        content = json.loads(message["content"])
        assert content["_tool_name"] == "run_command"
        assert "_path" not in content

    def test_format_tool_result_path_normalization(self):
        """测试路径规范化（./src/main.py → src/main.py）"""
        result = {
            "success": True,
            "result": "content",
            "error": ""
        }

        message = _format_tool_result("call_789", "write_file", result, {"path": "./src/main.py", "content": "code"})
        content = json.loads(message["content"])
        assert content["_path"] == "src/main.py"


class TestAgentLoop:
    """测试 Agent 主循环"""

    @patch('guardcode.agent.call_model')
    @patch('guardcode.agent.execute_tool')
    @patch('guardcode.agent.init_workspace')
    def test_simple_task_completion(self, mock_init_ws, mock_execute, mock_call):
        """测试简单任务完成（无工具调用）"""
        # 模拟模型直接返回答案，无工具调用
        mock_call.return_value = {
            "content": "Task completed successfully.",
            "tool_calls": [],
            "finish_reason": "stop"
        }
        
        config = Config(workspace=".", model="gpt-4-turbo")
        result = run_agent_loop("Say hello", config=config, max_iterations=5)
        
        assert result == "Task completed successfully."
        assert mock_call.call_count == 1
        assert mock_execute.call_count == 0

    @patch('guardcode.agent.call_model')
    @patch('guardcode.agent.execute_tool')
    @patch('guardcode.agent.init_workspace')
    def test_single_tool_call(self, mock_init_ws, mock_execute, mock_call):
        """测试单次工具调用"""
        # 第一次调用：模型返回工具调用
        # 第二次调用：模型返回最终答案
        mock_call.side_effect = [
            {
                "content": "I'll read the file.",
                "tool_calls": [
                    {
                        "id": "call_123",
                        "name": "read_file",
                        "arguments": {"path": "test.txt"}
                    }
                ],
                "finish_reason": "tool_calls"
            },
            {
                "content": "The file contains: Hello World",
                "tool_calls": [],
                "finish_reason": "stop"
            }
        ]
        
        mock_execute.return_value = {
            "success": True,
            "result": "Hello World",
            "error": ""
        }
        
        config = Config(workspace=".", model="gpt-4-turbo")
        result = run_agent_loop("Read test.txt", config=config, max_iterations=5)
        
        assert result == "The file contains: Hello World"
        assert mock_call.call_count == 2
        assert mock_execute.call_count == 1
        mock_execute.assert_called_once_with("read_file", {"path": "test.txt"}, config=config)

    @patch('guardcode.agent.call_model')
    @patch('guardcode.agent.execute_tool')
    @patch('guardcode.agent.init_workspace')
    def test_multiple_tool_calls(self, mock_init_ws, mock_execute, mock_call):
        """测试多次工具调用"""
        mock_call.side_effect = [
            # 第一次：列出文件
            {
                "content": "Listing files...",
                "tool_calls": [
                    {
                        "id": "call_1",
                        "name": "list_files",
                        "arguments": {"directory": "."}
                    }
                ],
                "finish_reason": "tool_calls"
            },
            # 第二次：读取文件
            {
                "content": "Reading file...",
                "tool_calls": [
                    {
                        "id": "call_2",
                        "name": "read_file",
                        "arguments": {"path": "test.txt"}
                    }
                ],
                "finish_reason": "tool_calls"
            },
            # 第三次：完成
            {
                "content": "Done. Found 2 files and read test.txt.",
                "tool_calls": [],
                "finish_reason": "stop"
            }
        ]
        
        mock_execute.side_effect = [
            {"success": True, "result": ["test.txt", "other.txt"], "error": ""},
            {"success": True, "result": "File content", "error": ""}
        ]
        
        config = Config(workspace=".", model="gpt-4-turbo")
        result = run_agent_loop("List and read files", config=config, max_iterations=10)
        
        assert "Done" in result
        assert mock_call.call_count == 3
        assert mock_execute.call_count == 2

    @patch('guardcode.agent.call_model')
    @patch('guardcode.agent.execute_tool')
    @patch('guardcode.agent.init_workspace')
    def test_tool_failure_recovery(self, mock_init_ws, mock_execute, mock_call):
        """测试工具失败后恢复"""
        mock_call.side_effect = [
            # 第一次：尝试读取不存在的文件
            {
                "content": "Reading file...",
                "tool_calls": [
                    {
                        "id": "call_1",
                        "name": "read_file",
                        "arguments": {"path": "nonexistent.txt"}
                    }
                ],
                "finish_reason": "tool_calls"
            },
            # 第二次：尝试其他方法
            {
                "content": "File not found, creating it.",
                "tool_calls": [
                    {
                        "id": "call_2",
                        "name": "write_file",
                        "arguments": {"path": "nonexistent.txt", "content": "New content"}
                    }
                ],
                "finish_reason": "tool_calls"
            },
            # 第三次：完成
            {
                "content": "File created successfully.",
                "tool_calls": [],
                "finish_reason": "stop"
            }
        ]
        
        mock_execute.side_effect = [
            {"success": False, "result": "", "error": "File not found"},
            {"success": True, "result": "Written", "error": ""}
        ]
        
        config = Config(workspace=".", model="gpt-4-turbo")
        result = run_agent_loop("Handle missing file", config=config, max_iterations=10)
        
        assert "created successfully" in result
        assert mock_call.call_count == 3

    @patch('guardcode.agent.call_model')
    @patch('guardcode.agent.init_workspace')
    def test_max_iterations_reached(self, mock_init_ws, mock_call):
        """测试达到最大迭代次数"""
        # 模型每轮返回不同的工具调用（避免触发循环检测）
        mock_call.side_effect = [
            {
                "content": "Continuing...",
                "tool_calls": [{"id": "c1", "name": "list_files", "arguments": {"directory": "."}}],
                "finish_reason": "tool_calls"
            },
            {
                "content": "Continuing...",
                "tool_calls": [{"id": "c2", "name": "list_files", "arguments": {"directory": "src"}}],
                "finish_reason": "tool_calls"
            },
            {
                "content": "Continuing...",
                "tool_calls": [{"id": "c3", "name": "list_files", "arguments": {"directory": "tests"}}],
                "finish_reason": "tool_calls"
            },
        ]

        with patch('guardcode.agent.execute_tool') as mock_execute:
            mock_execute.return_value = {
                "success": True,
                "result": [],
                "error": ""
            }

            config = Config(workspace=".", model="gpt-4-turbo")
            result = run_agent_loop("Infinite task", config=config, max_iterations=3)

            assert "maximum iterations" in result
            assert mock_call.call_count == 3

    @patch('guardcode.agent.call_model')
    @patch('guardcode.agent.execute_tool')
    @patch('guardcode.agent.init_workspace')
    def test_loop_detection(self, mock_init_ws, mock_execute, mock_call):
        """测试循环检测：连续两轮相同工具调用 → 终止"""
        same_response = {
            "content": "Reading file...",
            "tool_calls": [{
                "id": "call_1",
                "name": "read_file",
                "arguments": {"path": "main.py"}
            }],
            "finish_reason": "tool_calls"
        }
        mock_call.side_effect = [same_response, same_response, same_response]

        mock_execute.return_value = {
            "success": True,
            "result": "file content",
            "error": ""
        }

        config = Config(workspace=".", model="gpt-4-turbo")
        result = run_agent_loop("Read main.py repeatedly", config=config, max_iterations=10)

        assert "loop detected" in result
        # 应该在第2轮就检测到循环并终止（第1轮记录，第2轮相同→终止）
        assert mock_call.call_count == 2

    @patch('guardcode.agent.call_model')
    @patch('guardcode.agent.execute_tool')
    @patch('guardcode.agent.init_workspace')
    def test_consecutive_failures(self, mock_init_ws, mock_execute, mock_call):
        """测试连续失败超限"""
        # 每轮返回不同的文件路径（避免触发循环检测）
        mock_call.side_effect = [
            {
                "content": "Trying...",
                "tool_calls": [{"id": "c1", "name": "read_file", "arguments": {"path": "bad1.txt"}}],
                "finish_reason": "tool_calls"
            },
            {
                "content": "Trying...",
                "tool_calls": [{"id": "c2", "name": "read_file", "arguments": {"path": "bad2.txt"}}],
                "finish_reason": "tool_calls"
            },
            {
                "content": "Trying...",
                "tool_calls": [{"id": "c3", "name": "read_file", "arguments": {"path": "bad3.txt"}}],
                "finish_reason": "tool_calls"
            },
        ]

        # 工具一直失败
        mock_execute.return_value = {
            "success": False,
            "result": "",
            "error": "File not found"
        }

        config = Config(workspace=".", model="gpt-4-turbo")
        result = run_agent_loop("Read bad file", config=config, max_iterations=10)

        assert "consecutive failures" in result
        # 应该在 3 次连续失败后停止
        assert mock_execute.call_count == 3

    @patch('guardcode.agent.call_model')
    @patch('guardcode.agent.init_workspace')
    def test_model_call_failure(self, mock_init_ws, mock_call):
        """测试模型调用失败"""
        # 模型调用抛出异常
        mock_call.side_effect = Exception("API Error")
        
        config = Config(workspace=".", model="gpt-4-turbo")
        result = run_agent_loop("Test task", config=config, max_iterations=5)
        
        assert "consecutive failures" in result
        # 应该尝试 3 次后停止
        assert mock_call.call_count == 3

    @patch('guardcode.agent.call_model')
    @patch('guardcode.agent.execute_tool')
    @patch('guardcode.agent.init_workspace')
    def test_model_failure_then_success(self, mock_init_ws, mock_execute, mock_call):
        """测试模型失败后恢复"""
        # 前两次失败，第三次成功
        mock_call.side_effect = [
            Exception("Timeout"),
            Exception("Network Error"),
            {
                "content": "Success!",
                "tool_calls": [],
                "finish_reason": "stop"
            }
        ]
        
        config = Config(workspace=".", model="gpt-4-turbo")
        result = run_agent_loop("Test recovery", config=config, max_iterations=10)
        
        assert result == "Success!"
        assert mock_call.call_count == 3

    @patch('guardcode.agent.call_model')
    @patch('guardcode.agent.execute_tool')
    @patch('guardcode.agent.init_workspace')
    def test_multiple_tools_in_one_call(self, mock_init_ws, mock_execute, mock_call):
        """测试一次调用多个工具"""
        mock_call.side_effect = [
            # 一次返回多个工具调用
            {
                "content": "Processing...",
                "tool_calls": [
                    {
                        "id": "call_1",
                        "name": "list_files",
                        "arguments": {"directory": "."}
                    },
                    {
                        "id": "call_2",
                        "name": "read_file",
                        "arguments": {"path": "test.txt"}
                    }
                ],
                "finish_reason": "tool_calls"
            },
            {
                "content": "All done!",
                "tool_calls": [],
                "finish_reason": "stop"
            }
        ]
        
        mock_execute.side_effect = [
            {"success": True, "result": ["test.txt"], "error": ""},
            {"success": True, "result": "Content", "error": ""}
        ]
        
        config = Config(workspace=".", model="gpt-4-turbo")
        result = run_agent_loop("Multi-tool task", config=config, max_iterations=5)
        
        assert result == "All done!"
        assert mock_execute.call_count == 2


class TestEventDrivenInvalidation:
    """测试事件驱动写后失效（不等阈值触发）"""

    @patch('guardcode.agent.call_model')
    @patch('guardcode.agent.execute_tool')
    @patch('guardcode.agent.init_workspace')
    def test_write_invalidates_old_read_immediately(
        self, mock_init_ws, mock_execute, mock_call
    ):
        """write_file 成功后立即失效旧 read_file 结果"""
        mock_call.side_effect = [
            # 第一次：读取文件
            {
                "content": "Reading file...",
                "tool_calls": [{
                    "id": "call_1",
                    "name": "read_file",
                    "arguments": {"path": "main.py"}
                }],
                "finish_reason": "tool_calls"
            },
            # 第二次：写入文件（触发失效）
            {
                "content": "Modifying file...",
                "tool_calls": [{
                    "id": "call_2",
                    "name": "write_file",
                    "arguments": {"path": "main.py", "content": "new content"}
                }],
                "finish_reason": "tool_calls"
            },
            # 第三次：完成
            {
                "content": "Done.",
                "tool_calls": [],
                "finish_reason": "stop"
            },
        ]
        mock_execute.side_effect = [
            {"success": True, "result": "old file content", "error": ""},
            {"success": True, "result": "Successfully wrote to main.py", "error": ""},
        ]

        config = Config(workspace=".", model="gpt-4-turbo")
        result = run_agent_loop("Read and modify main.py", config=config, max_iterations=10)

        assert result == "Done."
        # 第三次调用模型时，messages 中的旧 read_file 应已被失效
        third_call_messages = mock_call.call_args_list[2][0][0]
        for msg in third_call_messages:
            if msg.get("role") == "tool" and msg.get("tool_call_id") == "call_1":
                content = json.loads(msg["content"])
                assert content.get("compressed") is True
                assert "modified later" in content["result"]
                break
        else:
            pytest.fail("Old read_file result not found in messages")

    @patch('guardcode.agent.call_model')
    @patch('guardcode.agent.execute_tool')
    @patch('guardcode.agent.init_workspace')
    def test_delete_invalidates_old_read_immediately(
        self, mock_init_ws, mock_execute, mock_call
    ):
        """delete_file 成功后立即失效旧 read_file 结果"""
        mock_call.side_effect = [
            {
                "content": "Reading...",
                "tool_calls": [{
                    "id": "call_1",
                    "name": "read_file",
                    "arguments": {"path": "temp.py"}
                }],
                "finish_reason": "tool_calls"
            },
            {
                "content": "Deleting...",
                "tool_calls": [{
                    "id": "call_2",
                    "name": "delete_file",
                    "arguments": {"path": "temp.py"}
                }],
                "finish_reason": "tool_calls"
            },
            {
                "content": "Done.",
                "tool_calls": [],
                "finish_reason": "stop"
            },
        ]
        mock_execute.side_effect = [
            {"success": True, "result": "temp content", "error": ""},
            {"success": True, "result": "Successfully deleted temp.py", "error": ""},
        ]

        config = Config(workspace=".", model="gpt-4-turbo")
        result = run_agent_loop("Read and delete temp.py", config=config, max_iterations=10)

        assert result == "Done."
        third_call_messages = mock_call.call_args_list[2][0][0]
        for msg in third_call_messages:
            if msg.get("role") == "tool" and msg.get("tool_call_id") == "call_1":
                content = json.loads(msg["content"])
                assert content.get("compressed") is True
                assert "modified later" in content["result"]
                break
        else:
            pytest.fail("Old read_file result not found in messages")

    @patch('guardcode.agent.call_model')
    @patch('guardcode.agent.execute_tool')
    @patch('guardcode.agent.init_workspace')
    def test_failed_write_does_not_invalidate(
        self, mock_init_ws, mock_execute, mock_call
    ):
        """失败的 write_file 不触发失效"""
        mock_call.side_effect = [
            {
                "content": "Reading...",
                "tool_calls": [{
                    "id": "call_1",
                    "name": "read_file",
                    "arguments": {"path": "main.py"}
                }],
                "finish_reason": "tool_calls"
            },
            {
                "content": "Writing...",
                "tool_calls": [{
                    "id": "call_2",
                    "name": "write_file",
                    "arguments": {"path": "main.py", "content": "new"}
                }],
                "finish_reason": "tool_calls"
            },
            {
                "content": "Done.",
                "tool_calls": [],
                "finish_reason": "stop"
            },
        ]
        mock_execute.side_effect = [
            {"success": True, "result": "old content", "error": ""},
            {"success": False, "result": "", "error": "Permission denied"},
        ]

        config = Config(workspace=".", model="gpt-4-turbo")
        result = run_agent_loop("Read and try to write main.py", config=config, max_iterations=10)

        assert result == "Done."
        # 第三次调用模型时，旧 read_file 应保持不变（未被失效）
        third_call_messages = mock_call.call_args_list[2][0][0]
        for msg in third_call_messages:
            if msg.get("role") == "tool" and msg.get("tool_call_id") == "call_1":
                content = json.loads(msg["content"])
                assert "compressed" not in content
                assert content["result"] == "old content"
                break
        else:
            pytest.fail("Old read_file result not found in messages")

    @patch('guardcode.agent.call_model')
    @patch('guardcode.agent.execute_tool')
    @patch('guardcode.agent.init_workspace')
    def test_write_without_prior_read_no_side_effect(
        self, mock_init_ws, mock_execute, mock_call
    ):
        """无旧读取时，write_file 不产生副作用"""
        mock_call.side_effect = [
            {
                "content": "Writing...",
                "tool_calls": [{
                    "id": "call_1",
                    "name": "write_file",
                    "arguments": {"path": "new.py", "content": "hello"}
                }],
                "finish_reason": "tool_calls"
            },
            {
                "content": "Done.",
                "tool_calls": [],
                "finish_reason": "stop"
            },
        ]
        mock_execute.side_effect = [
            {"success": True, "result": "Successfully wrote to new.py", "error": ""},
        ]

        config = Config(workspace=".", model="gpt-4-turbo")
        result = run_agent_loop("Create new.py", config=config, max_iterations=10)

        assert result == "Done."
        assert mock_execute.call_count == 1

    @patch('guardcode.agent.call_model')
    @patch('guardcode.agent.execute_tool')
    @patch('guardcode.agent.init_workspace')
    def test_read_compresses_old_large_reads_immediately(
        self, mock_init_ws, mock_execute, mock_call
    ):
        """read_file 成功后立即压缩旧的大型读取结果"""
        large_content = "x" * 600  # 超过 500 阈值
        mock_call.side_effect = [
            # 第一次：读取大文件
            {
                "content": "Reading big file...",
                "tool_calls": [{
                    "id": "call_1",
                    "name": "read_file",
                    "arguments": {"path": "big.py"}
                }],
                "finish_reason": "tool_calls"
            },
            # 第二次：读取另一个文件（触发旧读取压缩）
            {
                "content": "Reading another file...",
                "tool_calls": [{
                    "id": "call_2",
                    "name": "read_file",
                    "arguments": {"path": "small.py"}
                }],
                "finish_reason": "tool_calls"
            },
            # 第三次：完成
            {
                "content": "Done.",
                "tool_calls": [],
                "finish_reason": "stop"
            },
        ]
        mock_execute.side_effect = [
            {"success": True, "result": large_content, "error": ""},
            {"success": True, "result": "small content", "error": ""},
        ]

        config = Config(workspace=".", model="gpt-4-turbo")
        result = run_agent_loop("Read big.py then small.py", config=config, max_iterations=10)

        assert result == "Done."
        # 第三次调用模型时，第一次的 read_file 结果应已被压缩
        third_call_messages = mock_call.call_args_list[2][0][0]
        for msg in third_call_messages:
            if msg.get("role") == "tool" and msg.get("tool_call_id") == "call_1":
                content = json.loads(msg["content"])
                assert content.get("compressed") is True
                assert content["result"] == "<content: 600 chars>"
                break
        else:
            pytest.fail("Old read_file result not found in messages")

    @patch('guardcode.agent.call_model')
    @patch('guardcode.agent.execute_tool')
    @patch('guardcode.agent.init_workspace')
    def test_read_preserves_latest_read(
        self, mock_init_ws, mock_execute, mock_call
    ):
        """read_file 后，最新一轮的读取结果保持完整"""
        large_content = "x" * 600
        mock_call.side_effect = [
            {
                "content": "Reading...",
                "tool_calls": [{
                    "id": "call_1",
                    "name": "read_file",
                    "arguments": {"path": "a.py"}
                }],
                "finish_reason": "tool_calls"
            },
            {
                "content": "Done.",
                "tool_calls": [],
                "finish_reason": "stop"
            },
        ]
        mock_execute.side_effect = [
            {"success": True, "result": large_content, "error": ""},
        ]

        config = Config(workspace=".", model="gpt-4-turbo")
        result = run_agent_loop("Read a.py", config=config, max_iterations=10)

        assert result == "Done."
        # 第二次调用模型时，read_file 结果应保持完整（没有更早的读取需要压缩）
        second_call_messages = mock_call.call_args_list[1][0][0]
        for msg in second_call_messages:
            if msg.get("role") == "tool" and msg.get("tool_call_id") == "call_1":
                content = json.loads(msg["content"])
                assert "compressed" not in content
                assert content["result"] == large_content
                break
        else:
            pytest.fail("read_file result not found in messages")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
