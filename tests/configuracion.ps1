param()

# Offline regression checks. Only synthetic files under .setup are modified.
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$repo = Split-Path -Parent $PSScriptRoot
$fixtureRoot = Join-Path $repo ('.setup\configuracion-tests-' + [guid]::NewGuid().ToString('N'))
$folders = [ordered]@{
    usuarios = 'ms-usuarios-auth'; vehiculos = 'ms-vehiculos'; viajes = 'ms-viajes'
    reservas = 'ms-reservas-estadisticas'; gateway = 'api-gateway'; frontend = 'frontend-uniride'
}
$ports = @{ usuarios = 8081; vehiculos = 8082; viajes = 8083; reservas = 8084; gateway = 8080; frontend = 3000 }
$hosts = @{
    usuarios = '25.32.113.17'; vehiculos = '25.0.88.33'; viajes = '25.33.226.75'
    reservas = '25.1.20.39'; gateway = '25.1.20.39'; frontend = '25.1.20.39'
}
$jwt = 'jwt-ficticio-exclusivo-pruebas-1234567890'
$serviceKey = 'service-ficticio-exclusivo-pruebas-9876543210'
$script:assertions = 0

function Assert-Test([bool]$Condition, [string]$Description) {
    if (-not $Condition) { throw ('FALLO: ' + $Description) }
    $script:assertions++
}

function Write-TestFile([string]$Path, [string]$Content) {
    [System.IO.File]::WriteAllText($Path, $Content, (New-Object System.Text.UTF8Encoding($false)))
}

function Read-Variables([string]$Path) {
    $values = @{}
    foreach ($line in [System.IO.File]::ReadAllLines($Path)) {
        if ($line -match '^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=(.*)$') {
            $key = $Matches[1]
            Assert-Test (-not $values.ContainsKey($key)) ('Variable unica: ' + $key)
            $values[$key] = $Matches[2].Trim()
        }
    }
    return $values
}

function Get-EnvPath([string]$Fixture, [string]$Name) {
    $fileName = if ($Name -eq 'frontend') { '.env.local' } else { '.env' }
    return Join-Path (Join-Path $Fixture $folders[$Name]) $fileName
}

function New-Fixture([string]$Name) {
    $path = Join-Path $fixtureRoot $Name
    New-Item -ItemType Directory -Path (Join-Path $path 'scripts'), (Join-Path $path 'config') -Force | Out-Null
    foreach ($scriptFile in Get-ChildItem -LiteralPath (Join-Path $repo 'scripts') -Filter '*.ps1' -File) {
        Copy-Item -LiteralPath $scriptFile.FullName -Destination (Join-Path $path 'scripts')
    }
    Copy-Item -LiteralPath (Join-Path $repo 'config\hamachi.json') -Destination (Join-Path $path 'config\hamachi.json')
    foreach ($folder in $folders.Values) {
        $destination = Join-Path $path $folder
        New-Item -ItemType Directory -Path $destination -Force | Out-Null
        Copy-Item -LiteralPath (Join-Path (Join-Path $repo $folder) '.env.example') -Destination $destination
    }
    return $path
}

function Invoke-Configurator([string]$Fixture, [hashtable]$Arguments) {
    $lines = New-Object 'System.Collections.Generic.List[string]'
    $succeeded = $false
    try {
        & (Join-Path $Fixture 'scripts\Configurar-Hamachi.ps1') @Arguments *>&1 |
            ForEach-Object { $lines.Add([string]$_) }
        $succeeded = $true
    } catch {
        $lines.Add($_.Exception.Message)
    }
    return [pscustomobject]@{ Succeeded = $succeeded; Output = ($lines -join "`n") }
}

function Assert-NoSecrets([string]$Output, [string[]]$Secrets) {
    foreach ($secret in $Secrets) {
        Assert-Test (-not $Output.Contains($secret)) 'La salida no contiene claves privadas de prueba.'
    }
}

