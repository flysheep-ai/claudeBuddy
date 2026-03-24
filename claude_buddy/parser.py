"""
日志解析器：将 Claude Code JSONL 日志解析为结构化的步骤序列
"""
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Step:
    uuid: str
    parent_uuid: Optional[str]
    timestamp: str
    role: str           # "user" | "assistant" | "tool"
    step_type: str      # "user_input" | "thinking" | "text" | "tool_call" | "tool_result"
    content: str
    tool_name: Optional[str] = None
    tool_input: Optional[dict] = None
    metadata: dict = field(default_factory=dict)


def _format_tool_summary(tool_name: str, tool_input: dict) -> str:
    if tool_name == "Bash":
        desc = tool_input.get("description", "")
        cmd = tool_input.get("command", "")
        return f"{desc} | `{cmd[:100]}`" if desc else f"`{cmd[:120]}`"
    elif tool_name == "Read":
        return tool_input.get("file_path", str(tool_input)[:100])
    elif tool_name == "Write":
        return f"写入 {tool_input.get('file_path', '')}"
    elif tool_name == "Edit":
        return f"修改 {tool_input.get('file_path', '')}"
    elif tool_name == "Glob":
        return f"匹配 {tool_input.get('pattern', '')} 在 {tool_input.get('path', '.')}"
    elif tool_name == "Grep":
        return f"搜索 `{tool_input.get('pattern', '')}` 在 {tool_input.get('path', '.')}"
    elif tool_name == "WebSearch":
        return f"搜索: {tool_input.get('query', '')}"
    elif tool_name == "WebFetch":
        return f"抓取: {tool_input.get('url', '')[:80]}"
    else:
        return str(tool_input)[:150]


def _extract_tool_result_text(content) -> str:
    if isinstance(content, str):
        return content[:400]
    if isinstance(content, list):
        parts = [b.get("text", "") for b in content if isinstance(b, dict)]
        return " ".join(parts)[:400]
    return str(content)[:400]


def parse_session(lines: list[dict]) -> list[Step]:
    """
    将 JSONL 行列表解析为 Step 序列（按出现顺序，自动去重流式重复行）
    """
    steps: list[Step] = []
    seen: set[tuple] = set()

    for line in lines:
        msg_type = line.get("type")
        if msg_type not in ("user", "assistant"):
            continue

        uuid = line.get("uuid", "")
        parent_uuid = line.get("parentUuid")
        timestamp = line.get("timestamp", "")
        content = line.get("message", {}).get("content", "")

        if msg_type == "user":
            if isinstance(content, str):
                if content and not content.startswith("<") and len(content) > 2:
                    steps.append(Step(uuid=uuid, parent_uuid=parent_uuid,
                                      timestamp=timestamp, role="user",
                                      step_type="user_input", content=content.strip()))
            elif isinstance(content, list):
                for block in content:
                    if not isinstance(block, dict):
                        continue
                    if block.get("type") == "tool_result":
                        raw = block.get("content", "")
                        text = _extract_tool_result_text(raw)
                        if text.strip():
                            steps.append(Step(uuid=uuid, parent_uuid=parent_uuid,
                                              timestamp=timestamp, role="tool",
                                              step_type="tool_result", content=text,
                                              metadata={"tool_use_id": block.get("tool_use_id", "")}))

        elif msg_type == "assistant":
            if not isinstance(content, list):
                continue
            for block in content:
                if not isinstance(block, dict):
                    continue
                btype = block.get("type")

                if btype == "thinking":
                    text = block.get("thinking", "").strip()
                    key = (uuid, "thinking", hash(text[:64]))
                    if text and key not in seen:
                        seen.add(key)
                        steps.append(Step(uuid=uuid, parent_uuid=parent_uuid,
                                          timestamp=timestamp, role="assistant",
                                          step_type="thinking", content=text))

                elif btype == "text":
                    text = block.get("text", "").strip()
                    key = (uuid, "text", hash(text[:64]))
                    if text and key not in seen:
                        seen.add(key)
                        steps.append(Step(uuid=uuid, parent_uuid=parent_uuid,
                                          timestamp=timestamp, role="assistant",
                                          step_type="text", content=text))

                elif btype == "tool_use":
                    tool_name = block.get("name", "")
                    tool_input = block.get("input", {})
                    summary = _format_tool_summary(tool_name, tool_input)
                    key = (uuid, "tool_call", hash(summary[:64]))
                    if key not in seen:
                        seen.add(key)
                        steps.append(Step(uuid=uuid, parent_uuid=parent_uuid,
                                          timestamp=timestamp, role="assistant",
                                          step_type="tool_call", content=summary,
                                          tool_name=tool_name, tool_input=tool_input))
    return steps


def get_session_stats(steps: list[Step]) -> dict:
    stats: dict = {"total": len(steps), "user_inputs": 0, "thinking": 0,
                   "text_responses": 0, "tool_calls": 0, "tool_results": 0, "tools_used": {}}
    for step in steps:
        match step.step_type:
            case "user_input":   stats["user_inputs"] += 1
            case "thinking":     stats["thinking"] += 1
            case "text":         stats["text_responses"] += 1
            case "tool_result":  stats["tool_results"] += 1
            case "tool_call":
                stats["tool_calls"] += 1
                n = step.tool_name or "Unknown"
                stats["tools_used"][n] = stats["tools_used"].get(n, 0) + 1
    return stats
