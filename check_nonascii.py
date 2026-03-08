from pathlib import Path

for p in Path('cradle-selrena/src/selrena').rglob('*.py'):
    text = p.read_text(encoding='utf-8', errors='replace')
    if any(ord(ch) > 127 for ch in text):
        print('non-ascii in', p)
