# 获取项目根目录 (Assuming script is in /scripts)
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Resolve-Path "$ScriptDir\.."
$PipCacheDir = Join-Path $ProjectRoot "data\cache\pip"

# 确保目录存在
if (-not (Test-Path $PipCacheDir)) {
    New-Item -ItemType Directory -Path $PipCacheDir | Out-Null
}

# 设置当前会话的环境变量
$env:PIP_CACHE_DIR = $PipCacheDir

Write-Host "[Environment] Pip Cache Redirected to: $PipCacheDir" -ForegroundColor Green
Write-Host "[Environment] All pip downloads in this session will be cached locally." -ForegroundColor Cyan
