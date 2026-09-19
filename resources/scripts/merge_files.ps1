# merge_files.ps1
# 功能：交互式收集文件路径，输入 generate 后合并所有文件，并添加 #FILE: 标记
# 修复：PowerShell 5.1 下 UTF-8 中文乱码问题

$ErrorActionPreference = "Stop"

# 让控制台按 UTF-8 显示，避免 Write-Host 中文本身乱码
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding          = [System.Text.Encoding]::UTF8

# 无 BOM 的 UTF-8（推荐，git 友好）
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)

# 如果你希望输出文件带 BOM（Windows 记事本更友好），改用下面这行：
# $utf8NoBom = New-Object System.Text.UTF8Encoding($true)

$fileList = @()
Write-Host "=== 文件合并脚本 ===" -ForegroundColor Cyan
Write-Host "请输入要合并的文件路径（每行一个）。输入 'generate' 开始合并。" -ForegroundColor Cyan

while ($true) {
    $inputPath = Read-Host "路径"
    if ($inputPath -eq "generate") { break }
    if ($inputPath.Trim() -ne "") {
        $fileList += $inputPath
    }
}

if ($fileList.Count -eq 0) {
    Write-Host "没有输入任何文件，程序退出。" -ForegroundColor Yellow
    exit
}

$outputFile = Read-Host "请输入输出文件名（默认 merged_output.txt）"
if ([string]::IsNullOrWhiteSpace($outputFile)) {
    $outputFile = "merged_output.txt"
}

# 解析成绝对路径，避免相对路径带来的意外
$outputFull = [System.IO.Path]::GetFullPath((Join-Path (Get-Location) $outputFile))
if (Test-Path $outputFull) {
    Remove-Item $outputFull -Force
}

$added  = 0
$missed = 0

foreach ($f in $fileList) {
    if (-not (Test-Path $f)) {
        Write-Warning "文件不存在，已跳过: $f"
        $missed++
        continue
    }

    $full = (Resolve-Path $f).Path

    try {
        # 关键：用 .NET 读取。无参 ReadAllText 会自动检测 BOM，
        # 没有 BOM 时默认按 UTF-8 解码。PS 5.1 的 Get-Content 做不到这一点。
        $content = [System.IO.File]::ReadAllText($full)
    }
    catch {
        Write-Warning "读取失败: $f ($_)"
        $missed++
        continue
    }

    # 关键：用 .NET 追加写入，编码由我们显式控制，不经过 Add-Content
    $header = "#FILE: $f`r`n"
    [System.IO.File]::AppendAllText($outputFull, $header,  $utf8NoBom)
    [System.IO.File]::AppendAllText($outputFull, $content, $utf8NoBom)
    [System.IO.File]::AppendAllText($outputFull, "`r`n",  $utf8NoBom)

    Write-Host "已添加: $f" -ForegroundColor Green
    $added++
}

Write-Host "`n合并完成！成功: $added，跳过: $missed" -ForegroundColor Cyan
Write-Host "输出文件: $outputFull" -ForegroundColor Cyan