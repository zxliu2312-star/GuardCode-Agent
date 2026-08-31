"""
Tests for 2.7: 配置文件扩展

验证 security 字段的加载、全局/项目配置合并、项目覆盖全局。
"""

import json
import pytest
from pathlib import Path

from guardcode.config import (
    Config,
    SecurityConfig,
    load_config,
    load_config_from_file,
    merge_configs,
    dict_to_config,
)


class TestSecurityConfigFields:
    """验证 security 字段的加载。"""

    def test_security_always_block_loaded(self, tmp_path):
        """always_block 从项目配置加载。"""
        config_file = tmp_path / ".guardcode.json"
        config_file.write_text(json.dumps({
            "security": {"always_block": [r"rm -rf /", r"format\s+"]}
        }), encoding="utf-8")

        config = load_config(workspace=str(tmp_path))
        assert config.security.always_block == [r"rm -rf /", r"format\s+"]

    def test_security_auto_approve_loaded(self, tmp_path):
        """auto_approve 从项目配置加载。"""
        config_file = tmp_path / ".guardcode.json"
        config_file.write_text(json.dumps({
            "security": {"auto_approve": [r"pip install", r"npm install"]}
        }), encoding="utf-8")

        config = load_config(workspace=str(tmp_path))
        assert config.security.auto_approve == [r"pip install", r"npm install"]

    def test_security_both_fields_loaded(self, tmp_path):
        """同时加载 always_block 和 auto_approve。"""
        config_file = tmp_path / ".guardcode.json"
        config_file.write_text(json.dumps({
            "security": {
                "always_block": [r"rm -rf"],
                "auto_approve": [r"echo\s+"],
            }
        }), encoding="utf-8")

        config = load_config(workspace=str(tmp_path))
        assert config.security.always_block == [r"rm -rf"]
        assert config.security.auto_approve == [r"echo\s+"]

    def test_security_defaults_empty(self, tmp_path):
        """没有 security 字段时默认为空列表。"""
        config = load_config(workspace=str(tmp_path))
        assert config.security.always_block == []
        assert config.security.auto_approve == []


class TestGlobalConfig:
    """验证全局配置加载。"""

    def test_global_config_loaded(self, tmp_path, monkeypatch):
        """全局配置 ~/.guardcode/config.json 被加载。"""
        fake_home = tmp_path / "home"
        fake_home.mkdir()
        global_dir = fake_home / ".guardcode"
        global_dir.mkdir()
        (global_dir / "config.json").write_text(json.dumps({
            "model": "global-model",
            "security": {"always_block": ["rm"]}
        }), encoding="utf-8")

        monkeypatch.setattr(Path, "home", lambda: fake_home)

        config = load_config(workspace=str(tmp_path))
        assert config.model == "global-model"
        assert config.security.always_block == ["rm"]


class TestProjectOverridesGlobal:
    """验证项目配置覆盖全局配置。"""

    def test_project_overrides_global(self, tmp_path, monkeypatch):
        """项目 .guardcode.json 覆盖全局 config.json。"""
        fake_home = tmp_path / "home"
        fake_home.mkdir()
        global_dir = fake_home / ".guardcode"
        global_dir.mkdir()
        (global_dir / "config.json").write_text(json.dumps({
            "model": "global-model",
            "security": {
                "always_block": ["rm"],
                "auto_approve": ["echo"],
            }
        }), encoding="utf-8")

        monkeypatch.setattr(Path, "home", lambda: fake_home)

        workspace = tmp_path / "workspace"
        workspace.mkdir()
        (workspace / ".guardcode.json").write_text(json.dumps({
            "model": "project-model",
            "security": {"always_block": ["format"]}
        }), encoding="utf-8")

        config = load_config(workspace=str(workspace))
        # 项目覆盖全局
        assert config.model == "project-model"
        # always_block 被项目覆盖（不是合并）
        assert config.security.always_block == ["format"]
        # auto_approve 全局保留（项目没覆盖）
        assert config.security.auto_approve == ["echo"]


class TestExplicitConfigFile:
    """验证命令行 --config 优先级最高。"""

    def test_explicit_overrides_project(self, tmp_path, monkeypatch):
        """命令行配置文件覆盖项目配置。"""
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_API_BASE", raising=False)
        monkeypatch.delenv("GUARDCODE_MODEL", raising=False)

        workspace = tmp_path / "ws"
        workspace.mkdir()
        (workspace / ".guardcode.json").write_text(json.dumps({
            "model": "project",
            "security": {"always_block": ["project-block"]}
        }), encoding="utf-8")

        explicit = tmp_path / "explicit.json"
        explicit.write_text(json.dumps({
            "model": "explicit",
            "security": {"auto_approve": ["explicit-approve"]}
        }), encoding="utf-8")

        config = load_config(str(explicit), str(workspace))
        assert config.model == "explicit"
        assert config.security.always_block == ["project-block"]
        assert config.security.auto_approve == ["explicit-approve"]


class TestConfigMergeSecurity:
    """验证 security 字段的递归合并。"""

    def test_merge_preserves_unoverridden_security(self):
        """合并时保留未被覆盖的 security 子字段。"""
        base = {
            "security": {"always_block": ["a"], "auto_approve": ["b"]}
        }
        override = {
            "security": {"always_block": ["c"]}
        }
        result = merge_configs(base, override)
        assert result["security"]["always_block"] == ["c"]
        assert result["security"]["auto_approve"] == ["b"]
