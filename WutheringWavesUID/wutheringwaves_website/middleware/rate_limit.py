"""
速率限制中間件
防止 API 濫用
"""

import time
import logging
from collections import defaultdict

from starlette.responses import Response
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware

from ..config import config

logger = logging.getLogger(__name__)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """速率限制中間件"""

    def __init__(self, app, calls_per_minute: int = None):
        super().__init__(app)
        self.calls_per_minute = calls_per_minute or config.rate_limit_per_minute
        self.requests = defaultdict(list)

    async def dispatch(self, request: Request, call_next):
        """處理請求"""
        try:
            # 獲取客戶端 IP
            client_ip = request.client.host

            # 檢查速率限制
            if self._is_rate_limited(client_ip):
                logger.warning(f"Rate limit exceeded for IP: {client_ip}")
                raise HTTPException(status_code=429, detail="請求過於頻繁，請稍後再試")

            # 記錄請求
            self._record_request(client_ip)

            # 處理請求
            response = await call_next(request)
            return response

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Rate limit middleware error: {e}")
            return await call_next(request)

    def _is_rate_limited(self, client_ip: str) -> bool:
        """檢查是否超過速率限制"""
        now = time.time()
        minute_ago = now - 60

        # 清理過期的請求記錄
        self.requests[client_ip] = [
            req_time for req_time in self.requests[client_ip] if req_time > minute_ago
        ]

        # 檢查請求次數
        return len(self.requests[client_ip]) >= self.calls_per_minute

    def _record_request(self, client_ip: str):
        """記錄請求"""
        self.requests[client_ip].append(time.time())
