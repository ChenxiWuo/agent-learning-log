"""环境自检 —— W1 Day1 产出「环境清单」

用法（在 W01 目录下）：
    python check_env.py

只依赖标准库，任何 Python 3.10+ 都能跑；结果同时打印和写入 环境清单.md。

【今天顺手学到的坑】中文 Windows 的控制台默认是 GBK(cp936)，遇到 ✅ 这类
emoji 会直接 UnicodeEncodeError 崩掉。工程上的处理是：终端只输出 GBK 安全字符，
图标留给 UTF-8 文件。别用「改控制台编码」硬扛，换台机器又崩。
"""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent

# (命令名, 取版本参数, 最低要求)
TOOLS = [
    ("python", ["--version"], "3.10+"),
    ("uv", ["--version"], "任意新版"),
    ("git", ["--version"], "任意新版"),
    ("node", ["--version"], "20+"),
    ("docker", ["--version"], "20+"),
]

# (名称, URL, 用途)
ENDPOINTS = [
    ("PyPI", "https://pypi.org/simple/", "装依赖"),
    ("DeepSeek API", "https://api.deepseek.com", "调用模型"),
]

ICON = {"ok": "✅", "warn": "⚠️", "bad": "❌"}
TAG = {"ok": "[OK] ", "warn": "[!]  ", "bad": "[X]  "}


def tool_version(name: str, args: list[str]) -> str | None:
    """工具在 PATH 里就返回版本号第一行；不在返回 None。"""
    if shutil.which(name) is None:
        return None
    try:
        p = subprocess.run(
            [name, *args],
            capture_output=True,
            text=True,
            timeout=20,
            encoding="utf-8",
            errors="replace",
        )
        text = (p.stdout or p.stderr).strip()
        return text.splitlines()[0] if text else "(无输出)"
    except Exception as exc:  # 单个工具探测失败不该让整份清单失败
        return f"(探测失败: {exc})"


def reachable(url: str) -> tuple[bool, str]:
    """能不能连上？注意：服务器回了 401/404 也算「通」——它答话了，只是内容不对。

    真正的「不通」是 DNS 解析失败、连接被重置、超时（URLError/OSError）。
    这就是排障第一原则：先分清「网络层不通」和「应用层拒绝」。
    """
    try:
        req = urllib.request.Request(url, method="HEAD")
        with urllib.request.urlopen(req, timeout=10) as resp:
            return True, f"HTTP {resp.status}"
    except urllib.error.HTTPError as exc:  # 服务器答话了，只是拒绝我们
        return True, f"HTTP {exc.code}（可达，未鉴权）"
    except Exception as exc:
        return False, type(exc).__name__


def main() -> int:
    rows: list[dict] = []

    def add(item: str, value: str, status: str, note: str) -> None:
        rows.append({"item": item, "value": value, "status": status, "note": note})

    add("操作系统", platform.platform(), "ok", "—")
    add("CPU 核心数", str(os.cpu_count()), "ok", "—")
    py_ok = sys.version_info >= (3, 10)
    add("Python", f"{platform.python_version()}  {sys.executable}", "ok" if py_ok else "bad", "需 ≥3.10")

    missing: list[str] = []
    for name, args, need in TOOLS:
        ver = tool_version(name, args)
        if ver is None:
            missing.append(name)
            add(name, "未安装 / 不在 PATH", "bad", f"需 {need}")
        else:
            status = "bad" if ver.startswith("(探测失败") else "ok"
            add(name, ver, status, f"需 {need}")

    for label, url, use in ENDPOINTS:
        ok, detail = reachable(url)
        add(f"网络 · {label}", url, "ok" if ok else "bad", f"{detail}｜用途：{use}")

    in_venv = sys.prefix != sys.base_prefix
    add(
        "虚拟环境",
        sys.prefix if in_venv else "未激活，当前用系统 Python",
        "ok" if in_venv else "warn",
        "建议 uv sync 后用 .venv",
    )

    # 终端输出：只用 GBK 能编码的字符
    print(f"\n=== 环境自检 {datetime.now():%Y-%m-%d %H:%M} ===")
    for r in rows:
        print(f"{TAG[r['status']]}{r['item']}: {r['value']}")
    bad = [r["item"] for r in rows if r["status"] == "bad"]
    print("\n结论：" + ("全部就绪，可以开始 Day1 第 2 步" if not bad else "待补：" + "、".join(bad)))

    # 文件输出：UTF-8 + 图标，给简历/复盘看
    md = [f"# 环境清单（{datetime.now():%Y-%m-%d}）", "", "| 项 | 值 | 状态 | 说明 |", "|---|---|---|---|"]
    md += [f"| {r['item']} | {r['value']} | {ICON[r['status']]} | {r['note']} |" for r in rows]
    md += ["", "## 待办", ""]
    md += [f"- [ ] 安装 `{m}`" for m in missing] or ["- [x] 工具链齐全"]
    if not in_venv:
        md += ["- [ ] 在 W01 下执行 `uv sync`，之后用 `uv run python xxx.py` 跑脚本"]
    md += [
        "- [ ] 填写 `.env` 里的 `DEEPSEEK_API_KEY`，运行 `uv run python first_call.py`",
        "- [ ] 在 `notes/W01-D1.md` 写一句：这次调用花了多少 token、多少钱",
    ]

    out = HERE / "环境清单.md"
    out.write_text("\n".join(md) + "\n", encoding="utf-8")
    print(f"已写入 {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
