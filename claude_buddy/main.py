#!/usr/bin/env python3
"""
claude-buddy — 把 Claude Code 的工作过程变成你的学习材料
"""
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.markdown import Markdown
from rich.prompt import IntPrompt, Prompt, Confirm

from . import config as cfg
from .collector import list_sessions, load_session
from .parser import parse_session, get_session_stats
from .reporter import generate_report

console = Console()


# ═══════════════════════════════════════════════════════════════
# 根命令
# ═══════════════════════════════════════════════════════════════

@click.group()
def cli():
    """claude-buddy — 把 Claude Code 的工作过程变成你的学习材料\n
    \b
    快速开始：
      claude-buddy config setup   ← 交互式配置向导（首次使用）
      claude-buddy list
      claude-buddy report -i 1
    """
    pass


# ═══════════════════════════════════════════════════════════════
# config 命令组
# ═══════════════════════════════════════════════════════════════

@cli.group("config")
def cmd_config():
    """管理 claude-buddy 配置（API Key、默认模型等）"""
    pass


@cmd_config.command("show")
def config_show():
    """显示当前所有配置"""
    current = cfg.load()
    table = Table(title="当前配置", show_header=True, header_style="bold blue")
    table.add_column("配置项", style="cyan", width=16)
    table.add_column("说明", style="dim", width=36)
    table.add_column("当前值", style="green")

    for key, desc in cfg.VALID_KEYS.items():
        value = current.get(key, "")
        if key == "api_key" and value:
            display = value[:8] + "..." + value[-4:] if len(value) > 12 else "***"
        else:
            display = value or "[dim]（未设置）[/dim]"
        table.add_row(key, desc, display)

    console.print(table)
    console.print(f"[dim]配置文件位置：{cfg.CONFIG_FILE}[/dim]")


@cmd_config.command("set")
@click.argument("key")
@click.argument("value")
def config_set(key: str, value: str):
    """设置配置项

    \b
    示例：
      claude-buddy config set api-key sk-ant-...
      claude-buddy config set model claude-opus-4-6
      claude-buddy config set output-dir ~/reports
    """
    # 支持 kebab-case 输入（api-key → api_key）
    key = key.replace("-", "_")
    try:
        cfg.set_value(key, value)
        if key == "api_key":
            masked = value[:8] + "..." + value[-4:] if len(value) > 12 else "***"
            console.print(f"[green]✓[/green] api_key 已保存（{masked}）")
        else:
            console.print(f"[green]✓[/green] {key} = {value}")
    except ValueError as e:
        console.print(f"[red]✗ {e}[/red]")
        console.print(f"可用配置项：{list(cfg.VALID_KEYS.keys())}")