function Assert-NoEnvs([string]$Fixture) {
    foreach ($name in $folders.Keys) {
        Assert-Test (-not (Test-Path -LiteralPath (Get-EnvPath $Fixture $name))) ('Sin archivo parcial para ' + $name)
    }
}

# Parse every repository PowerShell file, excluding generated dependencies and fixtures.
$pending = New-Object 'System.Collections.Generic.Stack[string]'
$pending.Push($repo)
$parsed = 0
while ($pending.Count -gt 0) {
    $directory = $pending.Pop()
    foreach ($file in Get-ChildItem -LiteralPath $directory -Filter '*.ps1' -File) {
        $tokens = $null; $parseErrors = $null
        $null = [System.Management.Automation.Language.Parser]::ParseFile($file.FullName, [ref]$tokens, [ref]$parseErrors)
        Assert-Test (@($parseErrors).Count -eq 0) ('Sintaxis PowerShell: ' + $file.FullName)
        $parsed++
    }
    foreach ($child in Get-ChildItem -LiteralPath $directory -Directory) {
        if ($child.Name -notin @('.git', '.setup', '.venv', 'node_modules', '__pycache__', '.pytest_cache', 'dist')) {
            $pending.Push($child.FullName)
        }
    }
}

$fixture = New-Fixture 'hamachi-existing'
$keysPath = Join-Path $fixture 'config\.env.equipo'
Write-TestFile $keysPath ("JWT_SECRET=$jwt`r`nSERVICE_API_KEY=$serviceKey`r`n")
$keyBytes = [System.IO.File]::ReadAllText($keysPath)
$keyTimestamp = (Get-Item -LiteralPath $keysPath).LastWriteTimeUtc.Ticks
$before = @{}
$dbSnapshots = @{}
foreach ($name in @('usuarios', 'vehiculos', 'viajes', 'reservas')) {
    $path = Get-EnvPath $fixture $name
    $dbText = "# Base local ficticia: conservar exactamente.`r`nDB_HOST=sql-$name.invalid`r`nDB_PORT=14330`r`nDB_NAME=base_$name`r`nDB_USER=cuenta_$name`r`nDB_PASSWORD=clave-ficticia-$name-123!`r`nJWT_SECRET=anterior-ficticio`r`nSERVER_PORT=9000`r`n"
    Write-TestFile $path $dbText
    $before[$name] = $dbText
    $dbSnapshots[$name] = Read-Variables $path
}
$result = Invoke-Configurator $fixture @{ Servicio = 'Todos'; ClavesRuta = $keysPath }
Assert-Test $result.Succeeded 'Configuracion Hamachi completa.'
Assert-NoSecrets $result.Output @($jwt, $serviceKey)
Assert-Test ([System.IO.File]::ReadAllText($keysPath) -ceq $keyBytes) 'El archivo de claves existente conserva su contenido.'
Assert-Test ((Get-Item -LiteralPath $keysPath).LastWriteTimeUtc.Ticks -eq $keyTimestamp) 'El archivo de claves existente no se reescribe.'
$map = Get-Content -LiteralPath (Join-Path $fixture 'config\hamachi.json') -Raw | ConvertFrom-Json
$configured = @{}
foreach ($name in $folders.Keys) {
    Assert-Test ($map.$name.host -eq $hosts[$name]) ('IP Hamachi acordada para ' + $name)
    Assert-Test ($map.$name.port -eq $ports[$name]) ('Puerto acordado para ' + $name)
    $path = Get-EnvPath $fixture $name
    Assert-Test (Test-Path -LiteralPath $path) ('Configuracion creada para ' + $name)
    $values = Read-Variables $path
    $configured[$name] = $values
    if ($name -eq 'frontend') {
        Assert-Test ($values['FRONTEND_HOST'] -eq '0.0.0.0' -and $values['FRONTEND_PORT'] -eq '3000') 'Frontend escucha en LAN y puerto 3000.'
        Assert-Test ($values['GATEWAY_URL'] -eq 'http://25.1.20.39:8080') 'Frontend apunta al Gateway Hamachi.'
        Assert-Test ($values['VITE_API_BASE_URL'] -eq '/api/v1') 'El navegador usa la ruta relativa del proxy.'
    } else {
        Assert-Test ($values['SERVER_HOST'] -eq '0.0.0.0') ('Escucha LAN para ' + $name)
        Assert-Test ($values['SERVER_PORT'] -eq [string]$ports[$name]) ('Puerto HTTP configurado para ' + $name)
    }
    if ($name -in @('usuarios', 'vehiculos', 'viajes', 'reservas')) {
        Assert-Test ($values['JWT_SECRET'] -ceq $jwt) ('JWT comun para ' + $name)
        foreach ($key in @('DB_HOST', 'DB_PORT', 'DB_NAME', 'DB_USER', 'DB_PASSWORD')) {
            Assert-Test ($values[$key] -ceq $dbSnapshots[$name][$key]) ('Preservar ' + $key + ' en ' + $name)
        }
        $backups = @(Get-ChildItem -LiteralPath (Split-Path -Parent $path) -Filter '.env.backup-*' -File)
        Assert-Test ($backups.Count -eq 1) ('Backup antes de modificar ' + $name)
        Assert-Test ([System.IO.File]::ReadAllText($backups[0].FullName) -ceq $before[$name]) ('Backup exacto para ' + $name)
    } else {
        Assert-Test (-not $values.ContainsKey('JWT_SECRET')) ('Sin JWT del servidor en ' + $name)
    }
    if ($name -in @('viajes', 'reservas')) {
        Assert-Test ($values['SERVICE_API_KEY'] -ceq $serviceKey) ('Llave interna comun para ' + $name)
        Assert-Test ($values['VEHICULOS_SERVICE_URL'] -eq 'http://25.0.88.33:8082') ('URL Vehiculos de ' + $name)
    } else {
        Assert-Test (-not $values.ContainsKey('SERVICE_API_KEY')) ('Llave interna ausente en ' + $name)
    }
}
Assert-Test ($configured['reservas']['VIAJES_SERVICE_URL'] -eq 'http://25.33.226.75:8083') 'Reservas apunta a Viajes Hamachi.'
foreach ($name in @('usuarios', 'vehiculos', 'viajes', 'reservas')) {
    $key = $name.ToUpperInvariant() + '_SERVICE_URL'
    Assert-Test ($configured['gateway'][$key] -eq ('http://' + $hosts[$name] + ':' + $ports[$name])) ('Gateway apunta a ' + $name)
}
Assert-Test ($configured['gateway']['FRONTEND_ORIGIN'].Split(',') -contains 'http://25.1.20.39:3000') 'CORS incluye el frontend Hamachi.'

