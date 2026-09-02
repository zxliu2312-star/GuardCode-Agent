"""
GuardCode Agent 数据库模块

使用 SQLite 存储必要信息：
- 任务列表（当前用户任务）
- 自定义模型配置
- 工作区设置

不区分用户，单机本地存储。
"""

import json
import sqlite3
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Optional


# 数据库文件路径
# 优先使用项目目录下的 data 文件夹，避免 Windows Defender 受控文件夹访问阻止写入主目录
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_DIR = _PROJECT_ROOT / "data"
DB_PATH = DB_DIR / "guardcode.db"

# 线程锁，确保并发安全
_db_lock = threading.RLock()


def _get_connection() -> sqlite3.Connection:
    """获取数据库连接"""
    DB_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA journal_mode=WAL")
    except sqlite3.OperationalError:
        pass
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _init_db():
    """初始化数据库表"""
    conn = _get_connection()
    try:
        cursor = conn.cursor()

        # 任务表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                workspace TEXT NOT NULL,
                mode TEXT DEFAULT 'WORK',
                status TEXT DEFAULT 'pending',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                session_id TEXT,
                last_message TEXT
            )
        """)

        # 模型配置表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS model_configs (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                api_base TEXT NOT NULL,
                api_key TEXT NOT NULL,
                model_name TEXT NOT NULL,
                is_built_in INTEGER DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)

        # 工作区设置表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS workspace_settings (
                id TEXT PRIMARY KEY,
                path TEXT NOT NULL UNIQUE,
                display_name TEXT,
                last_used TEXT NOT NULL,
                is_favorite INTEGER DEFAULT 0
            )
        """)

        # 应用设置表（键值对存储）
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS app_settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)

        # 规则表（自定义系统提示词规则）
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS rules (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                content TEXT NOT NULL,
                is_enabled INTEGER DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)

        # 消息历史表（记录任务对话历史）
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id TEXT PRIMARY KEY,
                task_id TEXT NOT NULL,
                type TEXT NOT NULL,
                content TEXT,
                timestamp INTEGER NOT NULL,
                metadata TEXT,
                FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE
            )
        """)
        
        # 为消息表创建索引，提升查询性能
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_messages_task_id_timestamp
            ON messages(task_id, timestamp)
        """)

        # Remove legacy duplicate custom names before enforcing uniqueness.
        cursor.execute("""
            DELETE FROM model_configs
            WHERE is_built_in = 0
              AND rowid NOT IN (
                  SELECT MIN(rowid) FROM model_configs
                  WHERE is_built_in = 0
                  GROUP BY name
              )
        """)
        cursor.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_model_configs_custom_name
            ON model_configs(name)
            WHERE is_built_in = 0
        """)

        conn.commit()
    finally:
        conn.close()


# ──────────────────────────────────────────────────────────
# 任务 CRUD
def save_task(
    task_id: str,
    name: str,
    workspace: str,
    mode: str = "WORK",
    status: str = "pending",
    session_id: Optional[str] = None,
    last_message: Optional[str] = None,
) -> dict:
    """保存或更新任务"""
    with _db_lock:
        conn = _get_connection()
        try:
            now = datetime.now().isoformat()
            cursor = conn.cursor()

            # 检查是否已存在
            cursor.execute("SELECT id FROM tasks WHERE id = ?", (task_id,))
            exists = cursor.fetchone()

            if exists:
                cursor.execute("""
                    UPDATE tasks
                    SET name=?, workspace=?, mode=?, status=?, session_id=?, last_message=?, updated_at=?
                    WHERE id=?
                """, (name, workspace, mode, status, session_id, last_message, now, task_id))
            else:
                cursor.execute("""
                    INSERT INTO tasks (id, name, workspace, mode, status, created_at, updated_at, session_id, last_message)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (task_id, name, workspace, mode, status, now, now, session_id, last_message))

            conn.commit()
            return get_task(task_id)
        finally:
            conn.close()


def get_task(task_id: str) -> Optional[dict]:
    """获取单个任务"""
    with _db_lock:
        conn = _get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
        finally:
            conn.close()


def list_tasks() -> list[dict]:
    """列出所有任务，按更新时间倒序"""
    with _db_lock:
        conn = _get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM tasks ORDER BY updated_at DESC")
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()


def delete_task(task_id: str) -> bool:
    """删除任务"""
    with _db_lock:
        conn = _get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()


def update_task_status(task_id: str, status: str, last_message: Optional[str] = None):
    """更新任务状态"""
    with _db_lock:
        conn = _get_connection()
        try:
            now = datetime.now().isoformat()
            cursor = conn.cursor()
            if last_message:
                cursor.execute(
                    "UPDATE tasks SET status=?, last_message=?, updated_at=? WHERE id=?",
                    (status, last_message, now, task_id)
                )
            else:
                cursor.execute(
                    "UPDATE tasks SET status=?, updated_at=? WHERE id=?",
                    (status, now, task_id)
                )
            conn.commit()
        finally:
            conn.close()


