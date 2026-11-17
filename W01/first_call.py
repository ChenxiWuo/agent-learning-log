"""首次调用 DeepSeek —— W1 Day1 产出「首次调用」

用法（在 W01 目录下）：
    1) 把 .env.example 复制成 .env，填上你的 DEEPSEEK_API_KEY
    2) uv run python first_call.py

这个脚本要让你亲眼看到三件事：
    ① DeepSeek 走的是 OpenAI 兼容协议 —— 换 base_url 就能复用整套 SDK 生态；
    ② 一次调用花了多少 token（成本的最小单位）；
    ③ 成本随时段变化（忙时/闲时差一倍），所以「成本」是设计出来的，不是省出来的。
"""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

from openai import OpenAI

HERE = Path(__file__).resolve().parent
BASE_URL = "https://api.deepseek.com"
MODEL = "deepseek-flash"


def load_env() -> None:
    """.env 是最简陋的配置方式，但你需要知道它做了什么：KEY=VALUE 逐行塞进环境变量。

    生产环境别用 .env 存密钥，用平台的 Secret 管理（W5 部署时会遇到）。
    """
    env_file = HERE / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def is_peak(now_utc: datetime) -> bool:
    """忙时 = 周一至周五 UTC 01:00-04:00 与 06:00-10:00（北京时间的上午和下午）。"""
    if now_utc.weekday() >= 5:  # 5=周六 6=周日
        return False
    hour = now_utc.hour
    return (1 <= hour < 4) or (6 <= hour < 10)


def estimate_cost(usage, pricing: dict, peak: bool) -> dict:
    """按 1M token 单价折算美元；cache hit 比 miss 便宜 20~50 倍，这是上下文复用的钱。"""
    m = pricing["models"][MODEL]
    ratio = 1.0 if peak else pricing["off_peak_multiplier"]
    hit = getattr(usage, "prompt_cache_hit_tokens", 0) or 0
    miss = getattr(usage, "prompt_cache_miss_tokens", 0) or usage.prompt_tokens
    out = usage.completion_tokens
    usd = (hit * m["cache_hit"] + miss * m["cache_miss"] + out * m["output"]) / 1_000_000 * ratio
    return {"cache_hit_tokens": hit, "cache_miss_tokens": miss, "output_tokens": out, "usd": usd, "peak": peak}


def main() -> int:
    load_env()
    if not os.environ.get("DEEPSEEK_API_KEY"):
        print("[X] 没找到 DEEPSEEK_API_KEY。请复制 .env.example 为 .env 并填入密钥。")
        print("    申请地址：https://platform.deepseek.com/api_keys")
        return 1

    client = OpenAI(api_key=os.environ["DEEPSEEK_API_KEY"], base_url=BASE_URL)
    messages = [
        {"role": "system", "content": "你是一位带我的资深 Agent 工程师，回答控制在 3 句话内。"},
        {"role": "user", "content": "用一句话说明 RAG 里「引用」为什么比「答案对不对」更值得先做。"},
    ]

    t0 = time.perf_counter()
    resp = client.chat.completions.create(model=MODEL, messages=messages, temperature=0.3)
    latency = time.perf_counter() - t0

    content = resp.choices[0].message.content
    print("=" * 60)
    print(content)
    print("=" * 60)

    price = json.loads((HERE / "pricing.json").read_text(encoding="utf-8"))
    now = datetime.now(timezone.utc)
    cost = estimate_cost(resp.usage, price, is_peak(now))

    print(f"模型      {MODEL}（{resp.model}）")
    print(f"延迟      {latency:.2f}s")
    print(f"输入      {resp.usage.prompt_tokens} tokens（cache 命中 {cost['cache_hit_tokens']}）")
    print(f"输出      {resp.usage.completion_tokens} tokens")
    print(f"时段      {'忙时' if cost['peak'] else '闲时'}（UTC {now:%H:%M}）")
    print(f"本次成本  ${cost['usd']:.6f}  ≈ ¥{cost['usd'] * 7.1:.4f}")

    # 追加一行账本：W1D4「统计 20 次调用」直接用这个文件跑统计
    record = {
        "ts": now.isoformat(timespec="seconds"),
        "model": MODEL,
        "latency_s": round(latency, 3),
        "prompt_tokens": resp.usage.prompt_tokens,
        "completion_tokens": resp.usage.completion_tokens,
        "peak": cost["peak"],
        "usd": round(cost["usd"], 8),
    }
    with (HERE / "calls.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
    print("已记账 → calls.jsonl（每行一次调用，W1D4 用它出成本表）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