$result = Invoke-Configurator $fixture @{ Servicio = 'Todos'; ClavesRuta = $keysPath; Local = $true }
Assert-Test $result.Succeeded 'Configuracion Local completa.'
Assert-NoSecrets $result.Output @($jwt, $serviceKey)
foreach ($name in $folders.Keys) {
    $values = Read-Variables (Get-EnvPath $fixture $name)
    foreach ($key in @($values.Keys)) {
        if ($key -match '(_SERVICE_URL|^GATEWAY_URL)$') {
            $uri = [uri]$values[$key]
            Assert-Test ($uri.IsLoopback -and $uri.Host -eq '127.0.0.1') ('Local usa loopback en ' + $name + '/' + $key)
            Assert-Test ($values[$key] -notmatch '25\.') ('Local no conserva IP Hamachi en ' + $name + '/' + $key)
        }
    }
    if ($name -in @('usuarios', 'vehiculos', 'viajes', 'reservas')) {
        foreach ($key in @('DB_HOST', 'DB_PORT', 'DB_NAME', 'DB_USER', 'DB_PASSWORD')) {
            Assert-Test ($values[$key] -ceq $dbSnapshots[$name][$key]) ('Local preserva ' + $key + ' en ' + $name)
        }
    }
}

foreach ($missing in @('JWT_SECRET', 'SERVICE_API_KEY')) {
    $missingFixture = New-Fixture ('missing-' + $missing)
    $missingKeys = Join-Path $missingFixture 'config\.env.equipo'
    if ($missing -eq 'SERVICE_API_KEY') { Write-TestFile $missingKeys ("JWT_SECRET=$jwt`r`n") }
    $result = Invoke-Configurator $missingFixture @{ Servicio = 'Todos'; ClavesRuta = $missingKeys }
    Assert-Test (-not $result.Succeeded) ('Falla si falta ' + $missing)
    Assert-Test ($result.Output.Contains('Falta ' + $missing)) ('Mensaje identifica ' + $missing)
    Assert-NoSecrets $result.Output @($jwt, $serviceKey)
    Assert-NoEnvs $missingFixture
}