# ──────────────────────────────────────────────────────────
# 模型配置 CRUD
# ──────────────────────────────────────────────────────────

def save_model_config(
    config_id: str,
    name: str,
    api_base: str,
    api_key: str,
    model_name: str,
    is_built_in: bool = False,
) -> dict:
    """保存或更新模型配置"""
    with _db_lock:
        conn = _get_connection()
        try:
            now = datetime.now().isoformat()
            cursor = conn.cursor()

            cursor.execute("SELECT id FROM model_configs WHERE id = ?", (config_id,))
            exists = cursor.fetchone()

            if exists:
                cursor.execute("""
                    UPDATE model_configs
                    SET name=?, api_base=?, api_key=?, model_name=?, is_built_in=?, updated_at=?
                    WHERE id=?
                """, (name, api_base, api_key, model_name, int(is_built_in), now, config_id))
            else:
                cursor.execute("""
                    INSERT INTO model_configs (id, name, api_base, api_key, model_name, is_built_in, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (config_id, name, api_base, api_key, model_name, int(is_built_in), now, now))

            conn.commit()
            return get_model_config(config_id)
        finally:
            conn.close()


def get_model_config(config_id: str) -> Optional[dict]:
    """获取单个模型配置"""
    with _db_lock:
        conn = _get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM model_configs WHERE id = ?", (config_id,))
            row = cursor.fetchone()
            if row:
                d = dict(row)
                d["is_built_in"] = bool(d["is_built_in"])
                return d
            return None
        finally:
            conn.close()


def get_model_config_by_name(name: str) -> Optional[dict]:
    """按模型名称获取配置"""
    with _db_lock:
        conn = _get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM model_configs WHERE name = ? LIMIT 1", (name,))
            row = cursor.fetchone()
            if row:
                d = dict(row)
                d["is_built_in"] = bool(d["is_built_in"])
                return d
            return None
        finally:
            conn.close()


def list_model_configs() -> list[dict]:
    """列出所有模型配置"""
    with _db_lock:
        conn = _get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM model_configs ORDER BY is_built_in DESC, created_at ASC")
            rows = cursor.fetchall()
            result = []
            for row in rows:
                d = dict(row)
                d["is_built_in"] = bool(d["is_built_in"])
                result.append(d)
            return result
        finally:
            conn.close()


def delete_model_config(config_id: str) -> bool:
    """删除模型配置"""
    with _db_lock:
        conn = _get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM model_configs WHERE id = ? AND is_built_in = 0", (config_id,))
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()


# ──────────────────────────────────────────────────────────
# 工作区设置 CRUD
# ──────────────────────────────────────────────────────────

def save_workspace(
    path: str,
    display_name: Optional[str] = None,
    is_favorite: bool = False,
) -> dict:
    """保存或更新工作区"""
    with _db_lock:
        conn = _get_connection()
        try:
            now = datetime.now().isoformat()
            cursor = conn.cursor()

            cursor.execute("SELECT id FROM workspace_settings WHERE path = ?", (path,))
            existing = cursor.fetchone()

            if existing:
                cursor.execute("""
                    UPDATE workspace_settings
                    SET display_name=?, last_used=?, is_favorite=?
                    WHERE path=?
                """, (display_name, now, int(is_favorite), path))
                config_id = existing["id"]
            else:
                import uuid
                config_id = str(uuid.uuid4())[:12]
                cursor.execute("""
                    INSERT INTO workspace_settings (id, path, display_name, last_used, is_favorite)
                    VALUES (?, ?, ?, ?, ?)
                """, (config_id, path, display_name, now, int(is_favorite)))

            conn.commit()
            cursor.execute("SELECT * FROM workspace_settings WHERE path = ?", (path,))
            row = cursor.fetchone()
            return dict(row) if row else {}
        finally:
            conn.close()


def list_workspaces() -> list[dict]:
    """列出所有工作区，按最近使用排序"""
    with _db_lock:
        conn = _get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM workspace_settings ORDER BY last_used DESC")
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()


def delete_workspace(path: str) -> bool:
    """删除工作区记录"""
    with _db_lock:
        conn = _get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM workspace_settings WHERE path = ?", (path,))
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()


# ──────────────────────────────────────────────────────────
# 应用设置（键值对）
# ──────────────────────────────────────────────────────────

def get_setting(key: str, default: Optional[str] = None) -> Optional[str]:
    """获取应用设置"""
    with _db_lock:
        conn = _get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM app_settings WHERE key = ?", (key,))
            row = cursor.fetchone()
            return row["value"] if row else default
        finally:
            conn.close()


def set_setting(key: str, value: str):
    """设置应用设置"""
    with _db_lock:
        conn = _get_connection()
        try:
            now = datetime.now().isoformat()
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO app_settings (key, value, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at
            """, (key, value, now))
            conn.commit()
        finally:
            conn.close()


# ──────────────────────────────────────────────────────────
# 规则 CRUD
# ──────────────────────────────────────────────────────────

