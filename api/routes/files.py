"""文件操作 REST 路由"""

import os
from pathlib import Path
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional

from guardcode.workspace import init_workspace, get_workspace, WorkspaceManager

router = APIRouter()


class WriteFileRequest(BaseModel):
    path: str
    content: str


def _get_workspace_manager(workspace_path: str) -> WorkspaceManager:
    """获取工作区管理器"""
    return WorkspaceManager(workspace_path)


@router.get("/files")
async def get_files(
    path: str = Query("."),
    workspace: str = Query(...),
):
    """列出目录或读取文件"""
    try:
        ws = _get_workspace_manager(workspace)
        validated = ws.validate_path(path)

        if validated.is_dir():
            items = []
            for item in sorted(validated.iterdir()):
                try:
                    rel = ws.get_relative_path(item)
                    items.append({
                        "name": item.name,
                        "path": str(rel),
                        "type": "directory" if item.is_dir() else "file",
                        "size": item.stat().st_size if item.is_file() else 0,
                    })
                except Exception:
                    continue
            return {"type": "directory", "path": path, "entries": items}
        else:
            try:
                content = validated.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                try:
                    content = validated.read_text(encoding="gbk")
                except UnicodeDecodeError:
                    raise HTTPException(400, "Cannot decode file")
            return {
                "type": "file",
                "path": path,
                "content": content,
                "size": validated.stat().st_size,
            }
    except ValueError as e:
        raise HTTPException(403, str(e))
    except Exception as e:
        raise HTTPException(500, str(e))


@router.put("/files")
async def write_file_endpoint(req: WriteFileRequest, workspace: str = Query(...)):
    """写入文件"""
    try:
        ws = _get_workspace_manager(workspace)
        validated = ws.validate_path(req.path)
        validated.parent.mkdir(parents=True, exist_ok=True)
        validated.write_text(req.content, encoding="utf-8")
        return {"success": True, "path": req.path}
    except ValueError as e:
        raise HTTPException(403, str(e))
    except Exception as e:
        raise HTTPException(500, str(e))


@router.delete("/files")
async def delete_file_endpoint(path: str = Query(...), workspace: str = Query(...)):
    """删除文件"""
    try:
        ws = _get_workspace_manager(workspace)
        validated = ws.validate_path(path)
        if not validated.exists():
            raise HTTPException(404, f"File not found: {path}")
        if validated.is_file():
            validated.unlink()
            return {"success": True, "path": path}
        else:
            raise HTTPException(400, "Path is a directory, not a file")
    except ValueError as e:
        raise HTTPException(403, str(e))
    except Exception as e:
        raise HTTPException(500, str(e))


@router.post("/upload")
async def upload_file_endpoint(
    workspace: str = Query(...),
    file: bytes = None,
    filename: str = None,
):
    """上传文件到工作区 .uploads 目录"""
    try:
        ws = _get_workspace_manager(workspace)
        uploads_dir = ws.validate_path(".uploads")
        uploads_dir.mkdir(parents=True, exist_ok=True)

        file_path = uploads_dir / filename
        file_path.write_bytes(file)

        rel_path = ws.get_relative_path(file_path)
        return {"success": True, "path": str(rel_path)}
    except Exception as e:
        raise HTTPException(500, str(e))
