"""
Settings API routes for managing application configuration
"""

from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlmodel import select, and_

from app.core.auth import get_current_user
from app.models.users import Campaigner, UserRole
from app.models.settings import AppSettings, SETTING_CATEGORIES, DEFAULT_SETTINGS
from app.config.database import get_session
from app.config.settings import get_settings, clear_settings_cache
import os

router = APIRouter(prefix="/settings", tags=["settings"])


class UpdateSettingRequest(BaseModel):
    """Request model for updating a setting"""
    value: str


class CreateSettingRequest(BaseModel):
    """Request model for creating a new setting"""
    key: str
    value: str
    value_type: str = "string"
    category: str = "general"
    description: Optional[str] = None
    is_secret: bool = False
    is_editable: bool = True
    requires_restart: bool = False


@router.get("/public/{key}")
async def get_public_setting(key: str):
    """
    Get a single non-secret setting value by key (public endpoint, no auth required).
    This is used by the frontend to get runtime configuration.
    Only returns non-secret settings.
    """
    try:
        with get_session() as session:
            setting = session.exec(
                select(AppSettings).where(AppSettings.key == key)
            ).first()

            if not setting:
                # Try to get from environment as fallback
                env_value = os.getenv(key.upper())
                if env_value:
                    return {
                        "success": True,
                        "key": key,
                        "value": env_value,
                        "source": "environment"
                    }

                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Setting '{key}' not found"
                )

            # Don't return secret values via public endpoint
            if setting.is_secret:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Cannot access secret settings via public endpoint"
                )

            return {
                "success": True,
                "key": setting.key,
                "value": setting.value,
                "source": "database"
            }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get setting: {str(e)}"
        )


@router.get("/categories")
async def get_setting_categories(
    current_user: Campaigner = Depends(get_current_user)
):
    """
    Get all setting categories.
    Only owners and admins can access settings.
    """
    if current_user.role not in [UserRole.OWNER, UserRole.ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only owners and admins can access settings"
        )

    return {
        "success": True,
        "categories": [
            {
                "name": cat.name,
                "display_name": cat.display_name,
                "description": cat.description,
                "icon": cat.icon
            }
            for cat in SETTING_CATEGORIES.values()
        ]
    }


@router.get("")
async def get_all_settings(
    category: Optional[str] = None,
    current_user: Campaigner = Depends(get_current_user)
):
    """
    Get all settings, optionally filtered by category.
    Only owners and admins can access settings.
    Secrets are masked for non-owners.
    """
    if current_user.role not in [UserRole.OWNER, UserRole.ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only owners and admins can access settings"
        )

    try:
        with get_session() as session:
            # Build query
            query = select(AppSettings)
            if category:
                query = query.where(AppSettings.category == category)

            settings = session.exec(query.order_by(AppSettings.category, AppSettings.key)).all()

            # Mask secrets for non-owners
            is_owner = current_user.role == UserRole.OWNER
            settings_data = []

            for setting in settings:
                setting_dict = {
                    "id": setting.id,
                    "key": setting.key,
                    "value": setting.value if (not setting.is_secret or is_owner) else "********",
                    "value_type": setting.value_type,
                    "category": setting.category,
                    "description": setting.description,
                    "is_secret": setting.is_secret,
                    "is_editable": setting.is_editable,
                    "requires_restart": setting.requires_restart,
                    "updated_at": setting.updated_at.isoformat() if setting.updated_at else None,
                }
                settings_data.append(setting_dict)

            return {
                "success": True,
                "settings": settings_data,
                "total": len(settings_data)
            }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get settings: {str(e)}"
        )


@router.get("/{setting_id}")
async def get_setting(
    setting_id: int,
    current_user: Campaigner = Depends(get_current_user)
):
    """
    Get a specific setting by ID.
    Only owners and admins can access settings.
    """
    if current_user.role not in [UserRole.OWNER, UserRole.ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only owners and admins can access settings"
        )

    try:
        with get_session() as session:
            setting = session.get(AppSettings, setting_id)

            if not setting:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Setting not found"
                )

            # Mask secret for non-owners
            is_owner = current_user.role == UserRole.OWNER
            value = setting.value if (not setting.is_secret or is_owner) else "********"

            return {
                "success": True,
                "setting": {
                    "id": setting.id,
                    "key": setting.key,
                    "value": value,
                    "value_type": setting.value_type,
                    "category": setting.category,
                    "description": setting.description,
                    "is_secret": setting.is_secret,
                    "is_editable": setting.is_editable,
                    "requires_restart": setting.requires_restart,
                    "updated_at": setting.updated_at.isoformat() if setting.updated_at else None,
                }
            }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get setting: {str(e)}"
        )


@router.put("/{setting_id}")
async def update_setting(
    setting_id: int,
    request: UpdateSettingRequest,
    current_user: Campaigner = Depends(get_current_user)
):
    """
    Update a setting value.
    Only owners and admins can update settings.
    """
    if current_user.role not in [UserRole.OWNER, UserRole.ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only owners and admins can update settings"
        )

    try:
        with get_session() as session:
            setting = session.get(AppSettings, setting_id)

            if not setting:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Setting not found"
                )

            if not setting.is_editable:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="This setting is not editable"
                )

            # Update the setting
            old_value = setting.value
            setting.value = request.value
            setting.updated_by_id = current_user.id

            session.add(setting)
            session.commit()
            session.refresh(setting)

            # Clear settings cache to force reload
            clear_settings_cache()

            # Log the change
            print(f"⚙️ Setting '{setting.key}' updated by {current_user.email}")
            print(f"   Old value: {old_value if not setting.is_secret else '********'}")
            print(f"   New value: {setting.value if not setting.is_secret else '********'}")

            if setting.requires_restart:
                print(f"   ⚠️ This setting requires service restart to take effect")

            return {
                "success": True,
                "message": "Setting updated successfully",
                "requires_restart": setting.requires_restart,
                "setting": {
                    "id": setting.id,
                    "key": setting.key,
                    "value": setting.value,
                    "updated_at": setting.updated_at.isoformat() if setting.updated_at else None,
                }
            }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update setting: {str(e)}"
        )


