"""
GuardCode Agent API 服务器入口

启动方式：
    python -m api.server

访问：
    http://localhost:8000          — API 根
    http://localhost:8000/docs     — OpenAPI 文档
"""

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from api.routes import sessions, files, ws, config

app = FastAPI(title="GuardCode Agent API", version="1.0.0")

# CORS：允许前端 dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(sessions.router, prefix="/api")
app.include_router(files.router, prefix="/api")
app.include_router(ws.router, prefix="/api")
app.include_router(config.router, prefix="/api")


@app.get("/")
async def root():
    return {"name": "GuardCode Agent API", "status": "running"}


# 生产模式：serve 前端静态文件（如果已构建）
frontend_dist = Path(__file__).parent.parent / "frontend" / "dist"
if frontend_dist.exists():
    app.mount("/", StaticFiles(directory=str(frontend_dist), html=True), name="frontend")


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
