# 安装 PC 网关和机器学习流水线所需的 Python 依赖。
$venvPython = 'C:\Users\flysusdjd\Documents\New project 3\ml_pipeline\.venv\Scripts\python.exe'
$requirementsPath = 'C:\Users\flysusdjd\Documents\New project 3\pc_gateway\requirements.txt'

if (-not (Test-Path -LiteralPath $venvPython)) {
    Write-Error "Python venv not found: $venvPython"
    exit 1
}

& $venvPython -m pip install -r $requirementsPath
exit $LASTEXITCODE
