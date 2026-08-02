<#
.SYNOPSIS
    统计当前目录及子目录下所有 Python 源码文件（*.py）的总大小。
.DESCRIPTION
    递归遍历当前目录，收集所有 .py 文件，计算总字节数，并以友好格式输出。
    同时列出每个文件的路径和大小（可选）。
.EXAMPLE
    .\Get-PyFileTotalSize.ps1
    仅显示汇总信息。
.EXAMPLE
    .\Get-PyFileTotalSize.ps1 -Verbose
    显示每个文件的详细信息及汇总。
#>

param(
    [switch]$Verbose   # 是否列出每个文件的详细信息
)

# 初始化
$totalSize = 0
$fileList = @()

# 递归获取所有 .py 文件（忽略权限错误）
Get-ChildItem -Recurse -Filter "*.py" -File -ErrorAction SilentlyContinue | ForEach-Object {
    $fileList += $_
    $totalSize += $_.Length
}

# 输出结果
if ($Verbose) {
    Write-Host "`n--- 文件列表 ---" -ForegroundColor Cyan
    $fileList | ForEach-Object {
        Write-Host ("{0,12:N0} 字节  {1}" -f $_.Length, $_.FullName)
    }
    Write-Host "`n"
}

Write-Host "找到 $($fileList.Count) 个 .py 文件" -ForegroundColor Yellow
Write-Host "总大小: $totalSize 字节" -ForegroundColor Green

# 转换为更直观的单位
if ($totalSize -ge 1TB) {
    Write-Host ("≈ {0:N2} TB" -f ($totalSize / 1TB)) -ForegroundColor Magenta
}
elseif ($totalSize -ge 1GB) {
    Write-Host ("≈ {0:N2} GB" -f ($totalSize / 1GB)) -ForegroundColor Magenta
}
elseif ($totalSize -ge 1MB) {
    Write-Host ("≈ {0:N2} MB" -f ($totalSize / 1MB)) -ForegroundColor Magenta
}
elseif ($totalSize -ge 1KB) {
    Write-Host ("≈ {0:N2} KB" -f ($totalSize / 1KB)) -ForegroundColor Magenta
}
pause