@cmd_config.command("setup")
def config_setup():
    """交互式配置向导（推荐首次使用）"""

    # 预置提供商信息：name -> (默认model, 默认base_url, 是否需要key)
    PROVIDERS = {
        "1": ("anthropic", "claude-sonnet-4-6", "",                              True),
        "2": ("openai",    "gpt-4o",            "",                              True),
        "3": ("ollama",    "llama3.2",          "http://localhost:11434/v1",     False),
        "4": ("other",     "",                  "",                              True),
    }

    current = cfg.load()
    console.print(Panel(
        "回答以下问题完成配置，直接回车保留当前值",
        title="[bold blue]claude-buddy 配置向导[/bold blue]",
        border_style="blue",
    ))

    # ── 1. 选择提供商 ─────────────────────────────────────────
    console.print("\n[bold]选择 LLM 提供商：[/bold]")
    console.print("  1. Anthropic（Claude 系列）")
    console.print("  2. OpenAI（GPT 系列）")
    console.print("  3. Ollama（本地模型，无需 API Key）")
    console.print("  4. 其他（兼容 OpenAI 接口的服务，如 DeepSeek、Moonshot 等）")

    cur_provider = current.get("provider", "anthropic")
    cur_choice = next((k for k, v in PROVIDERS.items() if v[0] == cur_provider), "1")
    choice = Prompt.ask("请选择", choices=["1", "2", "3", "4"], default=cur_choice)

    provider, default_model, default_base_url, needs_key = PROVIDERS[choice]

    # ── 2. 自定义 base_url ────────────────────────────────────
    if choice == "3":
        # Ollama：显示默认端点，允许修改
        cur_base = current.get("base_url", "") or default_base_url
        base_url = Prompt.ask(
            "Ollama 服务地址",
            default=cur_base or default_base_url,
        )
    elif choice == "4":
        # 其他服务：必须填 base_url
        cur_base = current.get("base_url", "")
        base_url = Prompt.ask(
            "API 地址（如 https://api.deepseek.com）",
            default=cur_base or "",
        )
        if not base_url:
            console.print("[yellow]警告：未填写 API 地址，后续可用 `config set base-url` 补充[/yellow]")
    else:
        base_url = ""

    # ── 3. API Key ────────────────────────────────────────────
    api_key = current.get("api_key", "")
    if needs_key:
        masked = (api_key[:8] + "..." + api_key[-4:]) if len(api_key) > 12 else ("***" if api_key else "")
        prompt_hint = f"API Key [dim](当前：{masked}，回车保留)[/dim]" if masked else "API Key"
        new_key = Prompt.ask(prompt_hint, password=True, default="")
        if new_key:
            api_key = new_key
        elif not api_key:
            console.print("[yellow]警告：未填写 API Key，后续可用 `config set api-key` 补充[/yellow]")

    # ── 4. 模型名称 ───────────────────────────────────────────
    cur_model = current.get("model", "") or default_model
    model = Prompt.ask("模型名称", default=cur_model)

    # ── 5. 默认输出目录（可选）───────────────────────────────
    cur_out = current.get("output_dir", "")
    out_hint = cur_out or "留空则每次打印到终端"
    output_dir = Prompt.ask(f"默认报告保存目录", default=cur_out or "")

    # ── 保存 ─────────────────────────────────────────────────
    new_cfg = {
        "provider":   provider,
        "api_key":    api_key,
        "model":      model,
        "base_url":   base_url,
        "output_dir": output_dir,
    }
    cfg.save(new_cfg)

    # ── 汇总展示 ──────────────────────────────────────────────
    masked_key = (api_key[:8] + "..." + api_key[-4:]) if len(api_key) > 12 else ("***" if api_key else "（未设置）")
    console.print(Panel(
        f"[bold]提供商:[/bold]  {provider}\n"
        f"[bold]API Key:[/bold] {masked_key}\n"
        f"[bold]模型:[/bold]    {model}\n"
        + (f"[bold]API 地址:[/bold] {base_url}\n" if base_url else "")
        + (f"[bold]输出目录:[/bold] {output_dir}\n" if output_dir else ""),
        title="[bold green]✓ 配置已保存[/bold green]",
        border_style="green",
    ))
    console.print(f"[dim]配置文件：{cfg.CONFIG_FILE}[/dim]")
    console.print("\n现在可以运行：[cyan]claude-buddy list[/cyan]")


@cmd_config.command("get")
@click.argument("key")
def config_get(key: str):
    """读取某个配置项的值"""
    key = key.replace("-", "_")
    if key not in cfg.VALID_KEYS:
        console.print(f"[red]未知配置项 '{key}'[/red]")
        return
    value = cfg.get(key)
    if key == "api_key" and value:
        value = value[:8] + "..." + value[-4:] if len(value) > 12 else "***"
    console.print(value or "[dim]（未设置）[/dim]")


# ═══════════════════════════════════════════════════════════════
# list 命令
# ═══════════════════════════════════════════════════════════════

