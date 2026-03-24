"""
会话采集器：从 ~/.claude/projects/ 发现并加载 Claude Code 会话日志
"""
import json
from pathlib import Path
from dataclasses import dataclass
from datetime import datetime

CLAUDE_DIR = Path.home() / ".claude"
PROJECTS_DIR = CLAUDE_DIR / "projects"
HISTORY_FILE = CLAUDE_DIR / "history.jsonl"


@dataclass
class SessionInfo:
    session_id: str
    project_path: str       # 真实项目路径
    display_name: str       # 项目短名称
    file_path: Path
    modified_time: datetime
    file_size: int
    first_message: str      # 首条用户消息预览


def _load_history_index() -> dict[str, dict]:
    index: dict[str, dict] = {}
    if not HISTORY_FILE.exists():
        return index
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                    sid = obj.get("sessionId", "")
                    if sid:
                        index[sid] = obj
                except json.JSONDecodeError:
                    continue
    except (PermissionError, OSError):
        pass
    return index


def _extract_cwd_from_session(file_path: Path) -> str:
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                    cwd = obj.get("cwd", "")
                    if cwd:
                        return cwd
                except json.JSONDecodeError:
                    continue
    except (PermissionError, OSError):
        pass
    return ""


def _extract_first_user_message(file_path: Path) -> str:
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                    if obj.get("type") != "user":
                        continue
                    content = obj.get("message", {}).get("content", "")
                    if isinstance(content, str) and content and not content.startswith("<"):
                        return content[:100]
                except json.JSONDecodeError:
                    continue
    except (PermissionError, OSError):
        pass
    return ""


def list_sessions() -> list[SessionInfo]:
    """列出所有可读的 Claude Code 会话，按时间倒序"""
    if not PROJECTS_DIR.exists():
        return []

    history_index = _load_history_index()
    sessions: list[SessionInfo] = []

    for project_dir in PROJECTS_DIR.iterdir():
        if not project_dir.is_dir():
            continue
        for jsonl_file in project_dir.glob("*.jsonl"):
            try:
                stat = jsonl_file.stat()
            except (PermissionError, OSError):
                continue

            session_id = jsonl_file.stem
            hist = history_index.get(session_id, {})
            project_path = hist.get("project", "") or _extract_cwd_from_session(jsonl_file)
            if not project_path:
                project_path = "/" + project_dir.name.lstrip("-").replace("-", "/")

            display_name = Path(project_path).name or project_path
            first_msg = hist.get("display", "") or _extract_first_user_message(jsonl_file)

            sessions.append(SessionInfo(
                session_id=session_id,
                project_path=project_path,
                display_name=display_name,
                file_path=jsonl_file,
                modified_time=datetime.fromtimestamp(stat.st_mtime),
                file_size=stat.st_size,
                first_message=first_msg[:80] if first_msg else "",
            ))

    return sorted(sessions, key=lambda s: s.modified_time, reverse=True)


def load_session(file_path: Path) -> list[dict]:
    """加载 session JSONL 文件，返回所有记录行"""
    lines: list[dict] = []
    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                lines.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return lines
