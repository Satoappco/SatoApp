# MCP OAuth2 Authentication and Validation

## Overview

Fixed Google Cloud ADC authentication error and created tools for validating MCP servers without going through the full chat workflow.

## Problems Fixed

### 1. Google Cloud ADC Authentication Error

**Error**:
```
Error executing tool get_account_summaries: Your default credentials were not found.
To set up Application Default Credentials, see https://cloud.google.com/docs/authentication/external/set-up-adc
```

**Root Cause**:
- Official Google Analytics MCP uses `google.auth.default()` which requires Application Default Credentials (service account)
- We're using OAuth2 refresh tokens, not service accounts
- The two authentication methods are incompatible

**Solution**: Created OAuth2-compatible MCP wrapper at `app/mcps/google-analytics-oauth/ga4_oauth_server.py`

### 2. No Easy Way to Validate MCPs

**Problem**: Had to go through entire chat workflow to test if MCP servers work

**Solution**: Created standalone validation script at `scripts/validate_mcp.py`

## OAuth2-Compatible Google Analytics MCP

### Location
```
app/mcps/google-analytics-oauth/ga4_oauth_server.py
```

### How It Works

The OAuth2 MCP wrapper:
1. Reads OAuth2 credentials from environment variables
2. Creates Google OAuth2 Credentials object from refresh token
3. Refreshes the access token automatically
4. Passes credentials to Google Analytics API clients
5. Exposes the same tools as the official MCP

### Environment Variables

```bash
GOOGLE_ANALYTICS_REFRESH_TOKEN=<refresh-token>
GOOGLE_ANALYTICS_PROPERTY_ID=<property-id>
GOOGLE_ANALYTICS_CLIENT_ID=<client-id>
GOOGLE_ANALYTICS_CLIENT_SECRET=<client-secret>
```

### Key Features

#### OAuth2 Credential Creation
```python
def _create_oauth_credentials() -> Credentials:
    """Create OAuth2 credentials from refresh token."""
    credentials = Credentials(
        token=None,  # Will be fetched using refresh token
        refresh_token=REFRESH_TOKEN,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        scopes=[_READ_ONLY_ANALYTICS_SCOPE]
    )
    # Refresh to get access token
    credentials.refresh(Request())
    return credentials
```

#### API Client Creation
```python
def create_admin_api_client():
    """Returns Admin API client with OAuth2 credentials."""
    return admin_v1beta.AnalyticsAdminServiceAsyncClient(
        client_info=_CLIENT_INFO,
        credentials=_create_oauth_credentials()
    )
```

### Available Tools

1. **get_account_summaries()**: List all GA accounts and properties
2. **get_property_details(property_id)**: Get property details
3. **run_report(...)**: Run GA4 reports with dimensions and metrics

### Registry Configuration

Added to `app/core/agents/crew/mcp_registry.py`:

```python
MCPServer.GOOGLE_ANALYTICS_OAUTH: {
    "name": "Google Analytics (OAuth2)",
    "description": "OAuth2-compatible Google Analytics MCP server",
    "command": sys.executable,
    "args": [str(MCPS_DIR / "google-analytics-oauth" / "ga4_oauth_server.py")],
    "service": "google_analytics",
    "working_directory": str(MCPS_DIR / "google-analytics-oauth"),
    "requires_credentials": ["refresh_token", "property_id", "client_id", "client_secret"],
    "env_mapping": {
        "refresh_token": "GOOGLE_ANALYTICS_REFRESH_TOKEN",
        "property_id": "GOOGLE_ANALYTICS_PROPERTY_ID",
        "client_id": "GOOGLE_ANALYTICS_CLIENT_ID",
        "client_secret": "GOOGLE_ANALYTICS_CLIENT_SECRET",
    }
}
```

**Now set as default**:
```python
DEFAULT_SELECTION = {
    "google_analytics": MCPServer.GOOGLE_ANALYTICS_OAUTH,  # OAuth2 by default
    ...
}
```

