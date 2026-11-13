<#
.SYNOPSIS
    Prueba local de deploy.ps1 contra un servidor Fabric SIMULADO (127.0.0.1). No toca Fabric ni la capacidad.

.DESCRIPTION
    Carga deploy.ps1 con punto (solo define funciones), sustituye el token, el cliente SQL y la carga a OneLake
    por simulaciones, apunta la API a localhost y ejecuta tres escenarios:
      1. Primera corrida: crea Lakehouse, Warehouse, Environment y notebooks.
      2. Segunda corrida: idempotente, no crea nada (solo actualiza notebooks).
      3. -WhatIf: no emite ninguna solicitud que no sea GET.
    Comprueba además que toda solicitud lleva x-ms-fabric-skill y que ningún elemento AB_* recibe escrituras.
    Es 100 % local: no usa red, credenciales ni Azure CLI (`az` se sustituye por una función que falla si se invoca).
    Requiere el .whl en librerias\B2_paquete_environment\dist (ver el README: python -m build --wheel).
#>
#Requires -Version 7.0
$ErrorActionPreference = 'Stop'
$aqui = $PSScriptRoot
$deploy = Join-Path (Split-Path $aqui -Parent) 'deploy\deploy.ps1'
$puerto = 18765
$nombreWorkspace = 'ws-simulado'
$registro = Join-Path $aqui 'registro_mock.json'
Remove-Item $registro -ErrorAction SilentlyContinue

$mock = Join-Path $aqui 'mock_fabric.py'
$servidor = Start-Process python -ArgumentList @("`"$mock`"", '--puerto', $puerto, '--registro', "`"$registro`"", '--workspace', $nombreWorkspace) -PassThru -WindowStyle Hidden
try {
    for ($i = 0; $i -lt 40; $i++) {
        if (Test-NetConnection -ComputerName 127.0.0.1 -Port $puerto -WarningAction SilentlyContinue -InformationLevel Quiet) { break }
        Start-Sleep -Milliseconds 250
    }
    . $deploy -WorkspaceName $nombreWorkspace
    function az { throw 'La prueba local nunca debe invocar az' }
    function Get-TokenAz { param($Destino) 'token-simulado' }
    function Invoke-SqlScript { param($Servidor, $BaseDatos, $Ruta, [switch]$MostrarResultados) Write-Host "  [mock sql] $(Split-Path $Ruta -Leaf) en $Servidor/$BaseDatos"; [pscustomobject]@{ Archivo = (Split-Path $Ruta -Leaf); Lotes = 1; Fallas = 0 } }
    function Send-OneLakeArchivo { param($WorkspaceId, $LakehouseId, $RutaRelativa, [byte[]]$Bytes) Write-Host "  [mock onelake] $RutaRelativa ($($Bytes.Length) bytes)" }
    $FabricApi = "http://127.0.0.1:$puerto/v1"
    $TimeoutPublicacionMin = 1

    function Leer-Registro { Start-Sleep -Milliseconds 300; @(Get-Content $registro -Raw | ConvertFrom-Json) }
    function Resumen-Escrituras($entradas) { @($entradas | Where-Object { $_.metodo -ne 'GET' }) }

    Write-Host "`n##### Escenario 1: primera corrida" -ForegroundColor Magenta
    $script:EsSimulacion = $false; $script:Resumen.Clear()
    Start-Despliegue
    $r1 = Leer-Registro
    $creaciones1 = @($r1 | Where-Object { $_.metodo -eq 'POST' -and $_.ruta -match '/(lakehouses|warehouses|environments|notebooks)$' })

    Write-Host "`n##### Escenario 2: segunda corrida (idempotencia)" -ForegroundColor Magenta
    $antes = $r1.Count
    $script:Resumen.Clear()
    Start-Despliegue
    $r2 = Leer-Registro
    $nuevas2 = @($r2 | Select-Object -Skip $antes)
    $creaciones2 = @($nuevas2 | Where-Object { $_.metodo -eq 'POST' -and $_.ruta -match '/(lakehouses|warehouses|environments|notebooks)$' })

    Write-Host "`n##### Escenario 3: -WhatIf" -ForegroundColor Magenta
    $antes3 = $r2.Count
    $script:Resumen.Clear(); $script:EsSimulacion = $true
    Start-Despliegue
    $r3 = Leer-Registro
    $nuevas3 = @($r3 | Select-Object -Skip $antes3)

    $fallas = @()
    if ($creaciones1.Count -ne 8) { $fallas += "esperaba 8 creaciones en la 1a corrida (lakehouse, warehouse, environment, 5 notebooks) y hubo $($creaciones1.Count)" }
    if ($creaciones2.Count -ne 0) { $fallas += "la 2a corrida creó $($creaciones2.Count) elementos (no es idempotente)" }
    if (@(Resumen-Escrituras $nuevas3).Count -ne 0) { $fallas += "-WhatIf emitió escrituras: $((Resumen-Escrituras $nuevas3).ruta -join ', ')" }
    if (@($r3 | Where-Object { -not $_.skill -or -not $_.autorizacion }).Count -gt 0) { $fallas += 'hay solicitudes sin x-ms-fabric-skill o sin Authorization' }
    $skills = @($r3 | ForEach-Object skill | Sort-Object -Unique)
    if (@($r3 | Where-Object { $_.metodo -ne 'GET' -and $_.ruta -match '33333333|44444444' }).Count -gt 0) { $fallas += 'se escribió sobre un elemento AB_*' }
    if (@($r3 | Where-Object { $_.ruta -match 'capacities/.*(resume|suspend)|resume|suspend' }).Count -gt 0) { $fallas += 'se tocó la capacidad' }
    $nb = @($r1 | Where-Object { $_.partes } | ForEach-Object { $_.partes } | Where-Object { $_.path -like '*.ipynb' })
    if ($nb.Count -lt 5 -or @($nb | Where-Object { -not $_.json_valido }).Count -gt 0) { $fallas += 'definiciones de notebook ausentes o no JSON' }
    if (@($nb | Where-Object { $_.texto -match '\{\{[A-Z_]+\}\}' }).Count -gt 0) { $fallas += 'quedaron marcadores {{...}} sin reemplazar en los notebooks subidos' }
    $wheelSubido = @($r1 | Where-Object { $_.partes } | ForEach-Object { $_.partes } | Where-Object { $_.path -like 'Libraries/CustomLibraries/fac_utils-*.whl' })
    if ($wheelSubido.Count -ne 1) { $fallas += "el .whl debía subirse una vez y se subió $($wheelSubido.Count)" }

    Write-Host "`nSolicitudes: corrida1=$($r1.Count) corrida2=$($nuevas2.Count) whatif=$($nuevas3.Count) | skills usados: $($skills -join ', ')"
    if ($fallas) { $fallas | ForEach-Object { Write-Host "FALLA: $_" -ForegroundColor Red }; exit 1 }
    Write-Host 'OK: flujo, idempotencia y -WhatIf verificados contra el servidor simulado' -ForegroundColor Green
}
finally {
    if ($servidor -and -not $servidor.HasExited) { Stop-Process -Id $servidor.Id -Force }
    Remove-Item $registro -ErrorAction SilentlyContinue
}
