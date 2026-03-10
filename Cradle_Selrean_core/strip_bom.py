from pathlib import Path

root = Path('cradle-selrena/src/selrena')
for py in root.rglob('*.py'):
    text = py.read_text(encoding='utf-8-sig')
    if text.startswith('\ufeff'):
        text = text.lstrip('\ufeff')
    py.write_text(text, encoding='utf-8')
print('boms removed')
