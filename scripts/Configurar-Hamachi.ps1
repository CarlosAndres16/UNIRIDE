param(
    [ValidateSet('Usuarios','Vehiculos','Viajes','Reservas','Gateway','Frontend','Todos')]
    [string]$Servicio = 'Reservas',
    [string]$ClavesRuta = '',
    [string]$MapaRuta = '',
    [switch]$GenerarClaves,
    [switch]$Local
)
$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot
if (-not $MapaRuta) { $MapaRuta = Join-Path $repo 'config\hamachi.json' }
if (-not $ClavesRuta) {
    $ClavesRuta = Join-Path $repo $(if ($GenerarClaves) { 'config\.env.equipo' } else { 'config\claves-practica.env' })
}
$mapa = Get-Content -LiteralPath $MapaRuta -Raw | ConvertFrom-Json

function Leer-Variable([string]$Archivo, [string]$Nombre) {
    if (-not (Test-Path -LiteralPath $Archivo)) { return $null }
    $lineas = @(Get-Content -LiteralPath $Archivo | Where-Object { $_ -match ('^\s*' + [regex]::Escape($Nombre) + '\s*=') })
    if ($lineas.Count -gt 1) { throw "Variable duplicada: $Nombre. Corrige el archivo antes de continuar." }
    if ($lineas.Count -eq 0) { return $null }
    $valor = ($lineas[0] -split '=',2)[1].Trim()
    if (($valor.StartsWith('"') -and $valor.EndsWith('"')) -or ($valor.StartsWith("'") -and $valor.EndsWith("'"))) {
        $valor = $valor.Substring(1,$valor.Length-2)
    }
    return $valor
}
function Nueva-Clave {
    $bytes = New-Object byte[] 64
    $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try { $rng.GetBytes($bytes) } finally { $rng.Dispose() }
    return [Convert]::ToBase64String($bytes).TrimEnd('=').Replace('+','-').Replace('/','_')
}
function Guardar-Utf8([string]$Archivo, [string]$Contenido) {
    [System.IO.File]::WriteAllText($Archivo, $Contenido, (New-Object System.Text.UTF8Encoding($false)))
}
function Establecer-Variables([string]$Archivo, [System.Collections.IDictionary]$Valores) {
    $contenido = [System.IO.File]::ReadAllText($Archivo)
    $original = $contenido
    foreach ($nombre in $Valores.Keys) {
        $patron = '(?m)^\s*' + [regex]::Escape($nombre) + '\s*=[^\r\n]*'
        if ([regex]::Matches($contenido, $patron).Count -gt 1) { throw "Variable duplicada: $nombre." }
        $linea = $nombre + '=' + $Valores[$nombre]
        if ([regex]::IsMatch($contenido,$patron)) {
            $contenido = [regex]::Replace($contenido,$patron,[System.Text.RegularExpressions.MatchEvaluator]{ param($m) $linea })
        } else { $contenido = $contenido.TrimEnd("`r","`n") + "`r`n" + $linea + "`r`n" }
    }
    if ($contenido -ne $original) {
        Copy-Item -LiteralPath $Archivo -Destination ($Archivo + '.backup-' + (Get-Date -Format 'yyyyMMdd-HHmmss-fff'))
        Guardar-Utf8 $Archivo $contenido
    }
}

