"""随包资源（模型 / 二进制）目录解析（M2 §Phase 0，见 docs/M2-实施计划.md）。

背景：M2 的 layout / TableFormer / OCR / Qwen tokenizer 基础模型 ~270MB，随安装包进
``resources/models/``（运行期只读）；高精度模型经 ``.kmod`` 装到数据根 ``modules/``（M4）。
模型体积大，**不走 PyInstaller 的 datas**（会让 onedir 暴涨、analysis 变慢），而是经
electron-builder 的 extraResources 与引擎目录并列打进安装包。

本模块给出「基础模型根目录」的统一解析，与 ``parsers/office_convert.find_soffice()``
定位裁剪版 LibreOffice 的思路一致（env → 内置 resources → 兜底）：

    env DOCFACTORY_MODELS_DIR → 内置 resources/models → 数据根 models/（开发填充/未来 .kmod）

都找不到则返回 None，由调用方降级为「该模型能力不可用」——沿用 M1 既有的降级语义
（如 tokenizer 回退启发式、docling/ocr 钩子返回 None 落 L1/L2），绝不联网下载。
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# 环境变量覆盖（开发机 / 自定义模型位置）
MODELS_ENV_KEY = "DOCFACTORY_MODELS_DIR"

# 安装目录内置位置：打包后引擎 exe 在 resources/engine/，模型在 resources/models/；
# 开发态则从仓库往下找。两种布局都试一遍，避免开发/生产两套逻辑。
_BUNDLED_MODELS_RELATIVE = Path("resources") / "models"


def _bundled_candidates(relative: Path) -> list[Path]:
    """内置资源的候选根目录（与 office_convert._bundled_candidates 同款探测）。

    打包后（PyInstaller onedir）从引擎 exe 目录上溯，开发态从本文件上溯，
    各取数级父目录拼上 ``relative``，去重后返回。
    """
    roots: list[Path] = []
    exe_dir = Path(sys.executable).resolve().parent
    roots.extend([exe_dir, *exe_dir.parents[:3]])
    here = Path(__file__).resolve()
    roots.extend(here.parents[:6])

    seen: set[Path] = set()
    out: list[Path] = []
    for root in roots:
        cand = root / relative
        if cand not in seen:
            seen.add(cand)
            out.append(cand)
    return out


def find_models_dir(data_models: Path | None = None) -> Path | None:
    """基础模型根目录：env → 内置 resources/models → 数据根 models/；都无则 None。

    返回的目录**保证存在**（供 docling/ocr 这类需要真实目录的调用方直接用）；
    ``data_models`` 一般传 ``paths.models``，作为开发期手工填充 / 未来 .kmod 的兜底。
    tokenizer 侧另有「即便目录暂不存在也照探一遍」的宽松需求，见 tokenizer._default_models_dir。
    """
    env = os.environ.get(MODELS_ENV_KEY, "").strip().strip('"')
    if env:
        p = Path(env)
        if p.is_dir():
            return p

    for cand in _bundled_candidates(_BUNDLED_MODELS_RELATIVE):
        if cand.is_dir():
            return cand

    if data_models is not None:
        dm = Path(data_models)
        if dm.is_dir():
            return dm
    return None
