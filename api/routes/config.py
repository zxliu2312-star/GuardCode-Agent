"""
配置管理 REST 路由

提供：
- 浏览本地文件系统（选择工作区）
- 模型配置 CRUD
- 任务 CRUD
- 工作区设置 CRUD
- 应用设置
"""

import os
import uuid
from pathlib import Path
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional, List

from api import database as db

router = APIRouter()


# ──────────────────────────────────────────────────────────
# 浏览本地文件系统
# ──────────────────────────────────────────────────────────

@router.get("/browse")
async def browse_directories(
    path: str = Query(default=""),
):
    """浏览本地文件系统目录

    返回指定路径下的子目录列表，用于选择工作区。
    如果 path 为空，返回常见根目录（Windows: 盘符列表）。
    """
    try:
        if not path or path == "":
            # Windows: 列出所有盘符
            if os.name == 'nt':
                drives = []
                for letter in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ':
                    drive = f'{letter}:\\'
                    if os.path.exists(drive):
                        drives.append({
                            'name': f'本地磁盘 ({letter}:)',
                            'path': drive,
                            'type': 'directory',
                        })
                # 也加入用户主目录
                home = str(Path.home())
                drives.insert(0, {
                    'name': f'主目录 ({home})',
                    'path': home,
                    'type': 'directory',
                })
                return {"path": "", "entries": drives}
            else:
                # Linux/Mac: 从根目录开始
                path = "/"

        target = Path(path).resolve()
        if not target.exists():
            raise HTTPException(404, f"路径不存在: {path}")
        if not target.is_dir():
            raise HTTPException(400, f"路径不是目录: {path}")

        entries = []
        try:
            for item in sorted(target.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower())):
                if item.name.startswith('.') and item.name not in ('.', '..'):
                    # 跳过隐藏文件（但保留 . 开头的工作区配置等）
                    continue
                if item.is_dir():
                    entries.append({
                        'name': item.name,
                        'path': str(item),
                        'type': 'directory',
                    })
        except PermissionError:
            raise HTTPException(403, f"无权限访问: {path}")

        # 返回父目录信息
        parent = str(target.parent) if str(target.parent) != str(target) else None

        return {
            "path": str(target),
            "parent": parent,
            "entries": entries,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))


class SelectWorkspaceRequest(BaseModel):
    path: str
    is_favorite: bool = False


@router.post("/browse/select")
async def select_workspace(req: SelectWorkspaceRequest):
    """选择工作区（确认选中）"""
    try:
        path = Path(req.path).resolve()
        if not path.exists():
            raise HTTPException(404, f"路径不存在: {req.path}")
        if not path.is_dir():
            raise HTTPException(400, f"路径不是目录: {req.path}")

        # 保存到数据库
        display_name = path.name or str(path)
        result = db.save_workspace(
            path=str(path),
            display_name=display_name,
            is_favorite=req.is_favorite,
        )

        return {
            "success": True,
            "path": str(path),
            "display_name": display_name,
            "workspace": result,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))


# ──────────────────────────────────────────────────────────
# 模型配置 CRUD
# ──────────────────────────────────────────────────────────

class ModelConfigRequest(BaseModel):
    name: str
    api_base: str
    api_key: str
    model_name: str
    is_built_in: bool = False


@router.get("/models")
async def list_models():
    """列出所有模型配置"""
    configs = db.list_model_configs()
    return {"models": configs}


@router.post("/models")
async def create_model(req: ModelConfigRequest):
    """创建自定义模型配置"""
    existing = db.get_model_config_by_name(req.name)
    config_id = existing["id"] if existing and not existing["is_built_in"] else f"model-{uuid.uuid4().hex[:12]}"
    result = db.save_model_config(
        config_id=config_id,
        name=req.name,
        api_base=req.api_base,
        api_key=req.api_key,
        model_name=req.model_name,
        is_built_in=req.is_built_in,
    )
    return {"model": result}


@router.put("/models/{config_id}")
async def update_model(config_id: str, req: ModelConfigRequest):
    """更新模型配置"""
    existing = db.get_model_config(config_id)
    if not existing:
        raise HTTPException(404, "模型配置不存在")
    result = db.save_model_config(
        config_id=config_id,
        name=req.name,
        api_base=req.api_base,
        api_key=req.api_key,
        model_name=req.model_name,
        is_built_in=existing.get("is_built_in", False),
    )
    return {"model": result}


@router.delete("/models/{config_id}")
async def delete_model(config_id: str):
    """删除模型配置（不能删除内置模型）"""
    success = db.delete_model_config(config_id)
    if not success:
        raise HTTPException(400, "无法删除（可能是内置模型或配置不存在）")
    return {"success": True}


