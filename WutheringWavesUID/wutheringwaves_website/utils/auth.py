"""
認證工具函數
處理 JWT token 和驗證碼驗證
"""

import logging
from typing import Any, Dict, Optional
from datetime import datetime, timedelta

import jwt

from ..config import config

logger = logging.getLogger(__name__)


def create_jwt_token(discord_id: str, uid: str) -> str:
    """創建 JWT token"""
    try:
        payload = {
            "discord_id": discord_id,
            "uid": uid,
            "exp": datetime.utcnow() + timedelta(minutes=config.jwt_expire_minutes),
            "iat": datetime.utcnow(),
        }

        token = jwt.encode(
            payload, config.jwt_secret_key, algorithm=config.jwt_algorithm
        )
        logger.info(f"JWT token created for user {discord_id}")
        return token

    except Exception as e:
        logger.error(f"Failed to create JWT token: {e}")
        raise


def verify_jwt_token(token: str) -> Dict[str, Any]:
    """驗證 JWT token"""
    try:
        payload = jwt.decode(
            token, config.jwt_secret_key, algorithms=[config.jwt_algorithm]
        )

        # 檢查過期時間
        if datetime.utcnow() > datetime.fromtimestamp(payload["exp"]):
            raise jwt.ExpiredSignatureError("Token has expired")

        logger.info(f"JWT token verified for user {payload.get('discord_id')}")
        return payload

    except jwt.ExpiredSignatureError:
        logger.warning("JWT token has expired")
        raise
    except jwt.InvalidTokenError as e:
        logger.warning(f"Invalid JWT token: {e}")
        raise
    except Exception as e:
        logger.error(f"Failed to verify JWT token: {e}")
        raise


async def verify_auth_code(discord_id: str, auth_code: str) -> bool:
    """驗證驗證碼"""
    try:
        from .database import get_auth_code, mark_auth_code_used

        # 獲取驗證碼記錄
        auth_record = await get_auth_code(discord_id)
        if not auth_record:
            logger.warning(f"No auth code found for user {discord_id}")
            return False

        # 檢查驗證碼是否匹配
        if auth_record.auth_code != auth_code:
            logger.warning(f"Invalid auth code for user {discord_id}")
            return False

        # 檢查是否已使用
        if auth_record.is_used:
            logger.warning(f"Auth code already used for user {discord_id}")
            return False

        # 檢查是否過期
        if datetime.now() > auth_record.expires_at:
            logger.warning(f"Auth code expired for user {discord_id}")
            return False

        # 檢查嘗試次數
        if auth_record.attempt_count >= config.max_auth_attempts:
            logger.warning(f"Too many attempts for user {discord_id}")
            return False

        logger.info(f"Auth code verified for user {discord_id}")
        return True

    except Exception as e:
        logger.error(f"Failed to verify auth code: {e}")
        return False
