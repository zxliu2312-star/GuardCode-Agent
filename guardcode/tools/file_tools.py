"""
文件操作工具

提供文件读写、列表和删除功能，所有操作都在工作区边界内。
"""

from pathlib import Path
from typing import Dict, Any
from ..workspace import get_workspace
from .base import register_tool
from ..security import scan_python_code, format_scan_results


@register_tool(
    name="read_file",
    description="Read the contents of a file within the workspace",
    parameters={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path to the file to read (relative or absolute)"
            }
        },
        "required": ["path"]
    }
)
def read_file(path: str) -> Dict[str, Any]:
    """
    读取文件内容
    
    Args:
        path: 文件路径（相对或绝对）
        
    Returns:
        {"success": bool, "result": str, "error": str}
    """
    try:
        # 路径校验
        workspace = get_workspace()
        validated_path = workspace.validate_path(path)
        
        # 检查文件是否存在
        if not validated_path.exists():
            return {
                "success": False,
                "result": "",
                "error": f"File does not exist: {path}"
            }
        
        # 检查是否为文件
        if not validated_path.is_file():
            return {
                "success": False,
                "result": "",
                "error": f"Path is not a file: {path}"
            }
        
        # 读取文件内容
        try:
            content = validated_path.read_text(encoding='utf-8')
        except UnicodeDecodeError:
            # 尝试其他编码
            try:
                content = validated_path.read_text(encoding='gbk')
            except UnicodeDecodeError:
                return {
                    "success": False,
                    "result": "",
                    "error": f"Cannot decode file (not text or unknown encoding): {path}"
                }
        
        return {
            "success": True,
            "result": content,
            "error": ""
        }
        
    except ValueError as e:
        # 路径校验失败
        return {
            "success": False,
            "result": "",
            "error": str(e)
        }
    except Exception as e:
        return {
            "success": False,
            "result": "",
            "error": f"Failed to read file: {e}"
        }


@register_tool(
    name="write_file",
    description="Write content to a file within the workspace, creating parent directories if needed",
    parameters={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path to the file to write (relative or absolute)"
            },
            "content": {
                "type": "string",
                "description": "Content to write to the file"
            }
        },
        "required": ["path", "content"]
    }
)
def write_file(path: str, content: str) -> Dict[str, Any]:
    """
    写入文件内容

    如果文件是 .py 后缀，会先进行静态安全扫描。
    发现风险时提示用户选择继续或中止。

    Args:
        path: 文件路径（相对或绝对）
        content: 要写入的内容
        
    Returns:
        {"success": bool, "result": str, "error": str}
    """
    try:
        # 路径校验
        workspace = get_workspace()
        validated_path = workspace.validate_path(path)
        
        # 代码静态扫描（仅 .py 文件）
        if validated_path.suffix == ".py":
            risks = scan_python_code(content)
            if risks:
                print(format_scan_results(risks))
                print(f"  写入 {path} 前发现上述风险。")
                choice = input("  [c]ontinue / [a]bort: ").strip().lower()
                if choice != "c":
                    return {
                        "success": False,
                        "result": "",
                        "error": f"Write aborted: {len(risks)} security risk(s) detected in code",
                    }
        
        # 创建父目录（如果不存在）
        validated_path.parent.mkdir(parents=True, exist_ok=True)
        
        # 写入文件
        validated_path.write_text(content, encoding='utf-8')
        
        return {
            "success": True,
            "result": f"Successfully wrote to {path}",
            "error": ""
        }
        
    except ValueError as e:
        # 路径校验失败
        return {
            "success": False,
            "result": "",
            "error": str(e)
        }
    except Exception as e:
        return {
            "success": False,
            "result": "",
            "error": f"Failed to write file: {e}"
        }


@register_tool(
    name="list_files",
    description="List files and directories within a directory in the workspace",
    parameters={
        "type": "object",
        "properties": {
            "directory": {
                "type": "string",
                "description": "Directory path to list (relative or absolute, defaults to current directory)"
            }
        },
        "required": []
    }
)
def list_files(directory: str = ".") -> Dict[str, Any]:
    """
    列出目录中的文件和子目录
    
    Args:
        directory: 目录路径（相对或绝对），默认为当前目录
        
    Returns:
        {"success": bool, "result": list[str], "error": str}
    """
    try:
        # 路径校验
        workspace = get_workspace()
        validated_path = workspace.validate_path(directory)
        
        # 检查目录是否存在
        if not validated_path.exists():
            return {
                "success": False,
                "result": [],
                "error": f"Directory does not exist: {directory}"
            }
        
        # 检查是否为目录
        if not validated_path.is_dir():
            return {
                "success": False,
                "result": [],
                "error": f"Path is not a directory: {directory}"
            }
        
        # 列出文件和目录，返回相对于工作区的路径
        items = []
        for item in sorted(validated_path.iterdir()):
            try:
                # 获取相对于工作区的路径
                relative_path = workspace.get_relative_path(item)
                # 如果是目录，添加尾部斜杠
                if item.is_dir():
                    items.append(f"{relative_path}/")
                else:
                    items.append(str(relative_path))
            except Exception:
                # 跳过无法访问的项
                continue
        
        return {
            "success": True,
            "result": items,
            "error": ""
        }
        
    except ValueError as e:
        # 路径校验失败
        return {
            "success": False,
            "result": [],
            "error": str(e)
        }
    except Exception as e:
        return {
            "success": False,
            "result": [],
            "error": f"Failed to list directory: {e}"
        }


@register_tool(
    name="delete_file",
    description="Delete a file within the workspace",
    parameters={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path to the file to delete (relative or absolute)"
            }
        },
        "required": ["path"]
    }
)
def delete_file(path: str) -> Dict[str, Any]:
    """
    删除文件
    
    Args:
        path: 文件路径（相对或绝对）
        
    Returns:
        {"success": bool, "result": str, "error": str}
    """
    try:
        # 路径校验
        workspace = get_workspace()
        validated_path = workspace.validate_path(path)
        
        # 检查文件是否存在
        if not validated_path.exists():
            return {
                "success": False,
                "result": "",
                "error": f"File does not exist: {path}"
            }
        
        # 检查是否为文件
        if not validated_path.is_file():
            return {
                "success": False,
                "result": "",
                "error": f"Path is not a file (use delete_directory for directories): {path}"
            }
        
        # 删除文件
        validated_path.unlink()
        
        return {
            "success": True,
            "result": f"Successfully deleted {path}",
            "error": ""
        }
        
    except ValueError as e:
        # 路径校验失败
        return {
            "success": False,
            "result": "",
            "error": str(e)
        }
    except Exception as e:
        return {
            "success": False,
            "result": "",
            "error": f"Failed to delete file: {e}"
        }
