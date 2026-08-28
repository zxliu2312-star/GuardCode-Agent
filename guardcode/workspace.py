"""
工作区管理模块

负责工作区的初始化和路径校验，确保所有文件操作都在工作区边界内。
"""

from pathlib import Path
from typing import Optional


class WorkspaceManager:
    """工作区管理器"""
    
    def __init__(self, workspace_path: str = "."):
        """
        初始化工作区管理器
        
        Args:
            workspace_path: 工作区路径（相对或绝对）
        """
        self.workspace_root = self._resolve_workspace(workspace_path)
    
    def _resolve_workspace(self, workspace_path: str) -> Path:
        """
        解析工作区路径为绝对路径
        
        Args:
            workspace_path: 工作区路径
            
        Returns:
            绝对路径的 Path 对象
        """
        # 转换为 Path 对象
        path = Path(workspace_path)
        
        # 获取绝对路径
        abs_path = path.resolve()
        
        # 确保目录存在
        if not abs_path.exists():
            raise ValueError(f"Workspace directory does not exist: {abs_path}")
        
        if not abs_path.is_dir():
            raise ValueError(f"Workspace path is not a directory: {abs_path}")
        
        return abs_path
    
    def validate_path(self, path: str) -> Path:
        """
        校验路径并返回规范化的 Path 对象
        
        功能：
        1. 支持相对路径和绝对路径
        2. 消解符号链接
        3. 检查是否在 workspace 内
        4. 返回规范化的 Path 对象
        
        Args:
            path: 要校验的路径（相对或绝对）
            
        Returns:
            规范化的 Path 对象
            
        Raises:
            ValueError: 如果路径在工作区外
        """
        # 转换为 Path 对象
        target_path = Path(path)
        
        # 如果是相对路径，相对于工作区解析
        if not target_path.is_absolute():
            target_path = self.workspace_root / target_path
        
        # 消解符号链接，获取真实路径
        try:
            resolved_path = target_path.resolve()
        except (OSError, RuntimeError) as e:
            raise ValueError(f"Cannot resolve path {path}: {e}")
        
        # 检查是否在工作区内
        try:
            # 尝试获取相对于工作区的路径
            resolved_path.relative_to(self.workspace_root)
        except ValueError:
            raise ValueError(
                f"Path is outside workspace boundary:\n"
                f"  Path: {resolved_path}\n"
                f"  Workspace: {self.workspace_root}"
            )
        
        return resolved_path
    
    def get_relative_path(self, path: Path) -> Path:
        """
        获取相对于工作区的路径
        
        Args:
            path: 绝对路径
            
        Returns:
            相对于工作区的路径
        """
        return path.relative_to(self.workspace_root)
    
    def is_within_workspace(self, path: str) -> bool:
        """
        检查路径是否在工作区内（不抛出异常）
        
        Args:
            path: 要检查的路径
            
        Returns:
            True 如果在工作区内，否则 False
        """
        try:
            self.validate_path(path)
            return True
        except ValueError:
            return False


# 全局工作区管理器实例
_workspace_manager: Optional[WorkspaceManager] = None


def init_workspace(workspace_path: str = ".") -> WorkspaceManager:
    """
    初始化全局工作区管理器
    
    Args:
        workspace_path: 工作区路径
        
    Returns:
        WorkspaceManager 实例
    """
    global _workspace_manager
    _workspace_manager = WorkspaceManager(workspace_path)
    return _workspace_manager


def get_workspace() -> WorkspaceManager:
    """
    获取全局工作区管理器
    
    Returns:
        WorkspaceManager 实例
        
    Raises:
        RuntimeError: 如果工作区未初始化
    """
    if _workspace_manager is None:
        raise RuntimeError("Workspace not initialized. Call init_workspace() first.")
    return _workspace_manager


def validate_path(path: str) -> Path:
    """
    校验路径的便捷函数
    
    Args:
        path: 要校验的路径
        
    Returns:
        规范化的 Path 对象
    """
    return get_workspace().validate_path(path)
