"""
配置管理模块

负责加载和管理 GuardCode Agent 的配置，支持：
- JSON 配置文件加载
- 环境变量覆盖
- 默认配置
- 全局配置和项目配置合并
"""

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, List, Dict, Any


@dataclass
class SecurityConfig:
    """安全配置"""
    always_block: List[str] = field(default_factory=list)
    auto_approve: List[str] = field(default_factory=list)


@dataclass
class ContextConfig:
    """上下文管理配置"""
    max_context_size: int = 100000  # 最大上下文字符数
    keep_recent_messages: int = 5    # 压缩时保留的最近消息数


@dataclass
class Config:
    """主配置类"""
    # API 配置
    api_key: str = ""
    api_base: str = "https://api.openai.com/v1"
    model: str = "gpt-4-turbo"
    
    # Agent 配置
    max_iterations: int = 10
    
    # 工作区配置
    workspace: str = "."
    
    # 子配置
    security: SecurityConfig = field(default_factory=SecurityConfig)
    context: ContextConfig = field(default_factory=ContextConfig)
    
    # 输出配置
    verbose: bool = False
    log_file: Optional[str] = None


def get_default_config() -> Config:
    """返回默认配置"""
    return Config()


def load_config_from_file(config_path: Path) -> Dict[str, Any]:
    """
    从 JSON 文件加载配置
    
    Args:
        config_path: 配置文件路径
        
    Returns:
        配置字典
    """
    if not config_path.exists():
        return {}
    
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        print(f"Warning: Failed to load config from {config_path}: {e}")
        return {}


def merge_configs(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """
    合并两个配置字典（递归）
    
    Args:
        base: 基础配置
        override: 覆盖配置
        
    Returns:
        合并后的配置
    """
    result = base.copy()
    
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = merge_configs(result[key], value)
        else:
            result[key] = value
    
    return result


def apply_env_overrides(config_dict: Dict[str, Any]) -> Dict[str, Any]:
    """
    应用环境变量覆盖
    
    支持的环境变量：
    - OPENAI_API_KEY -> api_key
    - OPENAI_API_BASE -> api_base
    - GUARDCODE_MODEL -> model
    - GUARDCODE_MAX_ITERATIONS -> max_iterations
    - GUARDCODE_VERBOSE -> verbose
    
    Args:
        config_dict: 配置字典
        
    Returns:
        应用环境变量后的配置
    """
    result = config_dict.copy()
    
    # API 配置
    if os.getenv('OPENAI_API_KEY'):
        result['api_key'] = os.getenv('OPENAI_API_KEY')
    
    if os.getenv('OPENAI_API_BASE'):
        result['api_base'] = os.getenv('OPENAI_API_BASE')
    
    # Agent 配置
    if os.getenv('GUARDCODE_MODEL'):
        result['model'] = os.getenv('GUARDCODE_MODEL')
    
    if os.getenv('GUARDCODE_MAX_ITERATIONS'):
        try:
            result['max_iterations'] = int(os.getenv('GUARDCODE_MAX_ITERATIONS'))
        except ValueError:
            pass
    
    # 输出配置
    if os.getenv('GUARDCODE_VERBOSE'):
        result['verbose'] = os.getenv('GUARDCODE_VERBOSE').lower() in ('1', 'true', 'yes')
    
    return result


def dict_to_config(config_dict: Dict[str, Any]) -> Config:
    """
    将配置字典转换为 Config 对象
    
    Args:
        config_dict: 配置字典
        
    Returns:
        Config 对象
    """
    # 处理嵌套的 security 配置
    security_dict = config_dict.get('security', {})
    security = SecurityConfig(
        always_block=security_dict.get('always_block', []),
        auto_approve=security_dict.get('auto_approve', [])
    )
    
    # 处理嵌套的 context 配置
    context_dict = config_dict.get('context', {})
    context = ContextConfig(
        max_context_size=context_dict.get('max_context_size', 100000),
        keep_recent_messages=context_dict.get('keep_recent_messages', 5)
    )
    
    # 构建主配置
    return Config(
        api_key=config_dict.get('api_key', ''),
        api_base=config_dict.get('api_base', 'https://api.openai.com/v1'),
        model=config_dict.get('model', 'gpt-4-turbo'),
        max_iterations=config_dict.get('max_iterations', 10),
        workspace=config_dict.get('workspace', '.'),
        security=security,
        context=context,
        verbose=config_dict.get('verbose', False),
        log_file=config_dict.get('log_file')
    )


def load_config(
    config_file: Optional[str] = None,
    workspace: Optional[str] = None
) -> Config:
    """
    加载完整配置
    
    加载顺序（后面的覆盖前面的）：
    1. 默认配置
    2. 全局配置文件 (~/.guardcode/config.json)
    3. 项目配置文件 ({workspace}/.guardcode.json)
    4. 命令行指定的配置文件
    5. 环境变量
    
    Args:
        config_file: 命令行指定的配置文件路径
        workspace: 工作区路径
        
    Returns:
        Config 对象
    """
    # 1. 默认配置
    config_dict = {}
    
    # 2. 全局配置
    global_config_path = Path.home() / '.guardcode' / 'config.json'
    if global_config_path.exists():
        global_config = load_config_from_file(global_config_path)
        config_dict = merge_configs(config_dict, global_config)
    
    # 3. 项目配置
    if workspace:
        project_config_path = Path(workspace) / '.guardcode.json'
        if project_config_path.exists():
            project_config = load_config_from_file(project_config_path)
            config_dict = merge_configs(config_dict, project_config)
    
    # 4. 命令行指定的配置文件
    if config_file:
        user_config_path = Path(config_file)
        if user_config_path.exists():
            user_config = load_config_from_file(user_config_path)
            config_dict = merge_configs(config_dict, user_config)
    
    # 5. 环境变量覆盖
    config_dict = apply_env_overrides(config_dict)
    
    # 转换为 Config 对象
    return dict_to_config(config_dict)
