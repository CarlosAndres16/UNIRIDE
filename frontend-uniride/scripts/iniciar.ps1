param([switch]$Instalar)

$ErrorActionPreference = 'Stop'
$projectDirectory = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectDirectory

if (-not (Get-Command node.exe -ErrorAction SilentlyContinue)) {
    throw 'Instala Node.js 26 o posterior antes de iniciar el frontend.'
}
if (-not (Get-Command npm.cmd -ErrorAction SilentlyContinue)) {
    throw 'No se encontró npm.cmd. Revisa la instalación de Node.js.'
}
$nodeMajor = [int]((& node.exe --version).TrimStart('v').Split('.')[0])
if ($nodeMajor -lt 26) {
    throw 'Este proyecto utiliza Node.js 26 o posterior para sus pruebas TypeScript.'
}

if (-not (Test-Path -LiteralPath '.env.local')) {
    Copy-Item -LiteralPath '.env.example' -Destination '.env.local'
    Write-Host 'Configuración local creada. El Gateway predeterminado es http://127.0.0.1:8080.'
}

if ($Instalar -or -not (Test-Path -LiteralPath 'node_modules')) {
    if (Test-Path -LiteralPath 'package-lock.json') {
        & npm.cmd ci
    } else {
        & npm.cmd install
    }
    if ($LASTEXITCODE -ne 0) {
        throw 'La instalación de dependencias falló. Revisa el mensaje de npm.'
    }
}

Write-Host 'Iniciando UniRide en http://localhost:3000. Usa Ctrl+C para detenerlo.'
& npm.cmd run dev
if ($LASTEXITCODE -ne 0) {
    throw 'El frontend no pudo iniciarse. Revisa la salida de Vite.'
}
