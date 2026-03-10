"""类型转换/校验工具。"""

def ensure_list(x):
    if isinstance(x, list):
        return x
    return [x]
