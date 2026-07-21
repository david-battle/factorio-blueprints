"""Full Jimbo bot application package.

The proof-of-concept remains in ``jimbo_bot.py``.  This package is the separate
full-bot implementation boundary described by FULL_BOT_DESIGN.md.
"""

from .config import FullBotConfig

__all__ = ["FullBotConfig"]
