# 查找并调用 arduino-cli，供其他 ESP32 工具脚本复用。
param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$CliArgs
)

$cliPath = 'C:\Users\flysusdjd\AppData\Local\Programs\Arduino IDE\resources\app\lib\backend\resources\arduino-cli.exe'

if (-not (Test-Path -LiteralPath $cliPath)) {
    Write-Error "arduino-cli not found: $cliPath"
    exit 1
}

& $cliPath @CliArgs
exit $LASTEXITCODE
