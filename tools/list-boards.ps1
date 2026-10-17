# 列出当前 arduino-cli 可识别的开发板。
$cliWrapper = Join-Path $PSScriptRoot 'arduino-cli.ps1'
& $cliWrapper 'board' 'list'
exit $LASTEXITCODE