@cli.command("list")
@click.option("--project", "-p", default="", help="按项目路径关键词过滤")
@click.option("--limit", "-n", default=20, help="最多显示条数（默认20）")
def cmd_list(project: str, limit: int):
    """列出所有可用的 Claude Code 会话"""
    with console.status("正在扫描会话..."):
        sessions = list_sessions()

    if project:
        sessions = [s for s in sessions if project.lower() in s.project_path.lower()]

    if not sessions:
        console.print("[yellow]未找到任何可读会话[/yellow]")
        console.print("[dim]提示：部分会话文件由 root 拥有，可运行：[/dim]")
        console.print("[dim]  sudo chmod 644 ~/.claude/projects/**/*.jsonl[/dim]")
        return

    table = Table(
        title=f"Claude Code 会话（共 {len(sessions)} 个，显示最近 {min(limit, len(sessions))} 个）",
        show_header=True,
        header_style="bold blue",
    )
    table.add_column("#",          style="dim",    width=4,  justify="right")
    table.add_column("Session ID", style="cyan",   width=10)
    table.add_column("项目",       style="green",  max_width=30)
    table.add_column("时间",       style="yellow", width=12)
    table.add_column("大小",       style="blue",   width=8,  justify="right")
    table.add_column("首条消息",   style="white",  max_width=36)

    for i, s in enumerate(sessions[:limit], 1):
        size_str = (f"{s.file_size/1024/1024:.1f}MB" if s.file_size > 1024*1024
                    else f"{s.file_size/1024:.0f}KB")
        table.add_row(
            str(i),
            s.session_id[:8],
            s.display_name,
            s.modified_time.strftime("%m-%d %H:%M"),
            size_str,
            s.first_message or "[dim]无预览[/dim]",
        )

    console.print(table)
    console.print("[dim]用 `claude-buddy report -i <序号>` 生成报告[/dim]")


# ═══════════════════════════════════════════════════════════════
# report 命令
# ═══════════════════════════════════════════════════════════════

