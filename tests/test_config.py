import json

from guardcode.config import (
    apply_env_overrides,
    dict_to_config,
    load_config,
    merge_configs,
)


def test_merge_configs_recursively_preserves_unoverridden_values():
    result = merge_configs(
        {"model": "base", "security": {"always_block": ["a"], "auto_approve": []}},
        {"security": {"auto_approve": ["b"]}},
    )

    assert result == {
        "model": "base",
        "security": {"always_block": ["a"], "auto_approve": ["b"]},
    }


def test_apply_env_overrides_parses_supported_values(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "secret")
    monkeypatch.setenv("OPENAI_API_BASE", "https://api.example/v1")
    monkeypatch.setenv("GUARDCODE_MODEL", "model-x")
    monkeypatch.setenv("GUARDCODE_MAX_ITERATIONS", "7")
    monkeypatch.setenv("GUARDCODE_VERBOSE", "yes")

    result = apply_env_overrides({"model": "old", "max_iterations": 2})

    assert result == {
        "api_key": "secret",
        "api_base": "https://api.example/v1",
        "model": "model-x",
        "max_iterations": 7,
        "verbose": True,
    }


def test_apply_env_overrides_ignores_invalid_iteration_count(monkeypatch):
    monkeypatch.setenv("GUARDCODE_MAX_ITERATIONS", "not-an-integer")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_BASE", raising=False)
    monkeypatch.delenv("GUARDCODE_MODEL", raising=False)
    monkeypatch.delenv("GUARDCODE_VERBOSE", raising=False)

    assert apply_env_overrides({"max_iterations": 3}) == {"max_iterations": 3}


def test_dict_to_config_builds_nested_defaults_and_values():
    config = dict_to_config(
        {
            "api_key": "key",
            "security": {"always_block": ["rm -rf /"]},
            "context": {"keep_recent_messages": 8},
        }
    )

    assert config.api_key == "key"
    assert config.security.always_block == ["rm -rf /"]
    assert config.security.auto_approve == []
    assert config.context.keep_recent_messages == 8
    assert config.context.max_context_size == 100000


def test_load_config_applies_env_then_project_then_explicit_file(
    tmp_path, monkeypatch
):
    """新优先级：默认 < 全局 < 环境变量 < 项目配置 < 命令行配置"""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / ".guardcode.json").write_text(
        json.dumps({"model": "project", "security": {"always_block": ["project"]}}),
        encoding="utf-8",
    )
    explicit = tmp_path / "explicit.json"
    explicit.write_text(
        json.dumps({"model": "explicit", "security": {"auto_approve": ["safe"]}}),
        encoding="utf-8",
    )
    monkeypatch.setenv("GUARDCODE_MODEL", "environment")

    config = load_config(str(explicit), str(workspace))

    # 命令行配置优先级最高
    assert config.model == "explicit"
    # 项目配置的 always_block 保留
    assert config.security.always_block == ["project"]
    # 命令行配置的 auto_approve 保留
    assert config.security.auto_approve == ["safe"]
