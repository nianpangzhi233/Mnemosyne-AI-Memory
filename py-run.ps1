<#
Run Python code from PowerShell pipeline without losing Unicode.

Usage:
@'
print('预检快照'.encode('unicode_escape').decode())
'@ | powershell -NoProfile -ExecutionPolicy Bypass -File .\py-run.ps1

PowerShell 5 pipes text to native executables using the console code page, so
`... | python -` can corrupt Chinese text before Python receives it. This script
keeps the pipeline inside PowerShell/.NET, writes a temporary UTF-8 file, then
runs Python on that file.
#>

$ErrorActionPreference = 'Stop'

[Console]::InputEncoding = [System.Text.Encoding]::UTF8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

$code = [Console]::In.ReadToEnd()
$tmp = [System.IO.Path]::ChangeExtension([System.IO.Path]::GetTempFileName(), '.py')

try {
    $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($tmp, $code, $utf8NoBom)
    $env:PYTHONUTF8 = '1'
    & python -X utf8 $tmp
    exit $LASTEXITCODE
}
finally {
    if (Test-Path -LiteralPath $tmp) {
        Remove-Item -LiteralPath $tmp -Force
    }
}
