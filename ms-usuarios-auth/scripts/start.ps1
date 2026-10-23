$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$projectPath = Split-Path -Parent $PSScriptRoot
$pythonPath = Join-Path $projectPath '.venv\Scripts\python.exe'

Push-Location -LiteralPath $projectPath
try {
    & $pythonPath -m app
    if ($LASTEXITCODE -ne 0) {
        throw 'El servicio termino con un error. Revise las variables de entorno y la instalacion.'
    }
} finally {
    Pop-Location
}
