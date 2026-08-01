"""模型资源目录解析测试（M2 §Phase 0，resources.find_models_dir）。

锁定解析优先级 env → 内置 resources/models → 数据根 models/ → None，以及
「返回的目录保证存在、内置优先于数据根、候选路径结构正确」。
内置分支依赖真实文件系统布局，测试里用 monkeypatch 把 _bundled_candidates 换成
可控返回值来隔离，避免仓库将来真出现 resources/models 时结果漂移。
"""

from __future__ import annotations

from docfactory.resources import (
    _BUNDLED_MODELS_RELATIVE,
    _bundled_candidates,
    find_models_dir,
)

_NO_BUNDLED = "docfactory.resources._bundled_candidates"


def test_env_override_wins(tmp_path, monkeypatch):
    d = tmp_path / "models"
    d.mkdir()
    monkeypatch.setenv("DOCFACTORY_MODELS_DIR", str(d))
    # env 优先级最高，连 data_models 都不看
    assert find_models_dir(tmp_path / "other") == d


def test_env_ignored_when_dir_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("DOCFACTORY_MODELS_DIR", str(tmp_path / "nope"))
    monkeypatch.setattr(_NO_BUNDLED, lambda rel: [])
    data = tmp_path / "data-models"
    data.mkdir()
    # env 指向不存在的目录 → 忽略，落到 data_models
    assert find_models_dir(data) == data


def test_bundled_preferred_over_data(tmp_path, monkeypatch):
    monkeypatch.delenv("DOCFACTORY_MODELS_DIR", raising=False)
    bundled = tmp_path / "res-models"
    bundled.mkdir()
    data = tmp_path / "data-models"
    data.mkdir()
    monkeypatch.setattr(_NO_BUNDLED, lambda rel: [bundled])
    # 内置 resources/models 优先于数据根 models/
    assert find_models_dir(data) == bundled


def test_data_models_fallback(tmp_path, monkeypatch):
    monkeypatch.delenv("DOCFACTORY_MODELS_DIR", raising=False)
    monkeypatch.setattr(_NO_BUNDLED, lambda rel: [])
    data = tmp_path / "m"
    data.mkdir()
    assert find_models_dir(data) == data


def test_none_when_nothing_exists(tmp_path, monkeypatch):
    monkeypatch.delenv("DOCFACTORY_MODELS_DIR", raising=False)
    monkeypatch.setattr(_NO_BUNDLED, lambda rel: [])
    # 数据根不存在 + 无内置 + 无 env → None（调用方据此降级为「模型能力不可用」）
    assert find_models_dir(tmp_path / "does-not-exist") is None
    assert find_models_dir(None) is None


def test_returned_dir_always_exists(tmp_path, monkeypatch):
    monkeypatch.delenv("DOCFACTORY_MODELS_DIR", raising=False)
    monkeypatch.setattr(_NO_BUNDLED, lambda rel: [])
    result = find_models_dir(tmp_path / "m")  # 不存在
    assert result is None  # 决不返回不存在的路径


def test_bundled_candidates_shape():
    cands = _bundled_candidates(_BUNDLED_MODELS_RELATIVE)
    assert cands, "候选列表不应为空"
    # 每个候选都以 resources/models 结尾
    assert all(c.parts[-2:] == ("resources", "models") for c in cands)
    # 去重
    assert len(cands) == len(set(cands))
