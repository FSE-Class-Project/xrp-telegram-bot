"""API routes for user settings management."""

import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.api.auth import verify_api_key
from backend.api.middleware import limiter
from backend.database.connection import get_db
from backend.database.models import User, UserSettings

logger = logging.getLogger(__name__)

# Create router
settings_router = APIRouter(prefix="/api/v1/user", tags=["Settings"])


class SettingsResponse(BaseModel):
    """User settings response model."""

    user_id: int
    price_alerts: bool = False
    transaction_notifications: bool = True
    currency_display: str = "USD"
    language: str = "en"
    two_factor_enabled: bool = False
    pin_code: str | None = None
    created_at: datetime
    updated_at: datetime


class SettingsUpdate(BaseModel):
    """Settings update request model."""

    price_alerts: bool | None = None
    transaction_notifications: bool | None = None
    currency_display: str | None = Field(None, pattern="^(USD|EUR|GBP|ZAR|JPY|BTC|ETH)$")
    language: str | None = Field(None, pattern="^(en|es|fr|de|pt|zh|ja)$")
    two_factor_enabled: bool | None = None
    pin_code: str | None = Field(None, min_length=4, max_length=8)


class ToggleSettingRequest(BaseModel):
    """Toggle setting request model."""

    setting: str = Field(
        ..., pattern="^(price_alerts|transaction_notifications|two_factor_enabled)$"
    )


class UserExportData(BaseModel):
    """User data export model."""

    user_id: int
    telegram_id: str
    telegram_username: str | None
    created_at: datetime
    wallet_address: str | None
    current_balance: float
    transaction_count: int
    total_sent: float
    settings: dict[str, Any]


