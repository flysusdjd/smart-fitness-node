$cliWrapper = Join-Path $PSScriptRoot 'arduino-cli.ps1'
& $cliWrapper 'board' 'list'
exit $LASTEXITCODE
