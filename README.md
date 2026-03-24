# Claude Buddy

**Turn your Claude Code sessions into structured learning reports.**

[中文文档](README_CN.md)

When Claude Code helps you build something, its full reasoning chain, task decomposition, and tool-use decisions are all recorded in local session logs — they're just not easy to read. **Claude Buddy** parses those logs and uses an LLM to generate a clean, structured report you can actually learn from.

```
$ claude-buddy report -i 3 -o report.md

✓ Loaded 412 raw records
✓ Parsed │ user inputs 5  thinking 18  tool calls 96 (Bash×51, Edit×22, Write×15…)
✓ Report generated → report.md
```

Each report covers:

1. **Requirement Understanding** — How the AI interpreted the user's request
2. **Task Decomposition** — How the requirement was broken into actionable steps
3. **Research Process** — What files were read and what context was gathered before coding
4. **Technical Design** — What approach was chosen and why
5. **Implementation Walkthrough** — Step-by-step breakdown of decisions and changes
6. **Problems & Solutions** — Obstacles encountered and how they were resolved
7. **Methodology Takeaways** — Reusable engineering patterns extracted from the session

---

## Requirements

- Python 3.11+
- [Claude Code](https://claude.ai/claude-code) installed and used at least once

## Installation

```bash
git clone https://github.com/your-username/claudeBuddy.git
cd claudeBuddy
pip install -e .
```

The `claude-buddy` command will be available globally after installation.

---

## Quick Start

```bash
# Step 1: Configure your LLM (one-time interactive wizard)
claude-buddy config setup

# Step 2: Browse your Claude Code session history
claude-buddy list

# Step 3: Generate a report for any session
claude-buddy report -i 1
```

---

## Configuration

Run `claude-buddy config setup` to launch the interactive wizard. The following providers are supported:

| Provider | Notes |
|----------|-------|
| **Anthropic** | Claude models — best report quality |
| **OpenAI** | GPT models |
| **Ollama** | Local models, no API key required |
| **Others** | Any service compatible with the OpenAI Chat Completions API (DeepSeek, Moonshot, etc.) |

Config is saved to `~/.claude-buddy/config.json` (chmod 600).

You can also set individual values:

```bash
claude-buddy config set api-key sk-ant-...
claude-buddy config set model claude-opus-4-6
claude-buddy config set output-dir ~/reports   # auto-save all reports here
claude-buddy config show
```

---

## Commands

### `claude-buddy list`

```bash
claude-buddy list              # show last 20 sessions
claude-buddy list -p myproject # filter by project name
claude-buddy list -n 50        # show more
```

### `claude-buddy report`

```bash
claude-buddy report            # interactive session picker
claude-buddy report -i 3       # pick by index (from list)
claude-buddy report -i 3 -o report.md          # save to file
claude-buddy report -i 3 -m claude-opus-4-6    # override model
claude-buddy report -i 3 -P ollama -m llama3.2 # override provider
claude-buddy report -i 3 --no-render           # plain Markdown output
```

**Priority order for API key**: CLI flag `-k` > environment variable > config file

### `claude-buddy config`

```bash
claude-buddy config setup      # interactive wizard
claude-buddy config show       # view all settings
claude-buddy config set <key> <value>
claude-buddy config get <key>
```

---

## How It Works

Claude Code writes every session to `~/.claude/projects/<project>/<session-id>.jsonl`. Each line is a JSON record containing:

- `thinking` — Claude's internal reasoning (task planning, trade-off analysis)
- `tool_use` — Tool invocations (Bash, Edit, Read, Write, Grep, etc.)
- `tool_result` — Tool outputs
- `text` — Claude's responses to the user

Claude Buddy reads these records, extracts the signal, compresses it into a structured digest, and sends it to an LLM to produce a human-readable report.

---

## Notes

- Some session files are owned by `root` (created via `sudo claude`). Fix permissions before reading:
  ```bash
  sudo chmod 644 ~/.claude/projects/**/*.jsonl
  ```
- Sessions larger than ~10 MB are automatically truncated to fit the model's context window
- macOS and Linux only (Claude Code stores logs at `~/.claude/`)

---

## Project Structure

```
claude_buddy/
├── collector.py   # session discovery and loading (~/.claude/projects/)
├── parser.py      # JSONL parsing (extracts thinking / tool_use / text)
├── reporter.py    # report generation (Anthropic SDK + OpenAI-compatible)
├── config.py      # config management (~/.claude-buddy/config.json)
└── main.py        # CLI entry point (click + rich)
```

---

## Contributing

Issues and pull requests are welcome.

---

## License

[MIT](LICENSE)
