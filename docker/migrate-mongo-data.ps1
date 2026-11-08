# ============================================================================
# 把老 mongo 容器（docker run 起的，数据在匿名卷里）的数据，复制到 compose 用的具名卷
#
# 为什么需要它：
#   老 mongo 是用 docker run -itd --name mongo -p 27017:27017 mongo 起的，没指定卷，
#   Docker 就给了它一个哈希名匿名卷。换成 compose 管理后用的是具名卷，
#   不迁移的话 MongoDB 会是一个空库（老卷不会自动删，只是不再被使用）。
#
# 用法（在项目根目录开 PowerShell）：
#   .\docker\migrate-mongo-data.ps1            自动从老 mongo 容器找源卷并复制
#   .\docker\migrate-mongo-data.ps1 -Force     目标卷里已有数据也强制覆盖
#
# 安全：只读老卷、往新卷写，全程不删除任何东西。
# ============================================================================
[CmdletBinding()]
param(
    [string]$OldVolume = '',
    [string]$TargetVolume = 'gewu-mongo-data',
    [switch]$Force
)

$ErrorActionPreference = 'Stop'

function Fail($msg) {
    Write-Host "[失败] $msg" -ForegroundColor Red
    exit 1
}

Write-Host '=== 迁移老 MongoDB 数据到 compose 具名卷 ===' -ForegroundColor Cyan

& docker info *> $null
if ($LASTEXITCODE -ne 0) { Fail '没连上 Docker，请先启动 Docker Desktop。' }

# ------------------------------------------------------------ 1. 定位老数据卷
if (-not $OldVolume) {
    $oldContainer = (& docker ps -a --filter 'name=^mongo$' --format '{{.Names}}' 2>$null)
    if ($oldContainer) {
        # 不用 --format 模板（PowerShell 5.1 下容易被拆坏），直接取整段 JSON 再解析
        $rawInspect = (& docker inspect 'mongo' 2>$null) -join [Environment]::NewLine
        if ($rawInspect) {
            $info = $rawInspect | ConvertFrom-Json
            $mounts = @(@($info)[0].Mounts)
            $dataMount = $mounts | Where-Object { $_.Destination -eq '/data/db' } | Select-Object -First 1
            if ($dataMount) { $OldVolume = $dataMount.Name }
        }
    }
}

if (-not $OldVolume) {
    # 容器已经被删掉、但匿名卷还在的情况：用 docker inspect 当时记下来的那个卷名
    $OldVolume = '5bbe73131437b11bbdfcb6c6b37a4122c4bc4edd4b9711cfa0286907ca63c47b'
    Write-Host '[提示] 没找到名叫 mongo 的容器，按已知的匿名卷名尝试。' -ForegroundColor Yellow
}

if ($OldVolume -eq $TargetVolume) {
    Fail '源卷和目标卷是同一个，不需要迁移。'
}

& docker volume inspect $OldVolume *> $null
if ($LASTEXITCODE -ne 0) {
    Write-Host "[失败] 找不到旧数据卷 '$OldVolume'。可能已经被 docker volume prune 清掉了。" -ForegroundColor Red
    Write-Host '       源卷名可以在旧容器还在时用 docker inspect mongo 看，'
    Write-Host '       找 Mounts 里 Destination 等于 /data/db 那一项的 Name。'
    exit 1
}

Write-Host "源卷  : $OldVolume"
Write-Host "目标卷: $TargetVolume"

# ------------------------------------------------------------ 2. 准备目标卷
& docker volume create $TargetVolume *> $null
if ($LASTEXITCODE -ne 0) { Fail "创建目标卷 '$TargetVolume' 失败。" }

$existing = (& docker run --rm --entrypoint sh -v "${TargetVolume}:/to" mongo -c 'ls -A /to 2>/dev/null | head -n 1' 2>$null)
if ($existing -and -not $Force) {
    Write-Host "[提示] 目标卷 '$TargetVolume' 里已经有东西了。" -ForegroundColor Yellow
    Write-Host '       确认要用老数据覆盖的话，加 -Force 再跑一次。' -ForegroundColor Yellow
    Write-Host '       注意：如果 compose 已经启动过，请先 docker compose down 再迁移。'
    exit 2
}

# ------------------------------------------------------------ 3. 停掉老容器再复制
$running = (& docker ps --filter 'name=^mongo$' --format '{{.Names}}' 2>$null)
if ($running) {
    Write-Host '[1/2] 先停掉老 mongo 容器，避免复制到写了一半的 WiredTiger 文件 ...'
    & docker stop mongo *> $null
} else {
    Write-Host '[1/2] 老 mongo 容器没在运行，直接复制。'
}

Write-Host '[2/2] 复制数据（用本地已有的 mongo 镜像做临时容器，不额外下载）...'
$out = & docker run --rm --entrypoint sh -v "${OldVolume}:/from" -v "${TargetVolume}:/to" mongo -c 'cp -a /from/. /to/ && echo COPY_OK && du -sh /to'
if ($LASTEXITCODE -ne 0 -or -not ($out -match 'COPY_OK')) {
    Write-Host $out
    Fail '复制失败。'
}

Write-Host ''
Write-Host '=== 迁移完成 ===' -ForegroundColor Green
$sizeLine = ($out | Where-Object { $_ -match '^\s*[\d\.]+[KMG]?\s*/to' } | Select-Object -First 1)
if ($sizeLine) { Write-Host "目标卷内容大小：$sizeLine" }
Write-Host ''
Write-Host '下一步：'
Write-Host '  docker rm -f mongo attu milvus-standalone milvus-etcd milvus-minio    清掉旧容器（卷会保留）'
Write-Host '  .\docker-start.bat                                                   一键启动'
Write-Host ''
Write-Host "确认数据没问题后，老匿名卷可以用 docker volume rm $OldVolume 回收。"