# La práctica usa el par público del repositorio. -ClavesRuta permite otro par explícito.
# GenerarClaves escribe un archivo privado aparte y nunca cambia el par público.
if ($GenerarClaves) {
    if (Test-Path -LiteralPath $ClavesRuta) { throw 'El archivo de claves ya existe. No se rotan claves de forma automática.' }
    New-Item -ItemType Directory -Path (Split-Path -Parent ([System.IO.Path]::GetFullPath($ClavesRuta))) -Force | Out-Null
    Guardar-Utf8 $ClavesRuta ("JWT_SECRET=" + (Nueva-Clave) + "`r`nSERVICE_API_KEY=" + (Nueva-Clave) + "`r`n")
    Write-Host 'Archivo privado de claves generado. No se muestran sus valores ni debe subirse a GitHub.'
}
$seleccion = if ($Servicio -eq 'Todos') { @('usuarios','vehiculos','viajes','reservas','gateway','frontend') } else { @($Servicio.ToLowerInvariant()) }
$jwt = $null; $serviceKey = $null
if (@($seleccion | Where-Object { $_ -in @('usuarios','vehiculos','viajes','reservas') }).Count -gt 0) {
    $jwt = Leer-Variable $ClavesRuta 'JWT_SECRET'
    if (-not $jwt -or [System.Text.Encoding]::UTF8.GetByteCount($jwt) -lt 32) { throw 'Falta JWT_SECRET válido en el archivo de claves. Actualiza el repositorio o revisa -ClavesRuta.' }
    $serviceKey = Leer-Variable $ClavesRuta 'SERVICE_API_KEY'
    if (@($seleccion | Where-Object { $_ -in @('viajes','reservas') }).Count -gt 0 -and
        (-not $serviceKey -or [System.Text.Encoding]::UTF8.GetByteCount($serviceKey) -lt 32 -or $serviceKey -eq $jwt)) {
        throw 'Falta SERVICE_API_KEY válida y distinta del JWT_SECRET en el archivo de claves.'
    }
    if ($jwt -notmatch '^[A-Za-z0-9_-]{32,}$' -or ($serviceKey -and $serviceKey -notmatch '^[A-Za-z0-9_-]{32,}$')) {
        throw 'El archivo de equipo debe contener las claves URL-safe generadas para esta integración, sin espacios ni comentarios en la misma línea.'
    }
}
function Url-Servicio([string]$Nombre) {
    $entrada = $mapa.$Nombre
    $direccion = if ($Local) { '127.0.0.1' } else { $entrada.host }
    return 'http://' + $direccion + ':' + $entrada.port
}
foreach ($nombre in $seleccion) {
    $entrada = $mapa.$nombre
    if (-not $entrada -or $entrada.port -lt 1 -or $entrada.port -gt 65535) { throw "Mapa inválido para $nombre." }
    $carpeta = Join-Path $repo $entrada.carpeta
    $archivo = Join-Path $carpeta $(if ($nombre -eq 'frontend') { '.env.local' } else { '.env' })
    if (-not (Test-Path -LiteralPath $archivo)) { Copy-Item -LiteralPath (Join-Path $carpeta '.env.example') -Destination $archivo }
    $valores = [ordered]@{}
    if ($nombre -eq 'frontend') {
        $valores['GATEWAY_URL'] = Url-Servicio 'gateway'
        $valores['VITE_API_BASE_URL'] = '/api/v1'
        $valores['FRONTEND_HOST'] = '0.0.0.0'
        $valores['FRONTEND_PORT'] = $entrada.port
    } else {
        $valores['SERVER_HOST'] = '0.0.0.0'; $valores['SERVER_PORT'] = $entrada.port
        if ($nombre -ne 'gateway') { $valores['JWT_SECRET'] = $jwt }
        if ($nombre -in @('viajes','reservas')) {
            $valores['SERVICE_API_KEY'] = $serviceKey
            $valores['VEHICULOS_SERVICE_URL'] = Url-Servicio 'vehiculos'
        }
        if ($nombre -eq 'reservas') { $valores['VIAJES_SERVICE_URL'] = Url-Servicio 'viajes' }
        if ($nombre -eq 'gateway') {
            foreach ($destino in @('usuarios','vehiculos','viajes','reservas')) { $valores[$destino.ToUpperInvariant() + '_SERVICE_URL'] = Url-Servicio $destino }
            $valores['FRONTEND_ORIGIN'] = 'http://localhost:3000,http://127.0.0.1:3000,' + (Url-Servicio 'frontend')
            $valores['GATEWAY_TIMEOUT_MS'] = 20000
            $valores['READINESS_TIMEOUT_MS'] = 8000
        }
    }
    Establecer-Variables $archivo $valores
    if ($nombre -eq 'frontend') { Write-Host ("Gateway del frontend: " + $valores['GATEWAY_URL'] + ' (segun el mapa de red).') }
    Write-Host "Configurado $nombre. Se conservaron las variables DB_*; revisa las de tu propio equipo si es la primera instalación."
}
Write-Host 'Reinicia los procesos o recrea los contenedores afectados para cargar los cambios.'
