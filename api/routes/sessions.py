"""会话管理 REST 路由"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from api.agent_adapter import create_session, get_session, list_sessions
from api import database as db

router = APIRouter()


class CreateSessionRequest(BaseModel):
    workspace: str
    mode: str = "WORK"  # PLAN / WORK / FEEDBACK / RESEARCH


class StartTaskRequest(BaseModel):
    task: str
    model: Optional[str] = None
    api_base: Optional[str] = None
    api_key: Optional[str] = None


class SaveMessageRequest(BaseModel):
    id: str
    type: str
    content: Optional[str] = None
    timestamp: int
    metadata: Optional[dict] = None


@router.post("/sessions")
async def create_session_endpoint(req: CreateSessionRequest):
    """创建新会话"""
    session = create_session(req.workspace, req.mode)
    return {
        "session_id": session.session_id,
        "workspace": session.workspace,
        "mode": session.mode,
    }


@router.get("/sessions")
async def list_sessions_endpoint():
    """列出所有会话"""
    return list_sessions()


@router.get("/sessions/{session_id}")
async def get_session_endpoint(session_id: str):
    """获取会话状态"""
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return {
        "session_id": session.session_id,
        "workspace": session.workspace,
        "mode": session.mode,
        "is_running": session.is_running,
    }


@router.post("/sessions/{session_id}/start")
async def start_task_endpoint(session_id: str, req: StartTaskRequest):
    """启动 Agent 任务"""
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.is_running:
        raise HTTPException(status_code=400, detail="Session is already running")

    session.start(req.task, model=req.model, api_base=req.api_base, api_key=req.api_key)
    return {"status": "started", "session_id": session_id}


@router.post("/sessions/{session_id}/stop")
async def stop_session_endpoint(session_id: str):
    """停止 Agent"""
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    session.stop()
    return {"status": "stopped", "session_id": session_id}


@router.get("/tasks/{task_id}/messages")
async def get_task_messages_endpoint(task_id: str, limit: Optional[int] = None):
    """获取任务的历史消息"""
    messages = db.get_task_messages(task_id, limit)
    return {"messages": messages}


@router.post("/tasks/{task_id}/messages")
async def save_message_endpoint(task_id: str, req: SaveMessageRequest):
    """保存消息到任务历史"""
    message = db.save_message(
        message_id=req.id,
        task_id=task_id,
        msg_type=req.type,
        content=req.content,
        timestamp=req.timestamp,
        metadata=req.metadata,
    )
    return {"message": message}


@router.delete("/tasks/{task_id}/messages")
async def delete_task_messages_endpoint(task_id: str):
    """删除任务的所有消息"""
    count = db.delete_task_messages(task_id)
    return {"deleted": count}
