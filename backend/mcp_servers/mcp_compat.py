"""Small compatibility layer for optional FastMCP support."""

try:
    from fastmcp import FastMCP as _FastMCP
except (ImportError, ModuleNotFoundError) as exc:
    _IMPORT_ERROR = exc

    class FastMCP:  # type: ignore[no-redef]
        """Keep local tools callable when FastMCP is unavailable or incompatible."""

        def __init__(self, name: str):
            self.name = name

        def tool(self, func=None):
            def decorator(target):
                return target

            return decorator(func) if func is not None else decorator

        def run(self, *args, **kwargs):
            raise RuntimeError(
                "FastMCP is unavailable. Install the optional 'mcp' dependencies "
                "to run this module as an MCP server."
            ) from _IMPORT_ERROR
else:
    FastMCP = _FastMCP
