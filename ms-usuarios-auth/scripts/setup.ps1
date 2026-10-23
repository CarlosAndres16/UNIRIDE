param(
    [switch]$IncluirPruebas
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$projectPath = Split-Path -Parent $PSScriptRoot
$pythonPath = Join-Path $projectPath '.venv\Scripts\python.exe'

Write-Host 'Requisitos previos: Python 3.12, SQL Server y Microsoft ODBC Driver 18 for SQL Server.'
Write-Host 'SQL Server debe aceptar autenticacion SQL y el usuario necesita permiso para crear la base.'

Push-Location -LiteralPath $projectPath
try {
    if (-not (Test-Path -LiteralPath $pythonPath)) {
        $launcherCommand = Get-Command py -CommandType Application -ErrorAction SilentlyContinue
        if ($null -ne $launcherCommand) {
            & $launcherCommand.Source -3.12 -m venv .venv
        } else {
            $pythonCommand = Get-Command python -CommandType Application -ErrorAction SilentlyContinue
            if ($null -eq $pythonCommand) {
                throw 'Instale Python 3.12 y habilite py o python en PATH antes de ejecutar este script.'
            }
            $createVenvScript = @'
import sys
import venv

if sys.version_info[:2] != (3, 12):
    raise SystemExit('El comando python debe corresponder a Python 3.12.')
venv.EnvBuilder(with_pip=True).create('.venv')
'@
            & $pythonCommand.Source -c $createVenvScript
        }
        if ($LASTEXITCODE -ne 0) {
            throw 'No se pudo crear el entorno virtual con Python 3.12.'
        }
    }

    $requirementsPath = 'requirements.txt'
    if ($IncluirPruebas) {
        $requirementsPath = 'requirements-dev.txt'
    }
    & $pythonPath -m pip install -r $requirementsPath
    if ($LASTEXITCODE -ne 0) {
        throw 'No se pudieron instalar las dependencias.'
    }

    $envPath = Join-Path $projectPath '.env'
    if (-not (Test-Path -LiteralPath $envPath)) {
        Copy-Item -LiteralPath (Join-Path $projectPath '.env.example') -Destination $envPath
    }

    $configureEnvScript = @'
import getpass
import secrets
from pathlib import Path
from dotenv import dotenv_values, set_key

env_path = Path('.env')
values = dotenv_values(env_path)
if not values.get('JWT_SECRET'):
    set_key(str(env_path), 'JWT_SECRET', secrets.token_urlsafe(48), quote_mode='always')
if not values.get('DB_PASSWORD'):
    password = getpass.getpass('DB_PASSWORD de SQL Server (no se mostrara): ')
    if not password:
        raise SystemExit('DB_PASSWORD no puede estar vacio.')
    set_key(str(env_path), 'DB_PASSWORD', password, quote_mode='always')
    del password
print('Variables locales preparadas en .env; no comparta ni publique ese archivo.')
'@
    & $pythonPath -c $configureEnvScript
    if ($LASTEXITCODE -ne 0) {
        throw 'No se pudo preparar el archivo .env.'
    }

    & $pythonPath -m scripts.create_database
    if ($LASTEXITCODE -ne 0) {
        throw 'No se pudo preparar la base de datos.'
    }

    & $pythonPath -m alembic upgrade head
    if ($LASTEXITCODE -ne 0) {
        throw 'No se pudieron aplicar las migraciones.'
    }

    Write-Host 'Preparacion terminada. Ejecute .\scripts\start.ps1 para iniciar el servicio.'
} finally {
    Pop-Location
}
