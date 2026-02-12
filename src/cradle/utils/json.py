import json
from datetime import datetime, date
from pathlib import Path
from decimal import Decimal
from typing import Any

class CradleJSONEncoder(json.JSONEncoder):
    """
    增强版 JSON Encoder
    支持: Path, datetime, date, set, bytes, Decimal
    """
    def default(self, obj: Any) -> Any:

        # 1.Path → 跨平台字符串
        if isinstance(obj, Path):
            return str(obj.as_posix())
        
        # 2.时间对象 → ISO 8601 标准字符串（前端/数据库通用）
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        
        # 3.set → list（JSON无set类型）
        if isinstance(obj, set):
            return list(obj)
        
        # 4.bytes → UTF-8字符串（安全降级）
        if isinstance(obj, bytes):
            return obj.decode('utf-8', errors='ignore')
        
        # 5.Decimal → float（精度警告！见下文）
        if isinstance(obj, Decimal):
            return float(obj)   # Decimal("3.14") → 3.14
            
        # 6.Pydantic模型 → 字典（v2专属）
        if hasattr(obj, 'model_dump'):
            return obj.model_dump(mode='json')  # 保留验证后结构
            
        # 未知类型 → 交还标准库（最终抛TypeError）
        return super().default(obj)

def json_dumps(obj: Any, **kwargs) -> str:
    """快捷工具：使用增强版 Encoder 序列化"""
    kwargs.setdefault('cls', CradleJSONEncoder)
    kwargs.setdefault('ensure_ascii', False) # 默认支持中文
    return json.dumps(obj, **kwargs)