# ──────────────────────────────────────────────────────────
# 任务 CRUD
# ──────────────────────────────────────────────────────────

class TaskRequest(BaseModel):
    name: str
    workspace: str
    mode: str = "WORK"
    status: str = "pending"
    session_id: Optional[str] = None
    last_message: Optional[str] = None


@router.get("/tasks")
async def list_tasks():
    """列出所有任务"""
    tasks = db.list_tasks()
    return {"tasks": tasks}


@router.post("/tasks")
async def create_task(req: TaskRequest):
    """创建任务"""
    task_id = f"task-{uuid.uuid4().hex[:12]}"
    result = db.save_task(
        task_id=task_id,
        name=req.name,
        workspace=req.workspace,
        mode=req.mode,
        status=req.status,
        session_id=req.session_id,
        last_message=req.last_message,
    )
    return {"task": result}


@router.get("/tasks/{task_id}")
async def get_task(task_id: str):
    """获取单个任务"""
    task = db.get_task(task_id)
    if not task:
        raise HTTPException(404, "任务不存在")
    return {"task": task}


@router.put("/tasks/{task_id}")
async def update_task(task_id: str, req: TaskRequest):
    """更新任务"""
    existing = db.get_task(task_id)
    if not existing:
        raise HTTPException(404, "任务不存在")
    result = db.save_task(
        task_id=task_id,
        name=req.name,
        workspace=req.workspace,
        mode=req.mode,
        status=req.status,
        session_id=req.session_id,
        last_message=req.last_message,
    )
    return {"task": result}


@router.delete("/tasks/{task_id}")
async def delete_task(task_id: str):
    """删除任务"""
    success = db.delete_task(task_id)
    if not success:
        raise HTTPException(404, "任务不存在")
    return {"success": True}


class UpdateStatusRequest(BaseModel):
    status: str
    last_message: Optional[str] = None


@router.patch("/tasks/{task_id}/status")
async def update_task_status_route(task_id: str, req: UpdateStatusRequest):
    """更新任务状态"""
    db.update_task_status(task_id, req.status, req.last_message)
    return {"success": True}


# ──────────────────────────────────────────────────────────
# 工作区设置
# ──────────────────────────────────────────────────────────

@router.get("/workspaces")
async def list_workspaces():
    """列出所有工作区"""
    workspaces = db.list_workspaces()
    return {"workspaces": workspaces}


class WorkspaceRequest(BaseModel):
    path: str
    display_name: Optional[str] = None
    is_favorite: bool = False


@router.post("/workspaces")
async def save_workspace(req: WorkspaceRequest):
    """保存工作区"""
    result = db.save_workspace(
        path=req.path,
        display_name=req.display_name,
        is_favorite=req.is_favorite,
    )
    return {"workspace": result}


@router.delete("/workspaces")
async def delete_workspace(path: str = Query(...)):
    """删除工作区记录"""
    success = db.delete_workspace(path)
    if not success:
        raise HTTPException(404, "工作区不存在")
    return {"success": True}


# ──────────────────────────────────────────────────────────
# 应用设置
# ──────────────────────────────────────────────────────────

@router.get("/settings/{key}")
async def get_setting(key: str):
    """获取应用设置"""
    value = db.get_setting(key)
    return {"key": key, "value": value}


class SettingRequest(BaseModel):
    value: str


@router.post("/settings/{key}")
async def set_setting(key: str, req: SettingRequest):
    """设置应用设置"""
    db.set_setting(key, req.value)
    return {"key": key, "value": req.value}


# ──────────────────────────────────────────────────────────
# 规则 CRUD
# ──────────────────────────────────────────────────────────

class RuleRequest(BaseModel):
    name: str
    content: str
    is_enabled: bool = True


@router.get("/rules")
async def list_rules():
    """列出所有规则"""
    rules = db.list_rules()
    return {"rules": rules}


@router.post("/rules")
async def create_rule(req: RuleRequest):
    """创建规则"""
    result = db.create_rule(
        name=req.name,
        content=req.content,
        is_enabled=req.is_enabled,
    )
    return {"rule": result}


@router.put("/rules/{rule_id}")
async def update_rule(rule_id: str, req: RuleRequest):
    """更新规则"""
    result = db.update_rule(
        rule_id=rule_id,
        name=req.name,
        content=req.content,
        is_enabled=req.is_enabled,
    )
    if not result:
        raise HTTPException(404, "规则不存在")
    return {"rule": result}


@router.delete("/rules/{rule_id}")
async def delete_rule(rule_id: str):
    """删除规则"""
    success = db.delete_rule(rule_id)
    if not success:
        raise HTTPException(404, "规则不存在")
    return {"success": True}
