$venvPython = 'C:\Users\flysusdjd\Documents\New project 3\ml_pipeline\.venv\Scripts\python.exe'
$scriptPath = 'C:\Users\flysusdjd\Documents\New project 3\pc_gateway\main.py'

if (-not (Test-Path -LiteralPath $venvPython)) {
    Write-Error "Python venv not found: $venvPython"
    exit 1
}

Set-Location 'C:\Users\flysusdjd\Documents\New project 3'
& $venvPython $scriptPath
exit $LASTEXITCODE