## MCP Validation Script

### Location
```
scripts/validate_mcp.py
```

### Features

- ✅ Validate individual or all MCP servers
- ✅ Test with customer credentials from database
- ✅ Show loaded tools for each server
- ✅ Detailed error reporting
- ✅ Timeout handling
- ✅ Summary report

### Usage

#### Validate All Servers
```bash
python scripts/validate_mcp.py
```

#### Validate Specific Server
```bash
python scripts/validate_mcp.py --server google-analytics-oauth
```

#### Validate with Customer Credentials
```bash
python scripts/validate_mcp.py --customer-id 1
```

#### List Available Servers
```bash
python scripts/validate_mcp.py --list
```

#### Set Custom Timeout
```bash
python scripts/validate_mcp.py --timeout 60
```

### Example Output

```
================================================================================
  MCP Server Validation
================================================================================

📊 Fetching credentials for customer ID: 1
   ✅ Found Google Analytics credentials
      Property ID: 444278043

--------------------------------------------------------------------------------
  Testing Google Analytics MCP Servers
--------------------------------------------------------------------------------

🔍 Validating Google Analytics (OAuth2)...
   Description: OAuth2-compatible Google Analytics MCP server (uses refresh tokens)
   Service: google_analytics
   Command: /usr/bin/python3
   Args: ['/app/mcps/google-analytics-oauth/ga4_oauth_server.py']
   Working Dir: /app/mcps/google-analytics-oauth
   Environment vars: ['GOOGLE_ANALYTICS_REFRESH_TOKEN', 'GOOGLE_ANALYTICS_PROPERTY_ID', ...]
   Starting MCP server...
   ✅ Success! Loaded 3 tools
   📋 Available tools:
      1. get_account_summaries
      2. get_property_details
      3. run_report

================================================================================
  Validation Summary
================================================================================

Total Servers: 2
✅ Passed: 1
❌ Failed: 1

✅ Successful Validations:
   • google-analytics-oauth: 3 tools

❌ Failed Validations:
   • google-analytics-mcp: Your default credentials were not found
```

### How It Works

1. **Credential Fetching**: Uses the same `_fetch_google_analytics_token()` method as AnalyticsCrew
2. **Server Initialization**: Creates MCP server with `MCPServerAdapter`
3. **Tool Loading**: Validates that tools can be loaded
4. **Error Handling**: Catches and reports initialization errors
5. **Timeout Protection**: Prevents hanging on problematic servers

## Comparison: Authentication Methods

### Service Account (ADC)
- **Used By**: Official Google Analytics MCP
- **Credentials**: JSON key file
- **Setup**: Set `GOOGLE_APPLICATION_CREDENTIALS` environment variable
- **Pros**: Simple for service-to-service auth
- **Cons**: Requires service account creation, doesn't use user OAuth

### OAuth2 Refresh Token
- **Used By**: Our OAuth2 MCP wrapper
- **Credentials**: Refresh token + client ID/secret
- **Setup**: Store in database per customer
- **Pros**: Uses actual user permissions, works with our OAuth flow
- **Cons**: Tokens can expire/be revoked

## Files Changed

### New Files

1. **`app/mcps/google-analytics-oauth/ga4_oauth_server.py`**
   - OAuth2-compatible Google Analytics MCP server
   - Reads refresh tokens from environment
   - Creates OAuth2 credentials automatically
   - Exposes same tools as official MCP

2. **`scripts/validate_mcp.py`**
   - Standalone MCP validation script
   - Tests server initialization and tool loading
   - Works with database credentials
   - Detailed error reporting

### Modified Files

1. **`app/core/agents/crew/mcp_registry.py`**
   - Added `MCPServer.GOOGLE_ANALYTICS_OAUTH` enum
   - Added OAuth2 MCP configuration
   - Changed default to OAuth2 version
   - Updated official MCP docs (requires service account)

## Testing

