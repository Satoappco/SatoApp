# Auto-Delete Orphaned Digital Assets

## Overview

This feature automatically deletes digital assets when they no longer have any associated connections. This helps keep the database clean by removing orphaned digital assets that are no longer in use.

## Behavior

### When a Connection is Deleted

When a connection is deleted (either individually or as part of bulk operations), the system automatically:

1. Deletes the connection from the database
2. Checks if the associated digital asset has any remaining connections
3. If no connections remain, deletes the digital asset automatically

### Affected Operations

The auto-delete functionality is triggered in the following scenarios:

#### 1. Individual Connection Deletion

When deleting individual connections through the API:

- **Google Ads**: `DELETE /google-ads/connections/{connection_id}`
- **Google Analytics**: `DELETE /google-analytics/connections/{connection_id}`
- **Facebook**: `DELETE /facebook/connections/{connection_id}`

**Example Response:**
```json
{
  "message": "Google Ads connection deleted successfully and associated digital asset was removed (no other connections)"
}
```

If the digital asset still has other connections, the response will be:
```json
{
  "message": "Google Ads connection deleted successfully"
}
```

#### 2. Bulk Connection Deletion

When deleting customers or campaigners, all their associated connections are deleted and orphaned digital assets are automatically cleaned up:

- **Delete Customer**: All connections for the customer are deleted, and orphaned assets are removed
- **Delete Campaigner/Worker**: All connections created by the campaigner are deleted, and orphaned assets are removed

## Implementation Details

### Service Function

The core functionality is implemented in `app/services/digital_asset_service.py`:

```python
def delete_orphaned_digital_asset(session: Session, digital_asset_id: int) -> bool:
    """
    Delete a digital asset if it has no connections.

    Args:
        session: Database session
        digital_asset_id: ID of the digital asset to check

    Returns:
        bool: True if the asset was deleted, False otherwise
    """
```

### Database Models

The relationship between `Connection` and `DigitalAsset`:

```python
class Connection(BaseModel, table=True):
    # ...
    digital_asset_id: int = Field(foreign_key="digital_assets.id")
    # ...

class DigitalAsset(BaseModel, table=True):
    # ...
    id: int  # Referenced by Connection.digital_asset_id
    # ...
```

## Testing

Comprehensive tests are provided in `tests/unit/test_orphaned_digital_asset_cleanup.py`:

### Test Coverage

1. **Basic Orphan Cleanup**
   - Test deleting a digital asset with no connections
   - Test that assets with connections are NOT deleted
   - Test handling of non-existent assets

2. **Connection Deletion Integration**
   - Test Google Ads connection deletion triggers cleanup
   - Test Google Analytics connection deletion triggers cleanup
   - Test Facebook connection deletion triggers cleanup

3. **Bulk Operations**
   - Test customer deletion cleans up orphaned assets
   - Test campaigner deletion cleans up orphaned assets
   - Test handling of multiple connections to the same asset

### Running Tests

```bash
# Run all orphaned asset cleanup tests
pytest tests/unit/test_orphaned_digital_asset_cleanup.py -v

# Run a specific test
pytest tests/unit/test_orphaned_digital_asset_cleanup.py::TestOrphanedDigitalAssetCleanup::test_delete_orphaned_digital_asset_no_connections -v
```

## Migration Notes

### Before This Feature

- Connections could be marked as "revoked" but remained in the database
- Digital assets could remain in the database even after all connections were removed
- Manual cleanup was required to remove orphaned assets

### After This Feature

- Connections are completely deleted when removed/revoked
- Digital assets are automatically deleted when their last connection is removed
- No manual cleanup required for orphaned assets

## Files Modified

1. **Service Layer**
   - `app/services/digital_asset_service.py` - Added `delete_orphaned_digital_asset()` function

2. **API Routes**
   - `app/api/v1/routes/google_ads.py` - Updated connection deletion endpoint
   - `app/api/v1/routes/google_analytics.py` - Updated connection deletion endpoint
   - `app/api/v1/routes/facebook.py` - Updated connection deletion endpoint
   - `app/api/v1/routes/customers.py` - Updated customer deletion to clean up orphaned assets
   - `app/api/v1/routes/campaigners.py` - Updated campaigner deletion to clean up orphaned assets

3. **Services**
   - `app/services/google_analytics_service.py` - Updated `revoke_ga_connection()` to delete instead of revoke

4. **Tests**
   - `tests/unit/test_orphaned_digital_asset_cleanup.py` - Comprehensive test suite

5. **Documentation**
   - `docs/AUTO_DELETE_ORPHANED_DIGITAL_ASSETS.md` - This file

## Example Scenarios

### Scenario 1: Single Connection to Asset

1. User has a Google Ads connection to digital asset A
2. User deletes the connection
3. Digital asset A has no remaining connections
4. **Result**: Digital asset A is automatically deleted

### Scenario 2: Multiple Connections to Same Asset

1. User has 2 Google Ads connections to the same digital asset A
2. User deletes one connection
3. Digital asset A still has 1 remaining connection
4. **Result**: Digital asset A is kept (not deleted)
5. User deletes the second connection
6. Digital asset A has no remaining connections
7. **Result**: Digital asset A is automatically deleted

### Scenario 3: Customer Deletion

1. Customer has 3 digital assets (A, B, C)
2. Asset A has 2 connections (both owned by the customer)
3. Asset B has 1 connection (owned by the customer)
4. Asset C has 2 connections (1 owned by the customer, 1 owned by another customer)
5. Customer is deleted
6. All 3 connections owned by the customer are deleted
7. **Result**:
   - Asset A is deleted (no remaining connections)
   - Asset B is deleted (no remaining connections)
   - Asset C is kept (still has 1 connection from another customer)

## Best Practices

1. **Before Deleting Connections**: Users should be aware that deleting the last connection to a digital asset will also delete the asset
2. **Backup Data**: Consider exporting important data before removing connections
3. **Testing**: Always test connection deletion in a staging environment first
4. **Monitoring**: Monitor logs for orphaned asset deletions to track cleanup activity

## Future Enhancements

Potential improvements for this feature:

1. **Soft Delete**: Add a soft delete option to mark assets as deleted without removing them
2. **Grace Period**: Implement a grace period before deleting orphaned assets
3. **Audit Log**: Add detailed audit logging for asset deletions
4. **Restore Functionality**: Add ability to restore recently deleted assets
5. **Notifications**: Notify users when their digital assets are auto-deleted

## Related Documentation

- [Database Management](./database_management.md) (if exists)
- [Connection Management](./connection_management.md) (if exists)
- [Google Ads Setup](./GOOGLE_ADS_SETUP.md)
