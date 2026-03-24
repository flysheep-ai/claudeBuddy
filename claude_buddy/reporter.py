"""
报告生成器：将结构化步骤序列通过 LLM 转化为教学报告

支持的提供商：
  - anthropic : 使用 anthropic SDK（claude-* 系列模型）
  - openai    : 使用 openai SDK（gpt-* 系列模型）
  - ollama    : 使用 openai SDK + 本地端点（llama / qwen 等本地模型）
  - 其他      : 任何兼容 OpenAI Chat Completions 接口的服务（DeepSeek、Moonshot 等）
"""
from .parser import Step

THINKING_MAX = 600
TEXT_MAX = 400
RESULT_MAX = 300
MAX_DIGEST_CHARS = 120_000


def _build_digest(steps: list[Step]) -> str:
    lines: list[str] = []
    tool_buf: list[str] = []

    def flush_tools() -> None:
        if not tool_buf:
            return
        if len(tool_buf) == 1:
            lines.append(f"  🔧 {tool_buf[0]}")
        else:
            lines.append(f"  🔧 连续执行 {len(tool_buf)} 个工具：")
            for t in tool_buf[:6]:
                lines.append(f"     - {t}")
            if len(tool_buf) > 6:
                lines.append(f"     - ...（共 {len(tool_buf)} 个）")
        tool_buf.clear()

    prev_type = None
    for step in steps:
        t = step.step_type
        if t == "user_input":
            flush_tools()
            lines.append(f"\n👤 用户：{step.content}")
        elif t == "thinking":
            flush_tools()
            text = step.content[:THINKING_MAX] + ("…" if len(step.content) > THINKING_MAX else "")
            lines.append(f"\n🤔 Claude思考：\n{text}")
        elif t == "text":
            flush_tools()
            text = step.content[:TEXT_MAX] + ("…" if len(step.content) > TEXT_MAX else "")
            lines.append(f"\n💬 Claude回复：{text}")
        elif t == "tool_call":
            tool_buf.append(f"[{step.tool_name}] {step.content}")
        elif t == "tool_result":
            if prev_type == "tool_call" or tool_buf:
                flush_tools()
                result = step.content[:RESULT_MAX] + ("…" if len(step.content) > RESULT_MAX else "")
                lines.append(f"  📤 结果：{result}")
        prev_type = t

    flush_tools()
    return "\n".join(lines)


SYSTEM_PROMPT = """你是一位经验丰富的技术教育专家，擅长将 AI 编程过程转化为清晰易懂的学习材料。
你的目标是帮助编程初学者理解"如何像专业工程师一样思考和解决问题"。

写作要求：
- 用中文输出，语言简洁清晰，面向有基础的编程初学者
- 重点提炼 Claude 的思维方式和决策逻辑，而不是罗列操作步骤
- 每个章节都要有洞见，让读者学到可复用的方法论
- 如果日志信息不足以支撑某个章节，简短说明即可，不要编造内容"""


def _make_prompt(digest: str, project_name: str) -> str:
    return f"""以下是 Claude Code 完成一个编程任务的工作日志摘要。

**项目**：{project_name}

=== 工作日志 ===
{digest}
=== 结束 ===

请生成一篇面向编程初学者的结构化学习报告，严格按照以下 Markdown 结构：

---

# 📋 项目构建报告：{project_name}

> **报告说明**：本报告通过分析 Claude Code 的工作日志，还原 AI 解决这个编程问题的完整思维过程，帮助你学习工程化的编程方法论。

---

## 1. 需求理解

## 2. 任务拆解策略

## 3. 信息调研过程

## 4. 技术方案设计

## 5. 实现过程详解

## 6. 问题与应对

## 7. 方法论总结

---
"""


def _call_anthropic(prompt: str, model: str, api_key: str) -> str:
    import anthropic
    client = anthropic.Anthropic(api_key=api_key)
    msg = client.messages.create(
        model=model,
        max_tokens=4096,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )
    return msg.content[0].text


def _call_openai_compatible(
    prompt: str,
    model: str,
    api_key: str,
    base_url: str,
) -> str:
    from openai import OpenAI
    kwargs: dict = {"api_key": api_key or "ollama"}   # ollama 不校验 key，但 SDK 要求非空
    if base_url:
        kwargs["base_url"] = base_url
    client = OpenAI(**kwargs)
    resp = client.chat.completions.create(
        model=model,
        max_tokens=4096,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": prompt},
        ],
    )
    return resp.choices[0].message.content


def generate_report(
    steps: list[Step],
    project_name: str,
    provider: str,
    model: str,
    api_key: str,
    base_url: str = "",
) -> str:
    """
    生成学习报告，根据 provider 自动选择 SDK：
      anthropic → anthropic SDK
      其他      → openai SDK（通过 base_url 支持 Ollama / DeepSeek 等）
    """
    digest = _build_digest(steps)
    if len(digest) > MAX_DIGEST_CHARS:
        digest = digest[:MAX_DIGEST_CHARS] + "\n\n…（日志已截断）"
    prompt = _make_prompt(digest, project_name)

    if provider == "anthropic":
        return _call_anthropic(prompt, model, api_key)
    else:
        return _call_openai_compatible(prompt, model, api_key, base_url)
