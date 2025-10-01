"""
鳴潮付費機制模組
"""

from .ocr_manager import OCRManager, ocr_manager
from .payment_manager import PaymentManager, payment_manager
from .premium_features import PremiumFeatures, premium_features
from .user_tier_manager import UserTierManager, user_tier_manager
from .background_manager import BackgroundManager, background_manager

# 導入指令處理器以註冊指令
from . import payment_commands, premium_commands, premium_bind_commands
from .redeem_code_manager import RedeemCodeManager, redeem_code_manager
from .premium_bind_manager import PremiumBindManager, premium_bind_manager

__all__ = [
    "PaymentManager",
    "UserTierManager",
    "RedeemCodeManager",
    "PremiumFeatures",
    "BackgroundManager",
    "OCRManager",
    "PremiumBindManager",
    "payment_manager",
    "user_tier_manager",
    "redeem_code_manager",
    "premium_features",
    "background_manager",
    "ocr_manager",
    "premium_bind_manager",
]
