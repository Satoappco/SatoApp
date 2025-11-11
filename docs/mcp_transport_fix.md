# MCP Transport Configuration Fix

## Problem

The application was throwing a `ValueError` when initializing MCP servers:

```
ValueError: Invalid transport, expected ['sse', 'streamable-http', 'ws'] found `stdio`
```

**Location**: `app/core/agents/crew/mcp_registry.py` line 194

## Root Cause

The `mcpadapt` library (used by CrewAI's `MCPServerAdapter`) supports two types of server parameters:

1. **`StdioServerParameters` object**: For command-line MCP servers using stdio transport
2. **Dictionary with transport field**: For HTTP-based servers using `sse`, `streamable-http`, or `ws`

Our code was incorrectly using a **dict with `"transport": "stdio"`**, which is not supported. The valid transports for dict-based parameters are:
- `sse` - Server-Sent Events
- `streamable-http` - Streamable HTTP
- `ws` - WebSocket

## Solution

Changed `mcp_registry.py` to return `StdioServerParameters` objects instead of dictionaries:

### Before (Incorrect)
```python
server_params = {
    "command": config["command"],
    "args": config["args"],
    "env": env_vars,
    "transport": "stdio"  # ❌ Invalid for dict-based params
}
```

### After (Correct)
```python
from mcp import StdioServerParameters

server_params = StdioServerParameters(
    command=config["command"],
    args=config["args"],
    env=env_vars
)
```

## Technical Details

### mcpadapt Library Behavior

From `mcpadapt/core.py` lines 105-116:

```python
if isinstance(serverparams, StdioServerParameters):
    client = stdio_client(serverparams)
elif isinstance(serverparams, dict):
    client_params = copy.deepcopy(serverparams)
    transport = client_params.pop("transport", "sse")
    if transport in TRANSPORTS:  # TRANSPORTS = {"sse", "streamable-http", "ws"}
        client = TRANSPORTS[transport](**client_params)
    else:
        raise ValueError(
            f"Invalid transport, expected {list(TRANSPORTS.keys())} found `{transport}`"
        )
```

**Key Points**:
- `StdioServerParameters`: Automatically uses stdio_client (no transport field needed)
- Dict: Must specify transport as one of: `sse`, `streamable-http`, or `ws`
- stdio is **only** available via `StdioServerParameters` object

### Our MCP Servers

All MCP servers in our registry use command-line execution via `uvx`:

```python
REGISTRY: Dict[MCPServer, Dict[str, Any]] = {
    MCPServer.GOOGLE_ANALYTICS_OFFICIAL: {
        "command": "uvx",
        "args": ["mcp-google-analytics"],
        ...
    },
    MCPServer.GOOGLE_ADS_OFFICIAL: {
        "command": "uvx",
        "args": ["run-mcp-server"],
        ...
    },
    MCPServer.META_ADS: {
        "command": "uvx",
        "args": ["meta-ads-mcp"],
        ...
    },
}
```

Since they all use command-line execution with stdio communication, `StdioServerParameters` is the correct format.

## Files Changed

### `app/core/agents/crew/mcp_registry.py`

1. **Added import**:
   ```python
   from mcp import StdioServerParameters
   ```

2. **Updated `build_server_params` return type**:
   ```python
   def build_server_params(
       server: MCPServer,
       credentials: Dict[str, str]
   ) -> StdioServerParameters:  # Changed from Dict[str, Any]
   ```

3. **Updated `build_all_server_params` return type**:
   ```python
   def build_all_server_params(...) -> List[StdioServerParameters]:  # Changed from List[Dict[str, Any]]
   ```

4. **Updated `configure_all_mcps` return type**:
   ```python
   def configure_all_mcps(...) -> List[StdioServerParameters]:  # Changed from List[Dict[str, Any]]
   ```

## Usage

No changes required in calling code. The `MCPServerAdapter` in `crew.py` already works correctly:

```python
# app/core/agents/crew/crew.py line 337
context_manager = MCPServerAdapter(self.mcp_param_list)
```

`MCPServerAdapter` accepts:
- A single `StdioServerParameters` object
- A single dict
- A list of `StdioServerParameters` objects
- A list of dicts
- A mixed list

## Testing

To verify the fix works:

1. Start the application
2. Send a chat message that triggers analytics crew
3. Check logs for successful MCP server initialization:
   ```
   ✅ Configured google-analytics-mcp
   ✅ Configured 1 MCP server(s)
   🔧 Initializing 1 MCP server(s)
   ✅ Total tools loaded: X
   ```

No `ValueError: Invalid transport` should appear.

## References

- mcpadapt library: `/home/yashar/projects/sato-be/tmp/AttemptedBE/venv/lib/python3.12/site-packages/mcpadapt/core.py`
- MCP Python SDK: https://github.com/modelcontextprotocol/python-sdk
- CrewAI MCPServerAdapter: https://docs.crewai.com/tools/mcp-tools

## Summary

✅ **Fixed**: Changed MCP server parameter format from dict with `"transport": "stdio"` to `StdioServerParameters` object
✅ **Impact**: MCP servers can now initialize properly without transport errors
✅ **Breaking Changes**: None - internal implementation detail only
