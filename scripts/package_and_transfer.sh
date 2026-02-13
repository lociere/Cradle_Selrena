#!/usr/bin/env bash
# 在下载机器上打包并通过 scp 上传到远程服务器（示例脚本）
# 用法: ./scripts/package_and_transfer.sh m3e-small-package.tar.gz youruser@47.99.49.252:/home/youruser/upload/

set -euo pipefail
PACKAGE=${1:-m3e-small-package.tar.gz}
DEST=${2:-}
if [ -z "$DEST" ]; then
  echo "Usage: $0 <package.tar.gz> user@host:/remote/path/" >&2
  exit 2
fi

if [ ! -f "$PACKAGE" ]; then
  echo "Package not found: $PACKAGE" >&2
  exit 3
fi

echo "Uploading $PACKAGE -> $DEST"
scp "$PACKAGE" "$DEST"
if [ $? -ne 0 ]; then
  echo "scp failed" >&2
  exit 4
fi

echo "上传完成。登录服务器并在项目目录执行：\n  tar xzf /remote/path/$(basename $PACKAGE) \n  mv model m3e-small && rm $(basename $PACKAGE)"
