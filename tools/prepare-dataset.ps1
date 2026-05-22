param(
    [int]$WindowSize = 20,
    [int]$StepSize = 5
)

$venvPython = 'C:\Users\flysusdjd\Documents\New project 3\ml_pipeline\.venv\Scripts\python.exe'
$projectRoot = 'C:\Users\flysusdjd\Documents\New project 3'
$scriptPath = 'C:\Users\flysusdjd\Documents\New project 3\ml_pipeline\prepare_dataset.py'

if (-not (Test-Path -LiteralPath $venvPython)) {
    Write-Error "Python venv not found: $venvPython"
    exit 1
}

Set-Location $projectRoot
& $venvPython $scriptPath --window-size $WindowSize --step-size $StepSize
exit $LASTEXITCODE
