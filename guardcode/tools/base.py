"""
工具系统基础设施

提供工具注册、schema 生成和执行机制。
使用 Rich 格式化输出显示被阻止的操作。
"""

import inspect
from typing import Dict, Any, Callable, List, Optional
from functools import wraps

# 安全模块（延迟导入避免循环依赖）
from ..security import classify_risk, confirm_operation, format_blocked_message, RiskLevel
from ..ui.console import print_blocked


# 全局工具注册表
_tool_registry: Dict[str, Dict[str, Any]] = {}


def register_tool(
    name: str,
    description: str,
    parameters: Optional[Dict[str, Any]] = None
):
    """
    工具注册装饰器
    
    Args:
        name: 工具名称
        description: 工具描述
        parameters: 参数 schema（可选，如果不提供则自动生成）
    
    Example:
        @register_tool(
            name="read_file",
            description="Read contents of a file",
            parameters={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path to the file"
                    }
                },
                "required": ["path"]
            }
        )
        def read_file(path: str) -> dict:
            ...
    """
    def decorator(func: Callable) -> Callable:
        # 如果没有提供参数 schema，尝试自动生成
        param_schema = parameters
        if param_schema is None:
            param_schema = _generate_parameter_schema(func)
        
        # 注册工具
        _tool_registry[name] = {
            "name": name,
            "description": description,
            "parameters": param_schema,
            "function": func
        }
        
        @wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)
        
        return wrapper
    
    return decorator


def _generate_parameter_schema(func: Callable) -> Dict[str, Any]:
    """
    自动生成参数 schema（基于函数签名）
    
    Args:
        func: 函数对象
        
    Returns:
        OpenAI 函数参数 schema
    """
    sig = inspect.signature(func)
    properties = {}
    required = []
    
    # 类型映射
    type_mapping = {
        str: "string",
        int: "integer",
        float: "number",
        bool: "boolean",
        list: "array",
        dict: "object"
    }
    
    for param_name, param in sig.parameters.items():
        # 跳过 self 和 cls
        if param_name in ('self', 'cls'):
            continue
        
        # 获取类型注解
        param_type = param.annotation
        if param_type == inspect.Parameter.empty:
            param_type = str  # 默认为 string
        
        # 转换为 JSON schema 类型
        json_type = type_mapping.get(param_type, "string")
        
        properties[param_name] = {
            "type": json_type,
            "description": f"Parameter {param_name}"
        }
        
        # 检查是否必需（没有默认值）
        if param.default == inspect.Parameter.empty:
            required.append(param_name)
    
    schema = {
        "type": "object",
        "properties": properties
    }
    
    if required:
        schema["required"] = required
    
    return schema


def generate_tool_schema(tool_name: str) -> Dict[str, Any]:
    """
    生成单个工具的 OpenAI function schema
    
    Args:
        tool_name: 工具名称
        
    Returns:
        OpenAI function schema
        
    Raises:
        KeyError: 如果工具未注册
    """
    if tool_name not in _tool_registry:
        raise KeyError(f"Tool '{tool_name}' not registered")
    
    tool_info = _tool_registry[tool_name]
    
    return {
        "type": "function",
        "function": {
            "name": tool_info["name"],
            "description": tool_info["description"],
            "parameters": tool_info["parameters"]
        }
    }


def get_tool_schemas() -> List[Dict[str, Any]]:
    """
    返回所有已注册工具的 schema
    
    Returns:
        工具 schema 列表（OpenAI tools 格式）
    """
    return [generate_tool_schema(name) for name in _tool_registry.keys()]


def _extract_security_config(config: Any) -> Dict[str, Any]:
    """将 Config 对象或 dict 转换为 classify_risk 需要的格式。"""
    if isinstance(config, dict):
        return config

    # Config 对象
    if hasattr(config, "security"):
        security = config.security
        return {
            "security": {
                "always_block": getattr(security, "always_block", []),
                "auto_approve": getattr(security, "auto_approve", []),
            }
        }

    return {}


def execute_tool(
    name: str,
    args: Dict[str, Any],
    config: Any = None,
) -> Dict[str, Any]:
    """
    执行指定的工具

    如果传入 config，会在执行前进行风险分级：
    - BLOCKED：直接拒绝，返回错误
    - DANGEROUS：调用 confirm_operation 等待用户确认
    - SAFE：直接执行

    Args:
        name: 工具名称
        args: 工具参数
        config: 配置对象（Config 或 dict），可选

    Returns:
        工具执行结果（统一格式：{"success": bool, "result": Any, "error": str}）
    """
    if name not in _tool_registry:
        return {
            "success": False,
            "result": None,
            "error": f"Tool '{name}' not found",
        }

    # 风险分级（fail-safe：config 为 None 时用空配置，
    # classify_risk 会将未知操作默认判为 DANGEROUS）
    security_config = _extract_security_config(config) if config is not None else {}
    risk_level = classify_risk(name, args, security_config)

    if risk_level == RiskLevel.BLOCKED:
        print_blocked(name, args)
        return {
            "success": False,
            "result": None,
            "error": "Operation blocked by security policy",
        }

    if risk_level == RiskLevel.DANGEROUS:
        if not confirm_operation(name, args):
                return {
                    "success": False,
                    "result": None,
                    "error": "Operation rejected by user",
                }

    tool_func = _tool_registry[name]["function"]

    try:
        result = tool_func(**args)

        # 如果工具返回的已经是标准格式，直接返回
        if isinstance(result, dict) and "success" in result:
            return result

        # 否则包装成标准格式
        return {
            "success": True,
            "result": result,
            "error": ""
        }
    except Exception as e:
        return {
            "success": False,
            "result": None,
            "error": str(e)
        }


def get_registered_tools() -> List[str]:
    """
    获取所有已注册的工具名称
    
    Returns:
        工具名称列表
    """
    return list(_tool_registry.keys())


def get_tool_info(name: str) -> Dict[str, Any]:
    """
    获取工具的详细信息
    
    Args:
        name: 工具名称
        
    Returns:
        工具信息字典
        
    Raises:
        KeyError: 如果工具未注册
    """
    if name not in _tool_registry:
        raise KeyError(f"Tool '{name}' not registered")
    
    info = _tool_registry[name].copy()
    # 不返回函数对象本身
    info.pop("function", None)
    return info
