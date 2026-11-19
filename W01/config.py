"""config.py — 配置的唯一入口。

规矩：除了这个文件，任何地方都不许读环境变量、不许打开 .env。
"""

from __future__ import annotations

import os
from pathlib import Path

from pydantic import BaseModel, Field, ValidationError, field_validator

ENV_FILE = Path(__file__).resolve().parent / ".env"


class ConfigError(RuntimeError):
    """配置阶段的错误。和业务错误分开，方便上层决定"退出"还是"重试"。"""


class Settings(BaseModel):
    api_key: str = Field(..., description="DeepSeek 的 sk- key")
    base_url: str = "https://api.deepseek.com"
    model: str = "deepseek-flash"
    temperature: float = Field(0.3, ge=0.0, le=2.0)
    max_tokens: int = Field(1024, ge=1)

    @field_validator("api_key")
    @classmethod
    def _check_key(cls, v: str) -> str:
        v = v.strip()
        if not v.startswith("sk-"):
            raise ValueError("api_key 必须以 'sk-' 开头")
        return v

    @classmethod
    def from_env(cls, env_file: Path = ENV_FILE) -> "Settings":
        # ① 读 .env，把 KEY=VALUE 塞进环境变量
        if env_file.exists():
            for raw in env_file.read_text(encoding="utf-8-sig").splitlines():
                line = raw.strip()  # 去掉首尾空白（含 \r）
                if not line:  # 空行
                    continue
                if line.startswith("#"):  # 注释行
                    continue
                if "=" not in line:  # 没有等号，不是配置
                    continue
                key, value = line.split("=", 1)  # 只切第一个等号
                os.environ.setdefault(  # 真实环境变量优先
                    key.strip(),
                    value.strip().strip('"').strip("'"),  # 去掉包裹的引号
                )

        # ② 从环境变量取值，交给 pydantic 校验和转换
        try:
            return cls(
                api_key=os.environ.get("DEEPSEEK_API_KEY", ""),
                base_url=os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
                model=os.environ.get("DEEPSEEK_MODEL", "deepseek-flash"),
                temperature=os.environ.get("DEEPSEEK_TEMPERATURE", "0.3"),
                max_tokens=os.environ.get("DEEPSEEK_MAX_TOKENS", "1024"),
            )
        except ValidationError as exc:
            # ③ 把 pydantic 的英文堆栈翻译成人话
            problems = "；".join(
                f"{'.'.join(str(p) for p in err['loc'])} → {err['msg']}"
                for err in exc.errors()
            )
            raise ConfigError(
                f"配置有问题：{problems}\n请检查 {env_file} 里的 DEEPSEEK_API_KEY 是否已填写。"
            ) from exc

    def __repr__(self) -> str:  # 4 格
        masked = (self.api_key[:5] + "***") if self.api_key else "<未设置>"  # 8 格
        return (  # 8 格
            f"Settings(api_key='{masked}', base_url='{self.base_url}', "  # 12 格
            f"model='{self.model}', temperature={self.temperature}, "  # 12 格
            f"max_tokens={self.max_tokens})"  # 12 格
        )

    __str__ = __repr__  # 4 格 ← 和 def 对齐，这是关键