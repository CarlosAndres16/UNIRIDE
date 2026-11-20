param(
    [Parameter(Mandatory=$true)]
    [ValidateSet('Usuarios','Vehiculos','Viajes','Reservas','Gateway','Frontend')]
    [string]$Servicio,
    [switch]$Instalar
)
$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot
$mapa = Get-Content -LiteralPath (Join-Path $repo 'config\hamachi.json') -Raw | ConvertFrom-Json
$nombre = $Servicio.ToLowerInvariant()
$directorio = Join-Path $repo $mapa.$nombre.carpeta
Push-Location -LiteralPath $directorio
try {
    $configuracion = if ($nombre -eq 'frontend') { '.env.local' } else { '.env' }
    if (-not (Test-Path -LiteralPath $configuracion)) { throw 'Configura primero el servicio con scripts\Configurar-Hamachi.ps1.' }
    if ($nombre -in @('usuarios','vehiculos','reservas')) {
        $python = Join-Path $directorio '.venv\Scripts\python.exe'
        if ($Instalar) {
            if (-not (Test-Path -LiteralPath $python)) {
                & py -3 -m venv .venv
                if ($LASTEXITCODE -ne 0) { throw 'No se pudo crear .venv. Instala Python 3.12 o posterior.' }
            }
            & $python -m pip install -r requirements.txt
            if ($LASTEXITCODE -ne 0) { throw 'Falló la instalación de dependencias Python.' }
        }
        if (-not (Test-Path -LiteralPath $python)) { throw 'Falta .venv. Ejecuta el mismo comando con -Instalar.' }
        $modulo = if ($nombre -eq 'reservas') { 'app.main' } else { 'app' }
        & $python -m $modulo
    } else {
        if ($Instalar) { & npm.cmd ci; if ($LASTEXITCODE -ne 0) { throw 'Falló npm ci.' } }
        if (-not (Test-Path -LiteralPath 'node_modules')) { throw 'Faltan dependencias. Ejecuta el mismo comando con -Instalar.' }
        if ($nombre -eq 'frontend') { & npm.cmd run dev } else { & npm.cmd start }
    }
    if ($LASTEXITCODE -ne 0) { throw "El proceso $Servicio terminó con error. Revisa la configuración y la salida anterior." }
} finally { Pop-Location }
