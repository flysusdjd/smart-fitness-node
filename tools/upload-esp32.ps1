# 编译并上传 ESP32-S3 固件到开发板。
param(
    [Parameter(Mandatory = $true)]
    [string]$Port,
    [string]$SketchPath = (Join-Path (Split-Path -Parent $PSScriptRoot) 'ESPS3'),
    [string]$Fqbn = 'esp32:esp32:esp32s3',
    [switch]$SkipBuild
)

$projectRoot = Split-Path -Parent $PSScriptRoot
$buildPath = Join-Path $projectRoot '.arduino-build\esp32s3'
$cliWrapper = Join-Path $PSScriptRoot 'arduino-cli.ps1'
$compileScript = Join-Path $PSScriptRoot 'compile-esp32.ps1'

if (-not $SkipBuild) {
    & $compileScript -SketchPath $SketchPath -Fqbn $Fqbn
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }
}

& $cliWrapper 'upload' '-p' $Port '--fqbn' $Fqbn '--input-dir' $buildPath $SketchPath
exit $LASTEXITCODE