def list_rules() -> list[dict]:
    """列出所有规则，按创建时间正序"""
    with _db_lock:
        conn = _get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM rules ORDER BY created_at ASC")
            rows = cursor.fetchall()
            result = []
            for row in rows:
                d = dict(row)
                d["is_enabled"] = bool(d["is_enabled"])
                result.append(d)
            return result
        finally:
            conn.close()


def get_rule(rule_id: str) -> Optional[dict]:
    """获取单个规则"""
    with _db_lock:
        conn = _get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM rules WHERE id = ?", (rule_id,))
            row = cursor.fetchone()
            if row:
                d = dict(row)
                d["is_enabled"] = bool(d["is_enabled"])
                return d
            return None
        finally:
            conn.close()


def create_rule(name: str, content: str, is_enabled: bool = True) -> dict:
    """创建规则"""
    with _db_lock:
        conn = _get_connection()
        try:
            import uuid
            now = datetime.now().isoformat()
            rule_id = f"rule-{uuid.uuid4().hex[:12]}"
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO rules (id, name, content, is_enabled, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (rule_id, name, content, int(is_enabled), now, now))
            conn.commit()
            cursor.execute("SELECT * FROM rules WHERE id = ?", (rule_id,))
            row = cursor.fetchone()
            d = dict(row) if row else {}
            d["is_enabled"] = bool(d.get("is_enabled", 1))
            return d
        finally:
            conn.close()


def update_rule(
    rule_id: str,
    name: str,
    content: str,
    is_enabled: bool,
) -> Optional[dict]:
    """更新规则"""
    with _db_lock:
        conn = _get_connection()
        try:
            now = datetime.now().isoformat()
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM rules WHERE id = ?", (rule_id,))
            if not cursor.fetchone():
                return None
            cursor.execute("""
                UPDATE rules
                SET name=?, content=?, is_enabled=?, updated_at=?
                WHERE id=?
            """, (name, content, int(is_enabled), now, rule_id))
            conn.commit()
            cursor.execute("SELECT * FROM rules WHERE id = ?", (rule_id,))
            row = cursor.fetchone()
            d = dict(row) if row else {}
            d["is_enabled"] = bool(d.get("is_enabled", 1))
            return d
        finally:
            conn.close()


def delete_rule(rule_id: str) -> bool:
    """删除规则"""
    with _db_lock:
        conn = _get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM rules WHERE id = ?", (rule_id,))
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()


# ──────────────────────────────────────────────────────────
# 消息历史 CRUD
# ──────────────────────────────────────────────────────────

def save_message(
    message_id: str,
    task_id: str,
    msg_type: str,
    content: Optional[str],
    timestamp: int,
    metadata: Optional[dict] = None,
) -> dict:
    """保存消息到历史"""
    with _db_lock:
        conn = _get_connection()
        try:
            cursor = conn.cursor()
            metadata_json = json.dumps(metadata) if metadata else None
            
            cursor.execute("""
                INSERT OR REPLACE INTO messages (id, task_id, type, content, timestamp, metadata)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (message_id, task_id, msg_type, content, timestamp, metadata_json))
            
            conn.commit()
            return {
                "id": message_id,
                "task_id": task_id,
                "type": msg_type,
                "content": content,
                "timestamp": timestamp,
                "metadata": metadata,
            }
        finally:
            conn.close()


def get_task_messages(task_id: str, limit: Optional[int] = None) -> list[dict]:
    """获取任务的历史消息，按时间顺序"""
    with _db_lock:
        conn = _get_connection()
        try:
            cursor = conn.cursor()
            if limit:
                cursor.execute("""
                    SELECT * FROM messages 
                    WHERE task_id = ? 
                    ORDER BY timestamp ASC 
                    LIMIT ?
                """, (task_id, limit))
            else:
                cursor.execute("""
                    SELECT * FROM messages 
                    WHERE task_id = ? 
                    ORDER BY timestamp ASC
                """, (task_id,))
            
            rows = cursor.fetchall()
            messages = []
            for row in rows:
                msg = dict(row)
                # 解析 metadata JSON
                if msg.get("metadata"):
                    try:
                        msg["metadata"] = json.loads(msg["metadata"])
                    except (json.JSONDecodeError, TypeError):
                        msg["metadata"] = None
                messages.append(msg)
            return messages
        finally:
            conn.close()


def delete_task_messages(task_id: str) -> int:
    """删除任务的所有消息"""
    with _db_lock:
        conn = _get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM messages WHERE task_id = ?", (task_id,))
            conn.commit()
            return cursor.rowcount
        finally:
            conn.close()


def get_message_count(task_id: str) -> int:
    """获取任务的消息数量"""
    with _db_lock:
        conn = _get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM messages WHERE task_id = ?", (task_id,))
            return cursor.fetchone()[0]
        finally:
            conn.close()


# ──────────────────────────────────────────────────────────
# 初始化
# ──────────────────────────────────────────────────────────

# 模块加载时初始化数据库
_init_db()
