# merge_files.ps1
# 功能：交互式收集文件路径，输入 generate 后合并所有文件，并添加 #FILE: 标记

$fileList = @()
Write-Host "=== 文件合并脚本 ===" -ForegroundColor Cyan
Write-Host "请输入要合并的文件路径（每行一个）。输入 'generate' 开始合并。" -ForegroundColor Cyan

while ($true) {
    $inputPath = Read-Host "路径"
    if ($inputPath -eq "generate") {
        break
    }
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

if (Test-Path $outputFile) {
    Remove-Item $outputFile -Force
}

$added = 0
$missed = 0

foreach ($f in $fileList) {
    if (Test-Path $f) {
        $content = Get-Content -Path $f -Raw -ErrorAction Stop
        Add-Content -Path $outputFile -Value "#FILE: $f" -Encoding UTF8
        Add-Content -Path $outputFile -Value $content -Encoding UTF8
        Add-Content -Path $outputFile -Value "" -Encoding UTF8
        Write-Host "已添加: $f" -ForegroundColor Green
        $added++
    } else {
        Write-Warning "文件不存在，已跳过: $f"
        $missed++
    }
}

Write-Host "`n合并完成！成功: $added，跳过: $missed" -ForegroundColor Cyan
Write-Host "输出文件: $outputFile" -ForegroundColor Cyan