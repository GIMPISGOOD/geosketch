# PowerShell 脚本：合并当前目录下所有 Python 文件到单个 txt 文件
# 用法：在目标目录下运行此脚本，或将其保存为 Merge-PyFiles.ps1 并执行

$outputFile = "merged_python_files.txt"   # 输出文件名

# 如果输出文件已存在，先删除（避免重复追加）
if (Test-Path $outputFile) {
    Remove-Item $outputFile
}

# 递归获取所有 .py 文件（排除输出文件本身，但 .txt 不会冲突）
Get-ChildItem -Recurse -Filter *.py | ForEach-Object {
    $file = $_

    # 构建文件头部信息
    $header = @"
============================================================
文件路径: $($file.FullName)
文件名:   $($file.Name)
修改时间: $($file.LastWriteTime)
============================================================

"@

    # 写入头部
    $header | Out-File -Append -FilePath $outputFile -Encoding UTF8

    # 写入文件内容（逐行读取以防超大文件）
    Get-Content -Path $file.FullName -Encoding UTF8 | Out-File -Append -FilePath $outputFile -Encoding UTF8

    # 文件结束后添加空行，便于区分
    "`n" | Out-File -Append -FilePath $outputFile -Encoding UTF8
}

Write-Host "所有 Python 文件已合并到：$outputFile"