"""WebSocket 路由 — Agent 事件流"""

import asyncio
import json
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from api.agent_adapter import get_session

router = APIRouter()


@router.websocket("/sessions/{session_id}/ws")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    """WebSocket 端点：双向通信 Agent 事件流"""
    session = get_session(session_id)
    if not session:
        await websocket.close(code=4004, reason="Session not found")
        return

    await websocket.accept()
    active = True

    async def push_events():
        """从事件队列读取事件并推送给前端"""
        nonlocal active
        while active:
            try:
                # 非阻塞获取事件
                events = session.get_events()
                for event in events:
                    if active:
                        await websocket.send_json(event)
                await asyncio.sleep(0.05)  # 50ms 轮询间隔
            except Exception:
                break

    async def receive_commands():
        """接收前端命令"""
        nonlocal active
        try:
            while active:
                data = await websocket.receive_text()
                msg = json.loads(data)

                msg_type = msg.get("type")

                if msg_type == "start":
                    # 启动任务
                    task = msg.get("task", "")
                    model = msg.get("model")
                    api_base = msg.get("api_base")
                    api_key = msg.get("api_key")
                    session.start(task, model=model, api_base=api_base, api_key=api_key)

                elif msg_type == "confirm_response":
                    # 用户确认响应
                    request_id = msg.get("request_id", "")
                    approved = msg.get("approved", False)
                    whitelist = msg.get("whitelist", False)
                    session.confirm(request_id, approved, whitelist)

                elif msg_type == "plan_approved":
                    # 用户批准计划
                    plan = msg.get("plan", {})
                    session.approve_plan(plan)

                elif msg_type == "plan_rejected":
                    # 用户拒绝计划
                    feedback = msg.get("feedback", "")
                    session.reject_plan(feedback)

                elif msg_type == "feedback_response":
                    # 用户反馈响应
                    request_id = msg.get("request_id", "")
                    action = msg.get("action", "continue")
                    feedback_text = msg.get("feedback", "")
                    session.feedback(request_id, action, feedback_text)

                elif msg_type == "stop":
                    # 停止 agent
                    session.stop()

        except WebSocketDisconnect:
            active = False
        except Exception:
            active = False

    # 并行运行推送和接收
    push_task = asyncio.create_task(push_events())
    receive_task = asyncio.create_task(receive_commands())

    try:
        await asyncio.gather(push_task, receive_task)
    except Exception:
        pass
    finally:
        active = False
        push_task.cancel()
        receive_task.cancel()
