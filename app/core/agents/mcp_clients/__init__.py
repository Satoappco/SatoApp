"""MCP (Model Context Protocol) client integrations."""

# Avoid circular imports by using lazy imports
__all__ = ["FacebookMCPClient", "GoogleMCPClient"]


def __getattr__(name):
    """Lazy import to avoid circular dependency issues."""
    if name == "FacebookMCPClient":
        from .facebook_client import FacebookMCPClient
        return FacebookMCPClient
    elif name == "GoogleMCPClient":
        from .google_client import GoogleMCPClient
        return GoogleMCPClient
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