@cli.command("report")
@click.argument("session_id", required=False)
@click.option("--index",    "-i", type=int, default=None, help="使用 list 中的序号")
@click.option("--output",   "-o", default="",             help="输出文件路径（默认打印到终端）")
@click.option("--provider", "-P", default="",             help="LLM 提供商（覆盖配置，如 openai / ollama）")
@click.option("--model",    "-m", default="",             help="生成模型（覆盖配置）")
@click.option("--api-key",  "-k", default="",             help="API Key（覆盖配置）")
@click.option("--base-url", "-b", default="",             help="自定义 API 地址（覆盖配置）")
@click.option("--no-render", is_flag=True,                help="输出纯文本 Markdown，不渲染")
def cmd_report(session_id, index, output, provider, model, api_key, base_url, no_render):
    """为指定会话生成编程学习报告"""

    # ── 合并配置（命令行选项 > 环境变量 > 配置文件）──────────
    loaded = cfg.load()
    resolved_provider = provider  or loaded.get("provider", "anthropic")
    resolved_model    = model     or loaded.get("model", "claude-sonnet-4-6")
    resolved_key      = api_key   or loaded.get("api_key", "")
    resolved_base_url = base_url  or loaded.get("base_url", "")
    resolved_out      = output    or loaded.get("output_dir", "")

    # Ollama 本地服务不需要真实 key，自动补默认端点
    if resolved_provider == "ollama":
        resolved_base_url = resolved_base_url or "http://localhost:11434/v1"
    elif not resolved_key:
        # 非 Ollama 提供商必须有 key
        env_hint = {"anthropic": "ANTHROPIC_API_KEY", "openai": "OPENAI_API_KEY"}.get(
            resolved_provider, "对应提供商的 API KEY"
        )
        console.print(f"[red]✗ 未找到 API Key（当前提供商：{resolved_provider}）[/red]")
        console.print("\n请通过以下任一方式设置：")
        console.print(f"  1. [cyan]claude-buddy config set api-key <key>[/cyan]   （持久保存）")
        console.print(f"  2. [cyan]export {env_hint}=<key>[/cyan]")
        console.print(f"  3. [cyan]claude-buddy report -k <key>[/cyan]            （本次使用）")
        return

    # ── 选择目标会话 ──────────────────────────────────────────
    with console.status("正在扫描会话..."):
        sessions = list_sessions()

    if not sessions:
        console.print("[red]未找到任何可读会话[/red]")
        return

    target = None
    if index is not None:
        if 1 <= index <= len(sessions):
            target = sessions[index - 1]
        else:
            console.print(f"[red]序号 {index} 超出范围（共 {len(sessions)} 个）[/red]")
            return
    elif session_id:
        target = next((s for s in sessions if s.session_id.startswith(session_id)), None)
        if not target:
            console.print(f"[red]未找到 session_id 以 '{session_id}' 开头的会话[/red]")
            return
    else:
        # 交互式选择
        console.print("\n[bold]最近 10 个会话：[/bold]")
        for i, s in enumerate(sessions[:10], 1):
            size_str = f"{s.file_size/1024:.0f}KB"
            console.print(
                f"  [cyan]{i}[/cyan]. [{s.modified_time.strftime('%m-%d %H:%M')}] "
                f"[green]{s.display_name}[/green] ({size_str})"
                + (f"\n     [dim]{s.first_message}[/dim]" if s.first_message else "")
            )
        choice = IntPrompt.ask("\n请输入序号", default=1)
        if 1 <= choice <= min(10, len(sessions)):
            target = sessions[choice - 1]
        else:
            console.print("[red]无效序号[/red]")
            return

    # ── 展示会话信息 ──────────────────────────────────────────
    base_url_hint = f" → {resolved_base_url}" if resolved_base_url else ""
    console.print(Panel(
        f"[bold]Session ID:[/bold]  {target.session_id}\n"
        f"[bold]项目路径:[/bold]   {target.project_path}\n"
        f"[bold]最后修改:[/bold]   {target.modified_time.strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"[bold]文件大小:[/bold]   {target.file_size/1024:.1f} KB\n"
        f"[bold]提供商:[/bold]    {resolved_provider}{base_url_hint}\n"
        f"[bold]模型:[/bold]      {resolved_model}\n"
        f"[bold]首条消息:[/bold]   {target.first_message or '（无）'}",
        title="[bold blue]即将处理的会话[/bold blue]",
        border_style="blue",
    ))

    # ── 读取 & 解析 ───────────────────────────────────────────
    try:
        with console.status("[bold green]读取日志文件..."):
            raw_lines = load_session(target.file_path)
    except PermissionError:
        cmd = f"sudo chmod 644 '{target.file_path}'"
        console.print("[red]✗ 权限不足，该会话文件由 root 拥有[/red]")
        console.print("\n复制以下命令执行后重试：")
        console.print(Panel(cmd, style="bold yellow", expand=False))
        return

    console.print(f"[green]✓[/green] 读取完成，共 {len(raw_lines)} 条原始记录")

    with console.status("[bold green]解析日志结构..."):
        steps = parse_session(raw_lines)

    stats = get_session_stats(steps)
    tools_str = "、".join(
        f"{k}×{v}" for k, v in sorted(stats["tools_used"].items(), key=lambda x: -x[1])
    ) or "无"
    console.print(
        f"[green]✓[/green] 解析完成 │ "
        f"用户输入 {stats['user_inputs']}  思考 {stats['thinking']}  "
        f"工具调用 {stats['tool_calls']}（{tools_str}）"
    )

    if stats["total"] == 0:
        console.print("[yellow]警告：未解析到有效步骤，会话可能为空[/yellow]")
        return

    # ── 生成报告 ──────────────────────────────────────────────
    console.print(f"\n正在调用 [cyan]{resolved_provider}[/cyan] / [cyan]{resolved_model}[/cyan] 生成报告...")
    try:
        with console.status("[bold green]LLM 处理中，请稍候..."):
            report_md = generate_report(
                steps, target.display_name,
                resolved_provider, resolved_model, resolved_key, resolved_base_url,
            )
    except Exception as e:
        console.print(f"[red]✗ 生成报告失败：{e}[/red]")
        return

    console.print("[green]✓[/green] 报告生成完成！\n")

    # ── 输出报告 ──────────────────────────────────────────────
    # 确定输出路径：--output > config output_dir > 终端
    if resolved_out and not output:
        # 配置了默认目录，自动命名
        out_dir = Path(resolved_out).expanduser()
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"{target.display_name}_{target.session_id[:8]}.md"
        out_path.write_text(report_md, encoding="utf-8")
        console.print(f"[green]✓[/green] 报告已保存至：[bold]{out_path}[/bold]")
    elif output:
        out_path = Path(output)
        out_path.write_text(report_md, encoding="utf-8")
        console.print(f"[green]✓[/green] 报告已保存至：[bold]{out_path.absolute()}[/bold]")
    else:
        if no_render:
            print(report_md)
        else:
            console.rule("[bold blue]生成的学习报告[/bold blue]")
            console.print(Markdown(report_md))
            console.rule()
            console.print("[dim]提示：-o report.md 保存到文件；claude-buddy config set output-dir ~/reports 设置默认目录[/dim]")
