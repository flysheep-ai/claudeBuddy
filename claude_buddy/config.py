"""
配置管理：读写 ~/.claude-buddy/config.json
"""
import json
import os
from pathlib import Path

CONFIG_DIR = Path.home() / ".claude-buddy"
CONFIG_FILE = CONFIG_DIR / "config.json"

VALID_KEYS = {
    "provider":   "LLM 提供商（anthropic / openai / ollama / 其他兼容 OpenAI 接口的服务）",
    "api_key":    "API Key（Anthropic: sk-ant-... | OpenAI: sk-... | Ollama: 留空即可）",
    "model":      "默认生成模型（claude-sonnet-4-6 / gpt-4o / llama3.2 等）",
    "base_url":   "自定义 API 地址（Ollama: http://localhost:11434/v1，留空使用提供商默认值）",
    "output_dir": "默认报告输出目录（留空则打印到终端）",
}

DEFAULTS: dict[str, str] = {
    "provider":   "anthropic",
    "api_key":    "",
    "model":      "claude-sonnet-4-6",
    "base_url":   "",
    "output_dir": "",
}

# 各提供商对应的环境变量名
_PROVIDER_ENV_VARS: dict[str, str] = {
    "anthropic": "ANTHROPIC_API_KEY",
    "openai":    "OPENAI_API_KEY",
}


def load() -> dict[str, str]:
    """读取配置文件，合并默认值；环境变量优先级高于配置文件"""
    cfg = DEFAULTS.copy()
    if CONFIG_FILE.exists():
        try:
            saved = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            cfg.update({k: v for k, v in saved.items() if k in DEFAULTS})
        except (json.JSONDecodeError, OSError):
            pass
    # 根据当前 provider 读取对应的环境变量
    env_var = _PROVIDER_ENV_VARS.get(cfg["provider"], "")
    if env_var and os.environ.get(env_var):
        cfg["api_key"] = os.environ[env_var]
    return cfg


def save(cfg: dict[str, str]) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")
    CONFIG_FILE.chmod(0o600)   # 保护 API Key 不被其他用户读取


def get(key: str) -> str:
    return load().get(key, "")


def set_value(key: str, value: str) -> None:
    if key not in VALID_KEYS:
        raise ValueError(f"未知配置项 '{key}'，可用项：{list(VALID_KEYS)}")
    cfg = load()
    cfg[key] = value
    save(cfg)