@router.post("")
async def create_setting(
    request: CreateSettingRequest,
    current_user: Campaigner = Depends(get_current_user)
):
    """
    Create a new setting.
    Only owners can create settings.
    """
    if current_user.role != UserRole.OWNER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only owners can create settings"
        )

    try:
        with get_session() as session:
            # Check if setting already exists
            existing = session.exec(
                select(AppSettings).where(AppSettings.key == request.key)
            ).first()

            if existing:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Setting with this key already exists"
                )

            # Create new setting
            new_setting = AppSettings(
                key=request.key,
                value=request.value,
                value_type=request.value_type,
                category=request.category,
                description=request.description,
                is_secret=request.is_secret,
                is_editable=request.is_editable,
                requires_restart=request.requires_restart,
                updated_by_id=current_user.id
            )

            session.add(new_setting)
            session.commit()
            session.refresh(new_setting)

            # Clear settings cache
            clear_settings_cache()

            print(f"⚙️ New setting '{new_setting.key}' created by {current_user.email}")

            return {
                "success": True,
                "message": "Setting created successfully",
                "setting": {
                    "id": new_setting.id,
                    "key": new_setting.key,
                    "value": new_setting.value,
                    "category": new_setting.category
                }
            }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create setting: {str(e)}"
        )


@router.delete("/{setting_id}")
async def delete_setting(
    setting_id: int,
    current_user: Campaigner = Depends(get_current_user)
):
    """
    Delete a setting.
    Only owners can delete settings.
    """
    if current_user.role != UserRole.OWNER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only owners can delete settings"
        )

    try:
        with get_session() as session:
            setting = session.get(AppSettings, setting_id)

            if not setting:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Setting not found"
                )

            setting_key = setting.key
            session.delete(setting)
            session.commit()

            # Clear settings cache
            clear_settings_cache()

            print(f"⚙️ Setting '{setting_key}' deleted by {current_user.email}")

            return {
                "success": True,
                "message": "Setting deleted successfully"
            }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete setting: {str(e)}"
        )


@router.post("/initialize")
async def initialize_settings(
    current_user: Campaigner = Depends(get_current_user)
):
    """
    Initialize default settings if they don't exist.
    Only owners can initialize settings.
    """
    if current_user.role != UserRole.OWNER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only owners can initialize settings"
        )

    try:
        with get_session() as session:
            created_count = 0

            for default_setting in DEFAULT_SETTINGS:
                # Check if setting exists
                existing = session.exec(
                    select(AppSettings).where(AppSettings.key == default_setting["key"])
                ).first()

                if not existing:
                    # Create setting
                    new_setting = AppSettings(
                        **default_setting,
                        updated_by_id=current_user.id
                    )
                    session.add(new_setting)
                    created_count += 1

            session.commit()

            # Clear settings cache
            clear_settings_cache()

            print(f"⚙️ Initialized {created_count} default settings")

            return {
                "success": True,
                "message": f"Initialized {created_count} default settings",
                "created_count": created_count
            }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to initialize settings: {str(e)}"
        )


@router.post("/reload")
async def reload_settings(
    current_user: Campaigner = Depends(get_current_user)
):
    """
    Reload settings cache.
    Only owners and admins can reload settings.
    """
    if current_user.role not in [UserRole.OWNER, UserRole.ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only owners and admins can reload settings"
        )

    try:
        # Clear the cache
        clear_settings_cache()

        # Reload settings
        new_settings = get_settings()

        print(f"⚙️ Settings cache reloaded by {current_user.email}")

        return {
            "success": True,
            "message": "Settings reloaded successfully",
            "note": "Some settings may require service restart to take full effect"
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to reload settings: {str(e)}"
        )


@router.post("/restart")
async def restart_service(
    current_user: Campaigner = Depends(get_current_user)
):
    """
    Restart the backend service.
    Only owners can restart the service.

    NOTE: This triggers a graceful restart of the backend.
    Frontend should restart itself separately if needed.
    """
    if current_user.role != UserRole.OWNER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only owners can restart the service"
        )

    try:
        import signal

        print(f"🔄 Backend restart requested by {current_user.email}")
        print(f"⚠️ Initiating graceful restart...")

        # Return response before restarting
        response = {
            "success": True,
            "message": "Backend restart initiated. Service will be back up in ~15 seconds."
        }

        # Schedule restart after response is sent
        import asyncio
        async def delayed_restart():
            await asyncio.sleep(1)  # Wait for response to be sent
            print("🔄 Executing backend restart now...")
            # Send SIGTERM to trigger graceful shutdown
            # Docker will restart the process
            os.kill(os.getpid(), signal.SIGTERM)

        # Start the delayed restart task
        asyncio.create_task(delayed_restart())

        return response

    except Exception as e:
        print(f"❌ Error during restart: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to restart service: {str(e)}"
        )
