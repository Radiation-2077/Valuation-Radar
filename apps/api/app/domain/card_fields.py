from __future__ import annotations


def display_label(value: object, default: str = "") -> str:
    """Read a legacy string or a v1.2 code/label object for display."""
    if isinstance(value, str):
        return value or default
    if isinstance(value, dict):
        label = value.get("label")
        if isinstance(label, str) and label:
            return label
        code = value.get("code")
        if isinstance(code, str) and code:
            return code
    return default


def confidence_label(value: object, default: str = "中") -> str:
    return display_label(value, default)
