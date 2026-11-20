param([switch]$Local, [string]$MapaRuta = '')
$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot
if (-not $MapaRuta) { $MapaRuta = Join-Path $repo 'config\hamachi.json' }
$mapa = Get-Content -LiteralPath $MapaRuta -Raw | ConvertFrom-Json
$fallos = 0
foreach ($nombre in @('usuarios','vehiculos','viajes','reservas','gateway')) {
    $entrada = $mapa.$nombre
    $direccion = if ($Local) { '127.0.0.1' } else { $entrada.host }
    $base = 'http://' + $direccion + ':' + $entrada.port
    $tcp = New-Object System.Net.Sockets.TcpClient
    try {
        $task = $tcp.ConnectAsync($direccion,[int]$entrada.port)
        if (-not $task.Wait(3000) -or -not $tcp.Connected) { throw 'TCP no disponible' }
    } catch {
        Write-Host "$nombre : SIN CONEXION TCP ($base). Revisa Hamachi, firewall y proceso."
        $fallos++; continue
    } finally { $tcp.Dispose() }
    try {
        $salud = Invoke-RestMethod -Uri ($base + '/health') -TimeoutSec 10
        $ready = Invoke-RestMethod -Uri ($base + '/health/ready') -TimeoutSec 10
        if ($salud.status -ne 'UP' -or $ready.status -ne 'UP') { throw 'Servicio no preparado' }
        Write-Host "$nombre : LISTO (proceso y base de datos/dependencias)."
    } catch {
        Write-Host "$nombre : TCP accesible, pero /health/ready falla. Revisa su base de datos o dependencias."
        $fallos++
    }
}
if ($fallos -gt 0) { Write-Host "Diagnóstico: $fallos servicio(s) pendientes."; exit 1 }
Write-Host 'Todas las APIs están disponibles. Esto no sustituye la prueba funcional con JWT.'
