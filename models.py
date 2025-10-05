"""
Data models for the AdGuard rewrite sync application
"""

from dataclasses import dataclass
from typing import Dict


@dataclass
class RewriteRule:
    """Represents an AdGuardHome rewrite rule"""
    domain: str
    answer: str
    enabled: bool = True

    def to_dict(self) -> Dict:
        return {
            "domain": self.domain,
            "answer": self.answer,
            "enabled": self.enabled
        }
