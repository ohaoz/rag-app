"""随包基础模型下载脚本（M2 §Phase 0，见 docs/M2-实施计划.md）。

把体积大的基础模型下载/准备到 ``engine/resources/models/``，运行期由
``docfactory.resources.find_models_dir()`` 定位（内置 resources/models 优先）。
这些资源**不入库**（见 engine/resources/.gitignore），由本脚本在构建期/CI 产出。

离线纪律：下载**只发生在构建期**（本脚本、CI 的 package 前置步骤），绝不进运行期代码；
引擎进程装了 offline_guard，运行时任何外联都会被拦。

当前实现：
- Qwen tokenizer（Apache-2.0）—— 让切片/导出的 token_count 从启发式估算切到与训练侧
  一致的真值（04 章 §3.2）。仅下 tokenizer.json（词表内嵌其中），不下模型权重。

后续（占位，接入各阶段时补）：
- layout(RT-DETR) + TableFormer（Docling，M2 §Phase 3）
- PP-OCRv5 mobile（RapidOCR，M2 §Phase 2）

用法::

    uv run python scripts/fetch_models.py            # 缺则下，已存在则跳过
    uv run python scripts/fetch_models.py --force     # 强制重下
    uv run python scripts/fetch_models.py --only qwen-tokenizer
"""

from __future__ import annotations

import argparse
import sys
import urllib.request
from pathlib import Path

# engine/ 根（本文件在 engine/scripts/ 下）
_ENGINE_ROOT = Path(__file__).resolve().parents[1]
_MODELS_ROOT = _ENGINE_ROOT / "resources" / "models"

# tokenizer.py 约定的位置：<models>/qwen-tokenizer/tokenizer.json
_QWEN_SUBDIR = "qwen-tokenizer"
_QWEN_FILE = "tokenizer.json"
# Qwen2.5 的 tokenizer.json（BPE 词表内嵌，约 7MB）。只取分词器，不取模型权重。
_QWEN_URL = "https://huggingface.co/Qwen/Qwen2.5-0.5B/resolve/main/tokenizer.json"

_UA = "docfactory-fetch-models/1.0 (+offline build step)"


def _download(url: str, dest: Path) -> int:
    """下载到临时文件再原子改名，返回字节数。失败抛异常由调用方汇报。"""
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".tmp")
    req = urllib.request.Request(url, headers={"User-Agent": _UA})  # noqa: S310 - 固定 https 源
    with urllib.request.urlopen(req, timeout=120) as resp:  # noqa: S310
        data = resp.read()
    tmp.write_bytes(data)
    tmp.replace(dest)
    return len(data)


def _verify_tokenizer(path: Path) -> str:
    """加载并试编码一段中英混排，确认文件可用；返回后端标识。"""
    from tokenizers import Tokenizer

    tok = Tokenizer.from_file(str(path))
    ids = tok.encode("交付期限为合同签订后 90 天。Delivery in 90 days.", add_special_tokens=False).ids
    if not ids:
        raise RuntimeError("tokenizer 编码结果为空")
    return f"ok（{len(ids)} tokens）"


def fetch_qwen_tokenizer(*, force: bool) -> None:
    dest = _MODELS_ROOT / _QWEN_SUBDIR / _QWEN_FILE
    if dest.is_file() and not force:
        print(f"[skip] Qwen tokenizer 已存在：{dest}（--force 可强制重下）")
        return
    print(f"[get ] {_QWEN_URL}")
    size = _download(_QWEN_URL, dest)
    verdict = _verify_tokenizer(dest)
    print(f"[done] {dest}  {size / 1024:.0f} KB  验证：{verdict}")


_FETCHERS = {"qwen-tokenizer": fetch_qwen_tokenizer}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="下载随包基础模型到 engine/resources/models/")
    parser.add_argument("--force", action="store_true", help="已存在也强制重下")
    parser.add_argument("--only", choices=sorted(_FETCHERS), help="只下指定项")
    args = parser.parse_args(argv)

    targets = [args.only] if args.only else list(_FETCHERS)
    failed: list[str] = []
    for name in targets:
        try:
            _FETCHERS[name](force=args.force)
        except Exception as exc:  # noqa: BLE001 - 汇总所有失败项一次性报告
            print(f"[FAIL] {name}: {type(exc).__name__}: {exc}", file=sys.stderr)
            failed.append(name)

    if failed:
        print(f"\n失败 {len(failed)} 项：{'、'.join(failed)}", file=sys.stderr)
        return 1
    print(f"\n全部完成，模型根：{_MODELS_ROOT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
