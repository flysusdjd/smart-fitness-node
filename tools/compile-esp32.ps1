param(
    [string]$SketchPath = (Join-Path (Split-Path -Parent $PSScriptRoot) 'ESPS3'),
    [string]$Fqbn = 'esp32:esp32:esp32s3',
    [switch]$Clean
)

$projectRoot = Split-Path -Parent $PSScriptRoot
$buildPath = Join-Path $projectRoot '.arduino-build\esp32s3'
$tempPath = Join-Path $projectRoot '.arduino-temp'
$cliWrapper = Join-Path $PSScriptRoot 'arduino-cli.ps1'

if ($Clean) {
    Remove-Item -LiteralPath $buildPath -Recurse -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $tempPath -Recurse -Force -ErrorAction SilentlyContinue
}

New-Item -ItemType Directory -Force -Path $buildPath | Out-Null
New-Item -ItemType Directory -Force -Path $tempPath | Out-Null

$env:TEMP = $tempPath
$env:TMP = $tempPath

& $cliWrapper 'compile' '--fqbn' $Fqbn '--build-path' $buildPath $SketchPath
exit $LASTEXITCODE
