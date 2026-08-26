"""Tests for the pure schema/value helpers used by the dynamic CLI commands."""

import click
import pytest

from devin_mcp.cli import parse_value, resolve_schema_type


@pytest.mark.parametrize(
    ("prop_def", "expected"),
    [
        ({"type": "array"}, "array"),
        ({"anyOf": [{"type": "array", "items": {"type": "string"}}, {"type": "null"}]}, "array"),
        ({"anyOf": [{"type": "null"}, {"type": "integer"}]}, "integer"),
        ({"oneOf": [{"type": "object"}, {"type": "null"}]}, "object"),
        ({"type": ["string", "null"]}, "string"),
        ({}, None),
        ({"type": ["null"]}, None),
    ],
)
def test_resolve_schema_type(prop_def: dict, expected: str | None) -> None:
    assert resolve_schema_type(prop_def) == expected


@pytest.mark.parametrize(
    ("value", "json_type", "expected"),
    [
        ('["a","b"]', "array", ["a", "b"]),
        ("devin-0000000000000000000000000000abcd", "array", ["devin-0000000000000000000000000000abcd"]),
        ('{"a": 1}', "object", {"a": 1}),
        ("42", "integer", 42),
        ("true", "boolean", True),
    ],
)
def test_parse_value(value: str, json_type: str, expected: object) -> None:
    assert parse_value(value, json_type) == expected


@pytest.mark.parametrize(
    ("value", "json_type"),
    [
        ('["a"', "array"),
        ("not-json", "object"),
    ],
)
def test_parse_value_rejects_broken_json(value: str, json_type: str) -> None:
    with pytest.raises(click.BadParameter):
        parse_value(value, json_type)
