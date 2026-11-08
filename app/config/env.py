"""
环境变量统一入口

为什么要有这个模块：
    原来 6 个 config 模块 + logger + Mongo 客户端各自 import dotenv 并调用
    load_dotenv()，重复且容易漏；取值方式也各写各的，
    `float(os.getenv("LLM_DEFAULT_TEMPERATURE"))` 在缺值时还会直接 TypeError。

统一到这里的约定：
    1. .env 只加载一次（load_env 幂等），入口是 app/__init__.py；
    2. 读取一律走下面带默认值 + 类型校验的函数；
    3. 「没配」用默认值兜底，「配错了」直接抛错 —— 避免错误配置被悄悄当成默认值。
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# app/config/env.py -> 上两级就是项目根
PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = PROJECT_ROOT / ".env"

_loaded = False


def load_env() -> None:
    """加载项目根目录的 .env 文件，多次调用只生效一次"""
    global _loaded
    if _loaded:
        return
    load_dotenv(ENV_FILE)
    _loaded = True


def get_str(name: str, default: str = "") -> str:
    """读取字符串配置；未配置或为空串时返回默认值"""
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    return raw.strip()


def get_bool(name: str, default: bool = False) -> bool:
    """读取布尔配置：1/true/yes/y/on 为 True，0/false/no/n/off 为 False"""
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    value = raw.strip().lower()
    if value in ("1", "true", "yes", "y", "on"):
        return True
    if value in ("0", "false", "no", "n", "off"):
        return False
    raise ValueError(f"环境变量 {name}={raw!r} 不是合法的布尔值（可用 1/0/true/false）")


def get_float(name: str, default: float) -> float:
    """读取浮点配置；缺值时用默认值，配错时直接报错"""
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return float(raw)
    except ValueError as exc:
        raise ValueError(f"环境变量 {name}={raw!r} 不是合法的数字") from exc


def get_int(name: str, default: int) -> int:
    """读取整数配置；缺值时用默认值，配错时直接报错"""
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ValueError(f"环境变量 {name}={raw!r} 不是合法的整数") from exc


# 模块导入即加载，保证任何 `from app.config.env import ...` 之后环境变量已就绪
load_env()