$generatedFixture = New-Fixture 'generate-once'
$generatedKeys = Join-Path $generatedFixture 'config\.env.equipo'
$result = Invoke-Configurator $generatedFixture @{ Servicio = 'Todos'; ClavesRuta = $generatedKeys; GenerarClaves = $true }
Assert-Test $result.Succeeded 'Generacion inicial de claves en fixture aislado.'
$generatedContent = [System.IO.File]::ReadAllText($generatedKeys)
$generated = Read-Variables $generatedKeys
Assert-Test ($generated.Count -eq 2) 'El archivo de equipo contiene solo las dos claves.'
Assert-Test ($generated['JWT_SECRET'] -match '^[A-Za-z0-9_-]{32,}$') 'JWT generado URL-safe.'
Assert-Test ($generated['SERVICE_API_KEY'] -match '^[A-Za-z0-9_-]{32,}$') 'Llave interna generada URL-safe.'
Assert-Test ($generated['JWT_SECRET'] -cne $generated['SERVICE_API_KEY']) 'Claves generadas distintas.'
Assert-NoSecrets $result.Output @($generated['JWT_SECRET'], $generated['SERVICE_API_KEY'])
$generatedTimestamp = (Get-Item -LiteralPath $generatedKeys).LastWriteTimeUtc.Ticks
$envContents = @{}
foreach ($name in $folders.Keys) { $envContents[$name] = [System.IO.File]::ReadAllText((Get-EnvPath $generatedFixture $name)) }
$result = Invoke-Configurator $generatedFixture @{ Servicio = 'Todos'; ClavesRuta = $generatedKeys; GenerarClaves = $true }
Assert-Test (-not $result.Succeeded) 'GenerarClaves rechaza un archivo existente.'
Assert-Test ($result.Output.Contains('ya existe')) 'La negativa explica que el archivo existe.'
Assert-Test ([System.IO.File]::ReadAllText($generatedKeys) -ceq $generatedContent) 'GenerarClaves no sobrescribe claves existentes.'
Assert-Test ((Get-Item -LiteralPath $generatedKeys).LastWriteTimeUtc.Ticks -eq $generatedTimestamp) 'GenerarClaves no reescribe el archivo existente.'
Assert-NoSecrets $result.Output @($generated['JWT_SECRET'], $generated['SERVICE_API_KEY'])
foreach ($name in $folders.Keys) {
    Assert-Test ([System.IO.File]::ReadAllText((Get-EnvPath $generatedFixture $name)) -ceq $envContents[$name]) ('Sin modificaciones tras rechazar rotacion: ' + $name)
}

Write-Host ("OK: {0} aserciones; {1} scripts PowerShell parseados; pruebas offline sin bases reales ni red." -f $script:assertions, $parsed)
Write-Host ('Fixtures conservados en ' + $fixtureRoot)
