"""
Napcat 数据模型 (Napcat Schemas)。

提供 Napcat Vessel 专用的结构化数据模型。
"""

from .napcat import NapcatArtifact, NapcatMessageRecord

__all__ = [
    "NapcatArtifact",
    "NapcatMessageRecord",
]
