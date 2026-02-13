"""
在服务器上验证模型是否可被 SentenceTransformer 识别并能生成 embedding。
用法（服务器上运行）：
    python scripts/verify_model_on_server.py assets/models/m3e-small

返回：退出码 0 表示加载成功，非 0 表示失败并打印错误。
"""
import sys
from pathlib import Path

if len(sys.argv) < 2:
    print('Usage: python scripts/verify_model_on_server.py <model-path>')
    sys.exit(2)

p = Path(sys.argv[1])
if not p.exists():
    print('模型目录不存在:', p)
    sys.exit(3)

try:
    from sentence_transformers import SentenceTransformer
    m = SentenceTransformer(str(p), device='cpu')
    v = m.encode('测试', convert_to_numpy=True)
    print('OK — embedding shape:', getattr(v, 'shape', 'unknown'))
    sys.exit(0)
except Exception as e:
    print('加载失败:', e)
    sys.exit(1)