### Test OAuth2 MCP Directly

```bash
# Set environment variables
export GOOGLE_ANALYTICS_REFRESH_TOKEN="<token>"
export GOOGLE_ANALYTICS_PROPERTY_ID="444278043"
export GOOGLE_ANALYTICS_CLIENT_ID="<client-id>"
export GOOGLE_ANALYTICS_CLIENT_SECRET="<secret>"

# Run the MCP server
python app/mcps/google-analytics-oauth/ga4_oauth_server.py
```

### Test with Validation Script

```bash
# Test with customer credentials
python scripts/validate_mcp.py --customer-id 1

# Test specific OAuth server
python scripts/validate_mcp.py --server google-analytics-oauth --customer-id 1
```

### Test in Full Workflow

Send a chat message that triggers analytics:
```
"Show me the top 5 cities by active users for the last 7 days"
```

Check logs for:
- ✅ MCP server initialization without ADC errors
- ✅ Tools loaded successfully
- ✅ Reports executed correctly

## Troubleshooting

### "Your default credentials were not found"

**Cause**: Using official MCP that requires service account

**Solution**: Make sure `GOOGLE_ANALYTICS_OAUTH` is set as default in registry:
```python
DEFAULT_SELECTION = {
    "google_analytics": MCPServer.GOOGLE_ANALYTICS_OAUTH,
}
```

### "GOOGLE_ANALYTICS_REFRESH_TOKEN not set"

**Cause**: Missing OAuth2 credentials in environment

**Solution**: Check that credentials are fetched from database and passed to MCP:
1. Verify `_fetch_google_analytics_token()` returns credentials
2. Check MCP registry env_mapping is correct
3. Validate credentials in database for customer

### "Invalid grant" OAuth error

**Cause**: Refresh token has been revoked or expired

**Solution**:
1. Re-authenticate the customer connection
2. Update refresh token in database
3. Check OAuth consent screen configuration

### Validation Script Times Out

**Cause**: MCP server not responding

**Solution**:
1. Check MCP server can start standalone
2. Increase timeout: `--timeout 60`
3. Check working directory and PYTHONPATH are correct

## Migration from Service Account to OAuth2

If you were using service accounts before:

1. **Remove service account files**:
   ```bash
   unset GOOGLE_APPLICATION_CREDENTIALS
   rm service-account.json
   ```

2. **Use OAuth2 MCP** (already default):
   ```python
   DEFAULT_SELECTION = {
       "google_analytics": MCPServer.GOOGLE_ANALYTICS_OAUTH
   }
   ```

3. **Ensure OAuth credentials** are in database:
   - Customer connections table has refresh_token
   - Digital assets table has property_id
   - Environment has client_id and client_secret

4. **Test** with validation script:
   ```bash
   python scripts/validate_mcp.py --customer-id <id>
   ```

## Related Documentation

- [Local MCP Servers](./local_mcp_servers.md) - Local MCP configuration
- [LangFuse and MCP Fixes](./langfuse_and_mcp_fixes.md) - Previous MCP fixes
- [MCP Transport Fix](./mcp_transport_fix.md) - stdio transport configuration
- Google OAuth2: https://developers.google.com/identity/protocols/oauth2
- Google Analytics API: https://developers.google.com/analytics/devguides/reporting/data/v1

## Summary

✅ **Fixed ADC authentication error** by creating OAuth2-compatible MCP wrapper
✅ **Created validation script** for testing MCPs without chat workflow
✅ **Set OAuth2 MCP as default** for Google Analytics
✅ **Maintained compatibility** with service account MCPs (optional)
✅ **Easy testing** with customer credentials from database

### Before
```
❌ Error: Your default credentials were not found
❌ Required service account JSON file
❌ No way to validate MCP without full chat
```

### After
```
✅ Uses OAuth2 refresh tokens from database
✅ Automatic credential refresh
✅ Standalone validation script
✅ Works with existing customer connections
```