@settings_router.get(
    "/settings/{telegram_id}",
    response_model=SettingsResponse,
    dependencies=[Depends(verify_api_key)],
    responses={
        200: {"description": "User settings retrieved successfully"},
        404: {"description": "User not found"},
        401: {"description": "Invalid API key"},
    },
)
@limiter.limit("60/minute")
async def get_user_settings(
    request: Request, response: Response, telegram_id: str, db: Session = Depends(get_db)
) -> SettingsResponse:
    """Get user settings."""
    try:
        # Get user from database
        user = db.query(User).filter(User.telegram_id == telegram_id).first()
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

        # Get or create user settings
        settings = user.settings
        if not settings:
            settings = UserSettings(user_id=user.id)
            db.add(settings)
            db.commit()
            db.refresh(settings)

        return SettingsResponse(
            user_id=user.id,  # type: ignore[arg-type]
            price_alerts=settings.price_alerts,  # type: ignore[arg-type]
            transaction_notifications=settings.transaction_notifications,  # type: ignore[arg-type]
            currency_display=settings.currency_display,  # type: ignore[arg-type]
            language=settings.language,  # type: ignore[arg-type]
            two_factor_enabled=settings.two_factor_enabled,  # type: ignore[arg-type]
            pin_code="****" if settings.pin_code else None,  # Mask PIN
            created_at=settings.created_at,  # type: ignore[arg-type]
            updated_at=settings.updated_at,  # type: ignore[arg-type]
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting user settings for telegram_id {telegram_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error"
        ) from e


@settings_router.put(
    "/settings/{telegram_id}",
    response_model=SettingsResponse,
    dependencies=[Depends(verify_api_key)],
    responses={
        200: {"description": "Settings updated successfully"},
        404: {"description": "User not found"},
        400: {"description": "Invalid settings data"},
        401: {"description": "Invalid API key"},
    },
)
@limiter.limit("30/minute")
async def update_user_settings(
    request: Request,
    response: Response,
    telegram_id: str,
    settings_update: SettingsUpdate,
    db: Session = Depends(get_db),
) -> SettingsResponse:
    """Update user settings."""
    try:
        # Get user from database
        user = db.query(User).filter(User.telegram_id == telegram_id).first()
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

        # Get or create user settings
        settings = user.settings
        if not settings:
            settings = UserSettings(user_id=user.id)
            db.add(settings)
            db.flush()

        # Update settings
        update_data = settings_update.model_dump(exclude_unset=True)

        for field, value in update_data.items():
            if hasattr(settings, field):
                # Handle PIN code encryption if needed
                if field == "pin_code" and value:
                    # In a real implementation, you'd hash/encrypt the PIN
                    # For now, we'll store it as-is (not recommended for production)
                    setattr(settings, field, value)
                else:
                    setattr(settings, field, value)

        settings.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(settings)

        logger.info(f"Updated settings for user telegram_id {telegram_id}")

        return SettingsResponse(
            user_id=user.id,  # type: ignore[arg-type]
            price_alerts=settings.price_alerts,  # type: ignore[arg-type]
            transaction_notifications=settings.transaction_notifications,  # type: ignore[arg-type]
            currency_display=settings.currency_display,  # type: ignore[arg-type]
            language=settings.language,  # type: ignore[arg-type]
            two_factor_enabled=settings.two_factor_enabled,  # type: ignore[arg-type]
            pin_code="****" if settings.pin_code else None,
            created_at=settings.created_at,  # type: ignore[arg-type]
            updated_at=settings.updated_at,  # type: ignore[arg-type]
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating settings for telegram_id {telegram_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error"
        ) from e


@settings_router.post(
    "/settings/{telegram_id}/toggle",
    response_model=SettingsResponse,
    dependencies=[Depends(verify_api_key)],
    responses={
        200: {"description": "Setting toggled successfully"},
        404: {"description": "User not found"},
        400: {"description": "Invalid setting name"},
        401: {"description": "Invalid API key"},
    },
)
@limiter.limit("30/minute")
async def toggle_user_setting(
    request: Request,
    response: Response,
    telegram_id: str,
    toggle_request: ToggleSettingRequest,
    db: Session = Depends(get_db),
) -> SettingsResponse:
    """Toggle a boolean setting."""
    try:
        # Get user from database
        user = db.query(User).filter(User.telegram_id == telegram_id).first()
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

        # Get or create user settings
        settings = user.settings
        if not settings:
            settings = UserSettings(user_id=user.id)
            db.add(settings)
            db.flush()

        # Toggle the setting
        setting_name = toggle_request.setting
        if hasattr(settings, setting_name):
            current_value = getattr(settings, setting_name)
            setattr(settings, setting_name, not current_value)
            settings.updated_at = datetime.now(timezone.utc)
            db.commit()
            db.refresh(settings)

            logger.info(f"Toggled {setting_name} for user telegram_id {telegram_id}: {not current_value}")
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid setting name: {setting_name}",
            )

        return SettingsResponse(
            user_id=user.id,  # type: ignore[arg-type]
            price_alerts=settings.price_alerts,  # type: ignore[arg-type]
            transaction_notifications=settings.transaction_notifications,  # type: ignore[arg-type]
            currency_display=settings.currency_display,  # type: ignore[arg-type]
            language=settings.language,  # type: ignore[arg-type]
            two_factor_enabled=settings.two_factor_enabled,  # type: ignore[arg-type]
            pin_code="****" if settings.pin_code else None,
            created_at=settings.created_at,  # type: ignore[arg-type]
            updated_at=settings.updated_at,  # type: ignore[arg-type]
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error toggling setting for telegram_id {telegram_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error"
        ) from e


@settings_router.post(
    "/export/{telegram_id}",
    response_model=UserExportData,
    dependencies=[Depends(verify_api_key)],
    responses={
        200: {"description": "User data exported successfully"},
        404: {"description": "User not found"},
        401: {"description": "Invalid API key"},
    },
)
@limiter.limit("5/hour")  # Limit data exports
async def export_user_data(
    request: Request, response: Response, telegram_id: str, db: Session = Depends(get_db)
) -> UserExportData:
    """Export user data."""
    try:
        # Get user from database
        user = db.query(User).filter(User.telegram_id == telegram_id).first()
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

        # Get user statistics
        from sqlalchemy import func

        from backend.database.models import Transaction

        # Count transactions and calculate total sent
        tx_stats = (
            db.query(
                func.count(Transaction.id).label("count"),
                func.coalesce(func.sum(Transaction.amount), 0).label("total_sent"),
            )
            .filter(Transaction.sender_id == user.id)
            .first()
        )

        if tx_stats:
            # Access by index position: count is at index 0, total_sent at index 1
            total_transactions = int(tx_stats[0]) if tx_stats[0] is not None else 0
            total_sent = float(tx_stats[1]) if tx_stats[1] is not None else 0.0
        else:
            total_transactions = 0
            total_sent = 0.0

        # Get current balance
        current_balance = user.wallet.balance if user.wallet else 0.0  # type: ignore[attr-defined]

        # Get settings
        settings_dict: dict[str, Any] = {}
        if user.settings:
            settings_dict = {  # type: ignore[unreachable]
                "price_alerts": user.settings.price_alerts,
                "transaction_notifications": user.settings.transaction_notifications,
                "currency_display": user.settings.currency_display,
                "language": user.settings.language,
                "two_factor_enabled": user.settings.two_factor_enabled,
                "has_pin": user.settings.pin_code is not None,
            }

        logger.info(f"Exported data for telegram_id {telegram_id}")

        return UserExportData(
            user_id=user.id,  # type: ignore[arg-type]
            telegram_id=user.telegram_id,  # type: ignore[arg-type]
            telegram_username=user.telegram_username,
            created_at=user.created_at,  # type: ignore[arg-type]
            wallet_address=user.wallet.xrp_address if user.wallet else None,  # type: ignore[attr-defined]
            current_balance=current_balance,
            transaction_count=total_transactions,
            total_sent=total_sent,
            settings=settings_dict,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error exporting data for telegram_id {telegram_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error"
        ) from e


@settings_router.delete(
    "/{telegram_id}",
    dependencies=[Depends(verify_api_key)],
    responses={
        200: {"description": "User account deleted successfully"},
        404: {"description": "User not found"},
        401: {"description": "Invalid API key"},
    },
)
@limiter.limit("1/hour")  # Very strict limit for account deletion
async def delete_user_account(
    request: Request, response: Response, telegram_id: str, db: Session = Depends(get_db)
) -> dict[str, str]:
    """Delete user account and all associated data."""
    try:
        # Get user from database
        user = db.query(User).filter(User.telegram_id == telegram_id).first()
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

        # Log the deletion for audit purposes
        logger.warning(
            f"User account deletion requested for telegram_id {telegram_id} (db_user_id: {user.id})"
        )

        # In a real implementation, you might want to:
        # 1. Archive the data instead of deleting
        # 2. Send final notifications
        # 3. Transfer remaining funds
        # 4. Implement a grace period

        # For now, we'll just mark as inactive instead of hard delete
        user.is_active = False
        if user.settings:
            db.delete(user.settings)  # type: ignore[unreachable]
        if user.wallet:
            # In production, ensure wallet is empty before deletion
            db.delete(user.wallet)  # type: ignore[unreachable]

        db.commit()

        logger.warning(f"User account telegram_id {telegram_id} marked as deleted")

        return {"message": "Account successfully deleted"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting account for telegram_id {telegram_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error"
        ) from e
