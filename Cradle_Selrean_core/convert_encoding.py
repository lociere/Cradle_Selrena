import pathlib
p = pathlib.Path(r'D:/elise/Cradle_Selrena/cradle-selrena/src/selrena/adapters/__init__.py')
# read with utf-16 (BOM) then write utf-8
text = p.read_text(encoding='utf-16')
p.write_text(text, encoding='utf-8')
print('converted')
