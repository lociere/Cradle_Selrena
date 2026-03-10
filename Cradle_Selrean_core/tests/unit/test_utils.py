import pytest
import sys, os
from pathlib import Path

# ensure src package available
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../src")))


# modules have been reorganized into subpackages
from selrena._internal.utils.data import dicts
from selrena._internal.utils.system import env
from selrena._internal.utils.io import path, yaml_io
from selrena._internal.utils.text import string



def test_dicts_path_operations():
    data = {}
    dicts.set_by_path(data, "a.b.c", 123)
    assert data == {"a": {"b": {"c": 123}}}
    assert dicts.get_by_path(data, "a.b.c") == 123
    assert dicts.has_path(data, "a.b.c")
    assert not dicts.has_path(data, "a.x")

    # merge
    dicts.merge_dicts(data, {"a": {"b": {"d": 456}, "x": 1}})
    assert data["a"]["b"]["d"] == 456

    updated, filled = dicts.fill_defaults({"k": 1}, {"k": 1, "m": 2})
    assert updated is True
    assert filled["m"] == 2


def test_env_helpers(tmp_path, monkeypatch):
    monkeypatch.setenv("TEST_BOOL", "true")
    monkeypatch.setenv("TEST_INT", "42")
    monkeypatch.setenv("TEST_FLOAT", "3.14")
    monkeypatch.setenv("TEST_LIST", "a,b,c")
    assert env.env_bool("TEST_BOOL")
    assert env.env_int("TEST_INT") == 42
    assert env.env_float("TEST_FLOAT") == 3.14
    assert env.env_list("TEST_LIST") == ["a", "b", "c"]


def test_path_helpers(tmp_path):
    # create a dummy file under project root to check relative path
    root = path.ProjectPath.PROJECT_ROOT
    # root should be the workspace directory, not the inner cradle-selrena package
    assert root.name == "Cradle_Selrena", f"unexpected project root: {root}"
    example = root / "example.txt"
    example.write_text("x")
    rel = path.get_relative_path(example)
    assert "example.txt" in rel


def test_string_clean_and_json():
    txt = "Hello [happy] world <think>secret</think> ```json {\"x\":1}```"
    cleaned = string.clean_text(txt, string.TextCleanOptions(remove_markdown_fences=True))
    assert "secret" not in cleaned

    json_txt = "Here is data: {\"a\": 2}"  # unwrapped
    parsed = string.extract_json_from_text(json_txt)
    assert parsed["a"] == 2


def test_yaml_io(tmp_path):
    p = tmp_path / "cfg.yaml"
    yaml_io.write_yaml(p, {"abc": 1})
    assert yaml_io.read_yaml(p)["abc"] == 1
    yaml_io.upsert_yaml(p, {"def": 2})
    assert yaml_io.read_yaml(p)["def"] == 2
