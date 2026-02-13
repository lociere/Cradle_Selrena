"""
离线下载脚本（用于能访问外网的机器）
用途：在可联网的机器上运行，下载 `moka-ai/m3e-small` 到当前目录并打包为 tar.gz
用法：
    python scripts/download_m3e_offline.py --out ./m3e-small-package

备注：需要已安装 huggingface_hub、transformers（或在虚拟环境中运行）
"""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

try:
    from huggingface_hub import snapshot_download
except Exception as e:
    print("请先安装依赖: pip install huggingface_hub")
    raise


def sha256sum(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            h.update(chunk)
    return h.hexdigest()


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--out', '-o', default='m3e-small-package', help='输出目录/包名')
    p.add_argument('--repo', default='moka-ai/m3e-small', help='HuggingFace 仓库 id')
    args = p.parse_args()

    outdir = Path(args.out).resolve()
    if outdir.exists():
        print(f"清理现有目录: {outdir}")
        shutil.rmtree(outdir)
    outdir.mkdir(parents=True)

    print(f"开始从 Hugging Face 下载: {args.repo} -> {outdir / 'model'}")
    model_dir = snapshot_download(repo_id=args.repo, local_dir=str(outdir / 'model'), resume_download=True)
    print('下载完成，路径：', model_dir)

    # 计算常用文件的 SHA256（供校验）
    files = []
    for pth in (outdir / 'model').rglob('*'):
        if pth.is_file() and pth.suffix.lower() in {'.bin', '.json', '.pt', '.safetensors', '.model', '.txt'}:
            files.append(pth)

    checks = {str(p.relative_to(outdir / 'model')): sha256sum(p) for p in files}
    (outdir / 'checksums.json').write_text(json.dumps(checks, indent=2, ensure_ascii=False))
    print('生成校验文件 checksums.json')

    # 打包为 tar.gz
    tarname = str(outdir) + '.tar.gz'
    print('打包为：', tarname)
    subprocess.check_call(['tar', 'czf', tarname, '-C', str(outdir), 'model', 'checksums.json'])
    print('打包完成:', tarname)
    print('\n上传到目标服务器 (示例)：')
    print('  scp', tarname, 'youruser@yourserver:/path/to/project/assets/models/')
    print('\n在目标服务器上执行：')
    print('  cd /path/to/project/assets/models && tar xzf m3e-small-package.tar.gz && mv model m3e-small')
    print('\n校验（目标服务器）：')
    print("  python -c \"from sentence_transformers import SentenceTransformer; print('OK', SentenceTransformer('assets/models/m3e-small').encode('测试')[0:5])\"")


if __name__ == '__main__':
    main()
