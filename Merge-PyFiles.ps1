<#
.SYNOPSIS
    递归合并目录下所有 Python 文件，并删除以 # 开头的行。
#>
param(
    [string]$SourceDir      = ".",
    [string]$OutputFile     = "merged_python.txt",
    [string]$InputEncoding  = "utf-8"
)

$ErrorActionPreference = "Stop"

# 转为绝对路径
$sourcePath = (Resolve-Path -Path $SourceDir).Path
$outputPath = [System.IO.Path]::GetFullPath($OutputFile)

# 查找所有 .py 文件，排除输出文件自身，避免重复合并
$pyFiles = Get-ChildItem -Path $sourcePath -Recurse -Filter *.py -File |
    Where-Object { $_.FullName -ne $outputPath } |
    Sort-Object FullName

# 输出使用 UTF-8 无 BOM，Python 3 默认兼容
$utf8NoBom = New-Object System.Text.UTF8Encoding -ArgumentList $false
$inputEnc  = [System.Text.Encoding]::GetEncoding($InputEncoding)

$writer = New-Object System.IO.StreamWriter -ArgumentList $outputPath, $false, $utf8NoBom

try {
    foreach ($file in $pyFiles) {
        $reader = $null
        try {
            $reader = New-Object System.IO.StreamReader -ArgumentList $file.FullName, $inputEnc
            try {
                while ($null -ne ($line = $reader.ReadLine())) {
                    # 删除行首空白后以 # 开头的行
                    if ($line -notmatch '^\s*#') {
                        $writer.WriteLine($line)
                    }
                }
            }
            finally {
                if ($null -ne $reader) {
                    $reader.Dispose()
                }
            }

            # 文件之间加一个空行，避免代码粘连
            $writer.WriteLine()
        }
        catch {
            Write-Warning "读取失败，已跳过：$($file.FullName) - $($_.Exception.Message)"
        }
    }
}
finally {
    $writer.Dispose()
}

Write-Host "完成：已合并 $($pyFiles.Count) 个 Python 文件到：$outputPath"