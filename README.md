# Claude Buddy

> 把 Claude Code 的工作过程，变成你的编程学习材料。

当 Claude Code 帮你完成一个项目时，它的完整思考链、任务拆解逻辑、工具调用过程都记录在本地日志里——只是没有人帮你读懂它。**Claude Buddy** 做的事情很简单：把这些日志解析出来，交给 LLM，生成一篇结构化的教学报告。

```
$ claude-buddy report -i 3 -o report.md

✓ 读取完成，共 412 条原始记录
✓ 解析完成 │ 用户输入 5  思考 18  工具调用 96（Bash×51、Edit×22、Write×15…）
✓ 报告生成完成！→ report.md
```

**生成的报告包含：**
1. 需求理解 — AI 如何解读用户意图
2. 任务拆解策略 — 需求如何被分解为可执行步骤
3. 信息调研过程 — 动手前读了哪些文件、搜了什么
4. 技术方案设计 — 选了什么方案，为什么
5. 实现过程详解 — 每步做了什么、决策逻辑是什么
6. 问题与应对 — 遇到了什么障碍，如何诊断和解决
7. 方法论总结 — 可复用的工程思维要点

---

## 安装

**要求**：Python 3.11+，已安装并使用过 [Claude Code](https://claude.ai/claude-code)

```bash
git clone https://github.com/your-username/claudeBuddy.git
cd claudeBuddy
pip install -e .
```

安装后 `claude-buddy` 命令全局可用。

---

## 快速开始

```bash
# 第一步：配置（交互式向导，一次性）
claude-buddy config setup

# 第二步：查看你的历史会话
claude-buddy list

# 第三步：选一个会话生成报告
claude-buddy report -i 1
```

---

## 配置

运行 `claude-buddy config setup` 进入交互式向导，支持以下提供商：

| 提供商 | 说明 |
|--------|------|
| **Anthropic** | Claude 系列，效果最佳 |
| **OpenAI** | GPT 系列 |
| **Ollama** | 本地模型，无需 API Key |
| **其他** | 任何兼容 OpenAI Chat Completions 接口的服务（DeepSeek、Moonshot 等） |

配置持久保存在 `~/.claude-buddy/config.json`（文件权限 600，仅当前用户可读）。

也可以单独设置：

```bash
claude-buddy config set api-key sk-ant-...
claude-buddy config set model claude-opus-4-6
claude-buddy config set output-dir ~/reports   # 设置后报告自动保存
claude-buddy config show                        # 查看当前配置
```

---

## 命令参考

### `claude-buddy list`

```bash
claude-buddy list              # 列出最近 20 个会话
claude-buddy list -p rag       # 按项目名过滤
claude-buddy list -n 50        # 显示更多
```

### `claude-buddy report`

```bash
claude-buddy report            # 交互式选择会话
claude-buddy report -i 3       # 用序号指定会话（来自 list）
claude-buddy report -i 3 -o report.md          # 保存到文件
claude-buddy report -i 3 -m claude-opus-4-6    # 临时换模型
claude-buddy report -i 3 -P ollama -m llama3.2 # 临时换提供商
claude-buddy report -i 3 --no-render           # 输出纯文本
```

**参数优先级**：命令行选项 > 环境变量（`ANTHROPIC_API_KEY` / `OPENAI_API_KEY`）> 配置文件

### `claude-buddy config`

```bash
claude-buddy config setup      # 交互式配置向导
claude-buddy config show       # 查看所有配置
claude-buddy config set <key> <value>
claude-buddy config get <key>
```

---

## 工作原理

Claude Code 将每个会话的完整日志存储在 `~/.claude/projects/<project>/<session-id>.jsonl`，每行一条 JSON 记录，包含：

- `thinking` — Claude 的思考过程（任务拆解、方案选择）
- `tool_use` — 工具调用（Bash、Edit、Read、Write 等）
- `tool_result` — 工具返回结果
- `text` — Claude 对用户的回复

Claude Buddy 解析这些记录，压缩为结构化摘要，交给 LLM 生成可读的教学报告。

---

## 注意事项

- 部分会话文件由 `root` 用户创建（通过 `sudo claude` 运行时），需要修复权限才能读取：
  ```bash
  sudo chmod 644 ~/.claude/projects/**/*.jsonl
  ```
- 大型会话（>10MB）会自动截断以适应模型上下文窗口
- 仅支持 macOS / Linux（Claude Code 日志路径为 `~/.claude/`）

---

## Contributing

欢迎提交 Issue 和 Pull Request。

```bash
git clone https://github.com/your-username/claudeBuddy.git
cd claudeBuddy
pip install -e .
```

项目结构：

```
claude_buddy/
├── collector.py   # 会话发现与加载（读取 ~/.claude/projects/）
├── parser.py      # JSONL 日志解析（提取 thinking / tool_use / text）
├── reporter.py    # LLM 报告生成（支持 Anthropic / OpenAI 兼容接口）
├── config.py      # 配置管理（~/.claude-buddy/config.json）
└── main.py        # CLI 入口（click + rich）
```

---

## License

[MIT](LICENSE)
