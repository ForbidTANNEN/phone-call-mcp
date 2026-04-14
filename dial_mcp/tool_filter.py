WRITE_PATTERNS = [
    "create", "update", "delete", "write", "send",
    "post", "put", "patch", "remove", "add", "set", "modify",
]


def filter_write_tools(tool_names: list[str]) -> list[str]:
    """Filter out tools that match write patterns. Returns read-only tool names."""
    result = []
    for name in tool_names:
        name_lower = name.lower()
        if not any(pattern in name_lower for pattern in WRITE_PATTERNS):
            result.append(name)
    return result
