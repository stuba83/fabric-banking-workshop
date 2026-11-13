<#
.SYNOPSIS
    Despliega los elementos FAC_* del demo Warehouse + bibliotecas en el workspace que indique quien despliega.

.DESCRIPTION
    Idempotente: cada elemento se resuelve por nombre; si existe no se vuelve a crear y su contenido se
    actualiza. Con -WhatIf solo hace lecturas (token, listados, estado de la capacidad) y muestra lo que haría.

    Crea o actualiza:
      Lakehouse   FAC_LH_Utils        (con esquemas; guarda la bitácora y Files/libs/fac_utils_lh.py)
      Warehouse   FAC_WH_Gold         (ejecuta 01_esquemas_tablas.sql y 02_procedimientos.sql)
      Environment FAC_ENV_Utils       (con el .whl de fac_utils; lo publica)
      Notebooks   FAC_NB_Utils, FAC_NB_Demo_Libreria_A/B/C, FAC_NB_Spark_vs_TSQL
      Pipeline    FAC_PL_Gold_Warehouse (solo con -DesplegarPipeline)

    NO modifica ningún elemento AB_*: solo lo lee (AB_Lakehouse debe existir). NUNCA reanuda, pausa ni escala
    la capacidad: si no está Activa, se detiene con un mensaje. Nunca ejecuta az login ni az account set: usa la
    sesión actual de Azure CLI (quien despliega ya ejecutó 'az login'); -AzureConfigDir es opcional y solo sirve para
    apuntar a otro perfil de Azure CLI (AZURE_CONFIG_DIR) durante esta ejecución.

    Cómo se ejecuta el SQL (decisión): se abre una conexión TDS con System.Data.SqlClient (incluido en
    PowerShell 7) usando un token de Entra de az para https://database.windows.net/. Motivo: ADO.NET no exige
    instalar nada (sqlcmd, el módulo SqlServer o un controlador ODBC). Alternativas válidas: sqlcmd -G, el editor SQL del portal o la herramienta MCP execute_query
    (un lote por llamada, sin GO).

.PARAMETER WorkspaceName
    OBLIGATORIO. Nombre del workspace donde se despliega (lo elige quien despliega; en el laboratorio, un nombre con
    su prefijo propio). El workspace debe tener capacidad Activa y contener el Lakehouse de origen (-LakehouseOrigen).
.PARAMETER AzureConfigDir
    Opcional. Carpeta de configuración de Azure CLI (AZURE_CONFIG_DIR) solo si se necesita un perfil distinto del
    predeterminado. Si se omite, se usa la sesión actual de Azure CLI.
.PARAMETER EjecutarPruebas
    Ejecuta warehouse\03_pruebas.sql y falla si alguna fila tiene estado FALLA.
.PARAMETER EjecutarComparacion
    Ejecuta comparacion\comparacion_tsql.sql (informa tiempos; no falla por tiempos).
.PARAMETER DesplegarPipeline
    Crea/actualiza FAC_PL_Gold_Warehouse con la plantilla JSON.
.PARAMETER RefrescarEndpoint
    Pide la sincronización de metadatos de los SQL analytics endpoints de AB_Lakehouse (si el Warehouse no ve
    las tablas) y de FAC_LH_Utils (para leer la bitácora de los notebooks); no modifica datos.
.PARAMETER RestablecerDemo
    Ejecuta warehouse\04_estado_inicial.sql: vacía bitácora y reconciliación y deja UNA carga completa (estado
    inicial reproducible para la demo en vivo).
.PARAMETER EnvironmentModo
    Definicion (predeterminado): sube el .whl dentro de la definición del Environment.
    Upload: usa la API de carga de biblioteca personalizada (multipart) si la definición falla.

.EXAMPLE
    pwsh -File .\deploy.ps1 -WorkspaceName 'MI-WORKSPACE' -WhatIf
.EXAMPLE
    pwsh -File .\deploy.ps1 -WorkspaceName 'MI-WORKSPACE' -EjecutarPruebas -EjecutarComparacion -RefrescarEndpoint
#>
#Requires -Version 7.0
[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [Parameter(Mandatory)][ValidateNotNullOrEmpty()][string]$WorkspaceName,
    [string]$WorkspaceId = '',
    [string]$LakehouseOrigen = 'AB_Lakehouse',
    [string]$PrefijoTablas = 'ab',
    [string]$WarehouseName = 'FAC_WH_Gold',
    [string]$LakehouseFacName = 'FAC_LH_Utils',
    [string]$EnvironmentName = 'FAC_ENV_Utils',
    [string]$AzureConfigDir = '',
    [ValidateSet('Definicion', 'Upload')][string]$EnvironmentModo = 'Definicion',
    [switch]$EjecutarPruebas,
    [switch]$EjecutarComparacion,
    [switch]$DesplegarPipeline,
    [switch]$RefrescarEndpoint,
    [switch]$RestablecerDemo,
    [switch]$OmitirSql,
    [switch]$OmitirModulo,
    [switch]$OmitirEnvironment,
    [switch]$OmitirNotebooks,
    [int]$TimeoutPublicacionMin = 20
)

$ErrorActionPreference = 'Stop'
$RaizDemo = Split-Path -Parent $PSScriptRoot
$FabricApi = 'https://api.fabric.microsoft.com/v1'
$script:EsSimulacion = [bool]$WhatIfPreference
$script:Tokens = @{}
$script:Resumen = [System.Collections.Generic.List[object]]::new()

# ---------------------------------------------------------------------------------------------
# Utilidades generales
# ---------------------------------------------------------------------------------------------
function Write-Paso([string]$Texto) { Write-Host "`n== $Texto" -ForegroundColor Cyan }

function Add-Resumen([string]$Elemento, [string]$Estado, [string]$Detalle = '') {
    $script:Resumen.Add([pscustomobject]@{ Elemento = $Elemento; Estado = $Estado; Detalle = $Detalle })
}

function Test-Aplicar([string]$Mensaje) {
    if ($script:EsSimulacion) { Write-Host "[WHATIF] $Mensaje" -ForegroundColor Yellow; return $false }
    Write-Host "[APLICAR] $Mensaje"
    return $true
}

function Get-TokenAz([ValidateSet('fabric', 'sql', 'storage')][string]$Destino) {
    if ($script:Tokens.ContainsKey($Destino)) { return $script:Tokens[$Destino] }
    $recurso = switch ($Destino) {
        'fabric' { 'https://api.fabric.microsoft.com' }
        'sql' { 'https://database.windows.net' }
        'storage' { 'https://storage.azure.com' }
    }
    $token = az account get-access-token --resource $recurso --query accessToken --output tsv 2>$null
    if (-not $token) {
        throw "No hay token para $recurso con AZURE_CONFIG_DIR=$env:AZURE_CONFIG_DIR. Ejecute 'az login' antes (o indique -AzureConfigDir si usa otro perfil); este script nunca ejecuta az login."
    }
    $script:Tokens[$Destino] = $token.Trim()
    return $script:Tokens[$Destino]
}

function Invoke-Fabric {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)][string]$Metodo,
        [Parameter(Mandatory)][string]$Ruta,
        $Cuerpo = $null,
        [string]$Skill = 'spark-cli',
        [switch]$PermitirError
    )
    $uri = if ($Ruta -like 'http*') { $Ruta } else { "$FabricApi$Ruta" }
    for ($intento = 1; $intento -le 6; $intento++) {
        $cabeceras = @{ Authorization = "Bearer $(Get-TokenAz 'fabric')"; 'x-ms-fabric-skill' = $Skill }
        $parametros = @{ Method = $Metodo; Uri = $uri; Headers = $cabeceras; SkipHttpErrorCheck = $true }
        if ($null -ne $Cuerpo) {
            $parametros.Body = ($Cuerpo | ConvertTo-Json -Depth 30 -Compress)
            $parametros.ContentType = 'application/json'
        }
        $r = Invoke-WebRequest @parametros
        $codigo = [int]$r.StatusCode
        if ($codigo -in 429, 503) {
            $espera = [int](($r.Headers['Retry-After'] | Select-Object -First 1) ?? 10)
            Write-Host "  (reintento ${intento}: HTTP ${codigo}, espera ${espera} s)"
            Start-Sleep -Seconds $espera
            continue
        }
        if ($codigo -eq 202) {
            $ubicacion = [string]($r.Headers['Location'] | Select-Object -First 1)
            $espera = [int](($r.Headers['Retry-After'] | Select-Object -First 1) ?? 5)
            return Wait-Operacion -Ubicacion $ubicacion -EsperaInicial $espera -Skill $Skill
        }
        if ($codigo -ge 400) {
            if ($PermitirError) { return [pscustomobject]@{ _error = $true; codigo = $codigo; cuerpo = $r.Content } }
            throw "Fabric $Metodo $Ruta -> HTTP $codigo : $($r.Content)"
        }
        if ([string]::IsNullOrWhiteSpace($r.Content)) { return $null }
        return ($r.Content | ConvertFrom-Json -Depth 30)
    }
    throw "Fabric $Metodo $Ruta -> demasiados reintentos"
}

function Wait-Operacion([string]$Ubicacion, [int]$EsperaInicial, [string]$Skill) {
    $limite = (Get-Date).AddMinutes($TimeoutPublicacionMin)
    $espera = [Math]::Max(2, $EsperaInicial)
    while ((Get-Date) -lt $limite) {
        Start-Sleep -Seconds $espera
        $estado = Invoke-Fabric -Metodo GET -Ruta $Ubicacion -Skill $Skill
        Write-Host "  operación: $($estado.status)"
        if ($estado.status -eq 'Succeeded') { return $estado }
        if ($estado.status -in 'Failed', 'Cancelled') { throw "Operación $($estado.status): $($estado | ConvertTo-Json -Depth 6 -Compress)" }
        $espera = 5
    }
    throw "Tiempo agotado esperando la operación $Ubicacion"
}

function Get-Elementos([string]$WorkspaceId, [string]$Tipo, [string]$Skill) {
    $ruta = "/workspaces/$WorkspaceId/items?type=$Tipo"
    $todos = @()
    while ($ruta) {
        $pagina = Invoke-Fabric -Metodo GET -Ruta $ruta -Skill $Skill
        $todos += @($pagina.value)
        $ruta = if ($pagina.continuationUri) { $pagina.continuationUri } else { $null }
    }
    return $todos
}

function Find-Elemento([string]$WorkspaceId, [string]$Tipo, [string]$Nombre, [string]$Skill) {
    return Get-Elementos $WorkspaceId $Tipo $Skill | Where-Object { $_.displayName -ceq $Nombre } | Select-Object -First 1
}

# ---------------------------------------------------------------------------------------------
# SQL: lotes separados por GO y ejecución por TDS con token de Entra
# ---------------------------------------------------------------------------------------------
function Split-SqlBatches([string]$Texto) {
    $sinComentarios = { param($lote) ([regex]::Replace([regex]::Replace($lote, '(?s)/\*.*?\*/', ''), '(?m)--.*$', '')).Trim() }
    return @([regex]::Split($Texto, '(?im)^[ \t]*GO[ \t]*(?:--.*)?\r?$') | Where-Object { (& $sinComentarios $_).Length -gt 0 })
}

function Get-SqlScript([string]$Ruta) {
    $sql = Get-Content -LiteralPath $Ruta -Raw -Encoding UTF8
    $destino = '{0}.dbo.{1}_' -f $LakehouseOrigen, $PrefijoTablas.ToLowerInvariant()
    return ($sql -creplace 'AB_Lakehouse\.dbo\.ab_', $destino)
}

function Invoke-SqlScript {
    param(
        [Parameter(Mandatory)][string]$Servidor,
        [Parameter(Mandatory)][string]$BaseDatos,
        [Parameter(Mandatory)][string]$Ruta,
        [switch]$MostrarResultados
    )
    Add-Type -AssemblyName System.Data.SqlClient
    $lotes = Split-SqlBatches (Get-SqlScript $Ruta)
    $conexion = [System.Data.SqlClient.SqlConnection]::new(
        "Server=tcp:$Servidor,1433;Database=$BaseDatos;Encrypt=True;TrustServerCertificate=False;Connection Timeout=60")
    $conexion.AccessToken = Get-TokenAz 'sql'
    $fallas = 0
    try {
        $conexion.Open()
        $numero = 0
        foreach ($lote in $lotes) {
            $numero++
            $comando = $conexion.CreateCommand()
            $comando.CommandText = $lote
            $comando.CommandTimeout = 1800
            try {
                $lector = $comando.ExecuteReader()
                do {
                    if ($lector.FieldCount -gt 0) {
                        $columnas = 0..($lector.FieldCount - 1) | ForEach-Object { $lector.GetName($_) }
                        $filas = [System.Collections.Generic.List[object]]::new()
                        while ($lector.Read()) {
                            $o = [ordered]@{}
                            for ($i = 0; $i -lt $lector.FieldCount; $i++) {
                                $valor = $lector.GetValue($i)
                                $o[$columnas[$i]] = if ($valor -is [System.DBNull]) { $null } else { $valor }
                            }
                            $filas.Add([pscustomobject]$o)
                        }
                        if ($MostrarResultados -and $filas.Count -gt 0) { $filas | Format-Table -AutoSize -Wrap | Out-String -Width 220 | Write-Host }
                        if ($columnas -contains 'estado') { $fallas += @($filas | Where-Object { $_.estado -eq 'FALLA' }).Count }
                    }
                } while ($lector.NextResult())
                $lector.Close()
            }
            catch {
                Write-Host "  lote $numero con error: $($_.Exception.Message)" -ForegroundColor Red
                $fallas++
                if (-not $MostrarResultados) { throw }   # 01/02: detener al primer error; en pruebas seguir
            }
        }
    }
    finally { $conexion.Dispose() }
    return [pscustomobject]@{ Archivo = Split-Path $Ruta -Leaf; Lotes = $lotes.Count; Fallas = $fallas }
}

# ---------------------------------------------------------------------------------------------
# Notebooks y definiciones
# ---------------------------------------------------------------------------------------------
function ConvertTo-Base64([byte[]]$Bytes) { [Convert]::ToBase64String($Bytes) }

function Get-NotebookTexto([string]$Ruta, [hashtable]$Marcadores) {
    $texto = Get-Content -LiteralPath $Ruta -Raw -Encoding UTF8
    foreach ($clave in $Marcadores.Keys) { $texto = $texto.Replace($clave, $Marcadores[$clave]) }
    $null = $texto | ConvertFrom-Json   # debe seguir siendo JSON válido
    return $texto
}

function Set-Notebook([string]$WorkspaceId, [string]$Nombre, [string]$Ruta, [hashtable]$Marcadores, [string]$Descripcion) {
    $existente = Find-Elemento $WorkspaceId 'Notebook' $Nombre 'spark-cli'
    $texto = Get-NotebookTexto $Ruta $Marcadores
    $cargas = @('notebook-content.ipynb', 'artifact.content.ipynb')   # segundo nombre: variante antigua de la documentación
    $accion = if ($existente) { "actualizar notebook $Nombre" } else { "crear notebook $Nombre" }
    if (-not (Test-Aplicar $accion)) { Add-Resumen $Nombre 'simulado' $accion; return $existente }
    foreach ($nombreParte in $cargas) {
        $definicion = @{ format = 'ipynb'; parts = @(@{ path = $nombreParte; payload = (ConvertTo-Base64 ([Text.Encoding]::UTF8.GetBytes($texto))); payloadType = 'InlineBase64' }) }
        $r = if ($existente) {
            Invoke-Fabric -Metodo POST -Ruta "/workspaces/$WorkspaceId/notebooks/$($existente.id)/updateDefinition" -Cuerpo @{ definition = $definicion } -PermitirError
        }
        else {
            Invoke-Fabric -Metodo POST -Ruta "/workspaces/$WorkspaceId/notebooks" -Cuerpo @{ displayName = $Nombre; description = $Descripcion; definition = $definicion } -PermitirError
        }
        if ($r -and $r.PSObject.Properties['_error']) {
            Write-Host "  parte '$nombreParte' rechazada (HTTP $($r.codigo)); se prueba la siguiente" -ForegroundColor Yellow
            continue
        }
        Add-Resumen $Nombre ($existente ? 'actualizado' : 'creado') $nombreParte
        return (Find-Elemento $WorkspaceId 'Notebook' $Nombre 'spark-cli')
    }
    throw "No se pudo subir el notebook $Nombre con ninguno de los nombres de parte"
}

# ---------------------------------------------------------------------------------------------
# OneLake (Files del Lakehouse)
# ---------------------------------------------------------------------------------------------
function Send-OneLakeArchivo([string]$WorkspaceId, [string]$LakehouseId, [string]$RutaRelativa, [byte[]]$Bytes) {
    $base = "https://onelake.dfs.fabric.microsoft.com/$WorkspaceId/$LakehouseId/$RutaRelativa"
    $h = @{ Authorization = "Bearer $(Get-TokenAz 'storage')"; 'x-ms-version' = '2021-06-08' }
    $directorio = ($RutaRelativa -split '/')[0..(($RutaRelativa -split '/').Count - 2)] -join '/'
    $d = Invoke-WebRequest -Method Put -Uri "https://onelake.dfs.fabric.microsoft.com/${WorkspaceId}/${LakehouseId}/${directorio}?resource=directory" -Headers $h -SkipHttpErrorCheck
    if ($d.StatusCode -ge 400 -and $d.StatusCode -ne 409) { throw "OneLake crear directorio $directorio -> HTTP $($d.StatusCode) $($d.Content)" }
    $c = Invoke-WebRequest -Method Put -Uri "${base}?resource=file" -Headers $h -SkipHttpErrorCheck
    if ($c.StatusCode -ge 400) { throw "OneLake crear archivo -> HTTP $($c.StatusCode) $($c.Content)" }
    $a = Invoke-WebRequest -Method Patch -Uri "${base}?action=append&position=0" -Headers $h -Body $Bytes -ContentType 'application/octet-stream' -SkipHttpErrorCheck
    if ($a.StatusCode -ge 400) { throw "OneLake append -> HTTP $($a.StatusCode) $($a.Content)" }
    $f = Invoke-WebRequest -Method Patch -Uri "${base}?action=flush&position=$($Bytes.Length)" -Headers $h -SkipHttpErrorCheck
    if ($f.StatusCode -ge 400) { throw "OneLake flush -> HTTP $($f.StatusCode) $($f.Content)" }
}

# ---------------------------------------------------------------------------------------------
# Environment
# ---------------------------------------------------------------------------------------------
function Wait-EnvironmentPublicado([string]$WorkspaceId, [string]$EnvironmentId) {
    $limite = (Get-Date).AddMinutes($TimeoutPublicacionMin)
    while ((Get-Date) -lt $limite) {
        $e = Invoke-Fabric -Metodo GET -Ruta "/workspaces/$WorkspaceId/environments/$EnvironmentId" -Skill 'spark-cli'
        $estado = $e.properties.publishDetails.state
        Write-Host "  publicación del Environment: $estado"
        if ($estado -eq 'Success') { return }
        if ($estado -in 'Failed', 'Cancelled') { throw "Publicación del Environment: $estado" }
        Start-Sleep -Seconds 20
    }
    throw "Tiempo agotado esperando la publicación del Environment (Full mode: 3 a 6 min según Learn; sesiones +1 a 3 min)"
}

function Set-EnvironmentWheel([string]$WorkspaceId, [string]$EnvironmentId, [string]$RutaWheel) {
    $nombre = Split-Path $RutaWheel -Leaf
    $publicadas = Invoke-Fabric -Metodo GET -Ruta "/workspaces/$WorkspaceId/environments/$EnvironmentId/libraries?beta=false" -Skill 'spark-cli' -PermitirError
    $yaPublicada = $publicadas -and -not $publicadas.PSObject.Properties['_error'] -and (@($publicadas.libraries | Where-Object { $_.name -eq $nombre }).Count -gt 0)
    $estadoActual = (Invoke-Fabric -Metodo GET -Ruta "/workspaces/$WorkspaceId/environments/$EnvironmentId" -Skill 'spark-cli').properties.publishDetails.state
    if ($yaPublicada -and $estadoActual -eq 'Success') {
        Write-Host "El Environment ya tiene $nombre publicado: nada que hacer"
        Add-Resumen $EnvironmentName 'sin cambios' "$nombre ya publicado"
        return
    }
    if (-not (Test-Aplicar "cargar $nombre en el Environment ($EnvironmentModo) y publicar (beta=false)")) { Add-Resumen $EnvironmentName 'simulado' $nombre; return }
    $bytes = [IO.File]::ReadAllBytes($RutaWheel)
    if ($EnvironmentModo -eq 'Definicion') {
        $cuerpo = @{ definition = @{ parts = @(@{ path = "Libraries/CustomLibraries/$nombre"; payload = (ConvertTo-Base64 $bytes); payloadType = 'InlineBase64' }) } }
        $null = Invoke-Fabric -Metodo POST -Ruta "/workspaces/$WorkspaceId/environments/$EnvironmentId/updateDefinition" -Cuerpo $cuerpo -Skill 'spark-cli'
    }
    else {
        $h = @{ Authorization = "Bearer $(Get-TokenAz 'fabric')"; 'x-ms-fabric-skill' = 'spark-cli' }
        $null = Invoke-RestMethod -Method Post -Uri "$FabricApi/workspaces/$WorkspaceId/environments/$EnvironmentId/staging/libraries/$nombre" -Headers $h -Form @{ file = Get-Item -LiteralPath $RutaWheel }
    }
    $null = Invoke-Fabric -Metodo POST -Ruta "/workspaces/$WorkspaceId/environments/$EnvironmentId/staging/publish?beta=false" -Skill 'spark-cli'
    Wait-EnvironmentPublicado $WorkspaceId $EnvironmentId
    Add-Resumen $EnvironmentName 'publicado' $nombre
}

# ---------------------------------------------------------------------------------------------
# Principal
# ---------------------------------------------------------------------------------------------
function Start-Despliegue {
    if ($AzureConfigDir) { $env:AZURE_CONFIG_DIR = $AzureConfigDir }
    if (-not (Get-Command az -ErrorAction SilentlyContinue)) { throw 'No se encontró az en el PATH.' }
    Write-Host "Azure CLI: $(if ($AzureConfigDir) { "perfil $AzureConfigDir" } else { 'sesión actual' }) | modo: $(if ($script:EsSimulacion) { 'SIMULACIÓN (-WhatIf, solo lecturas)' } else { 'APLICAR' })"

    Write-Paso 'Verificaciones previas (solo lectura)'
    $archivos = @{
        Esquemas   = Join-Path $RaizDemo 'warehouse\01_esquemas_tablas.sql'
        Procs      = Join-Path $RaizDemo 'warehouse\02_procedimientos.sql'
        Pruebas    = Join-Path $RaizDemo 'warehouse\03_pruebas.sql'
        Inicial    = Join-Path $RaizDemo 'warehouse\04_estado_inicial.sql'
        Comparar   = Join-Path $RaizDemo 'comparacion\comparacion_tsql.sql'
        Modulo     = Join-Path $RaizDemo 'librerias\B3_modulo_files\fac_utils_lh.py'
        Pipeline   = Join-Path $RaizDemo 'warehouse\pipeline\FAC_PL_Gold_Warehouse.pipeline-content.json'
    }
    $wheel = Get-ChildItem (Join-Path $RaizDemo 'librerias\B2_paquete_environment\dist') -Filter 'fac_utils-*-py3-none-any.whl' -ErrorAction SilentlyContinue | Sort-Object Name | Select-Object -Last 1
    foreach ($k in $archivos.Keys) { if (-not (Test-Path $archivos[$k])) { throw "Falta $($archivos[$k])" } }
    if (-not $wheel) { throw 'Falta el .whl: ejecute python -m build --wheel en librerias\B2_paquete_environment\fac_utils' }

    if ($WorkspaceId) { $ws = Invoke-Fabric -Metodo GET -Ruta "/workspaces/$WorkspaceId" -Skill 'sqldw-cli' }
    else {
        $lista = Invoke-Fabric -Metodo GET -Ruta '/workspaces' -Skill 'sqldw-cli'
        $ws = $lista.value | Where-Object { $_.displayName -ceq $WorkspaceName } | Select-Object -First 1
        if (-not $ws) { throw "No se encontró el workspace '$WorkspaceName'" }
    }
    $wsId = $ws.id
    Write-Host "Workspace: $($ws.displayName) ($wsId)"

    $cap = (Invoke-Fabric -Metodo GET -Ruta '/capacities' -Skill 'sqldw-cli').value | Where-Object { $_.id -eq $ws.capacityId } | Select-Object -First 1
    $estadoCap = if ($cap) { $cap.state } else { 'desconocido' }
    Write-Host "Capacidad del workspace: estado $estadoCap"
    if ($estadoCap -ne 'Active') {
        if ($script:EsSimulacion) { Write-Host 'AVISO: la capacidad no está Activa; con -WhatIf se continúa solo para listar las acciones.' -ForegroundColor Yellow }
        else { throw "La capacidad no está Activa (estado: $estadoCap). Este script nunca la reanuda: solicite la reanudación y vuelva a ejecutar." }
    }

    $ab = Find-Elemento $wsId 'Lakehouse' $LakehouseOrigen 'sqldw-cli'
    $abEndpoint = Find-Elemento $wsId 'SQLEndpoint' $LakehouseOrigen 'sqldw-cli'
    if (-not $ab) { throw "No existe el Lakehouse $LakehouseOrigen en el workspace (el Warehouse debe vivir junto a él)." }
    Write-Host "Lakehouse de origen (solo lectura): $LakehouseOrigen ($($ab.id))"
    if ($RefrescarEndpoint) {
        if ($abEndpoint -and (Test-Aplicar "sincronizar metadatos del SQL analytics endpoint de $LakehouseOrigen")) {
            $null = Invoke-Fabric -Metodo POST -Ruta "/workspaces/$wsId/sqlEndpoints/$($abEndpoint.id)/refreshMetadata" -Cuerpo @{} -Skill 'sqldw-cli'
            Add-Resumen "$LakehouseOrigen (endpoint)" 'metadatos sincronizados'
        }
    }

    # --- Lakehouse FAC_LH_Utils -------------------------------------------------------------------
    Write-Paso "Lakehouse $LakehouseFacName"
    $lhFac = Find-Elemento $wsId 'Lakehouse' $LakehouseFacName 'spark-cli'
    if ($lhFac) { Add-Resumen $LakehouseFacName 'ya existía' $lhFac.id }
    elseif (Test-Aplicar "crear Lakehouse $LakehouseFacName (con esquemas)") {
        $null = Invoke-Fabric -Metodo POST -Ruta "/workspaces/$wsId/lakehouses" -Skill 'spark-cli' -Cuerpo @{ displayName = $LakehouseFacName; description = 'Demo de bibliotecas: bitácora y módulo en Files (taller)'; creationPayload = @{ enableSchemas = $true } }
        $lhFac = Find-Elemento $wsId 'Lakehouse' $LakehouseFacName 'spark-cli'
        Add-Resumen $LakehouseFacName 'creado' $lhFac.id
    }
    else { Add-Resumen $LakehouseFacName 'simulado' 'crear' }

    if ($RefrescarEndpoint -and $lhFac) {
        $epFac = Find-Elemento $wsId 'SQLEndpoint' $LakehouseFacName 'sqldw-cli'
        if ($epFac -and (Test-Aplicar "sincronizar metadatos del SQL analytics endpoint de $LakehouseFacName")) {
            $null = Invoke-Fabric -Metodo POST -Ruta "/workspaces/$wsId/sqlEndpoints/$($epFac.id)/refreshMetadata" -Cuerpo @{} -Skill 'sqldw-cli'
            Add-Resumen "$LakehouseFacName (endpoint)" 'metadatos sincronizados'
        }
    }

    # --- Warehouse FAC_WH_Gold --------------------------------------------------------------------
    Write-Paso "Warehouse $WarehouseName"
    $wh = Find-Elemento $wsId 'Warehouse' $WarehouseName 'sqldw-cli'
    if ($wh) { Add-Resumen $WarehouseName 'ya existía' $wh.id }
    elseif (Test-Aplicar "crear Warehouse $WarehouseName en el mismo workspace que $LakehouseOrigen") {
        $null = Invoke-Fabric -Metodo POST -Ruta "/workspaces/$wsId/warehouses" -Skill 'sqldw-cli' -Cuerpo @{ displayName = $WarehouseName; description = 'Oro del demo: esquemas por dominio y procedimientos T-SQL (taller)' }
        $wh = Find-Elemento $wsId 'Warehouse' $WarehouseName 'sqldw-cli'
        Add-Resumen $WarehouseName 'creado' $wh.id
    }
    else { Add-Resumen $WarehouseName 'simulado' 'crear' }

    $servidor = $null
    if ($wh) {
        for ($i = 0; $i -lt 12 -and -not $servidor; $i++) {
            $servidor = (Invoke-Fabric -Metodo GET -Ruta "/workspaces/$wsId/warehouses/$($wh.id)" -Skill 'sqldw-cli').properties.connectionString
            if (-not $servidor) { Start-Sleep -Seconds 10 }
        }
        Write-Host "Cadena de conexión TDS: $servidor"
    }

    if (-not $OmitirSql) {
        Write-Paso 'SQL: esquemas, tablas y procedimientos'
        if ($servidor -and (Test-Aplicar "ejecutar 01_esquemas_tablas.sql y 02_procedimientos.sql en $WarehouseName")) {
            foreach ($clave in 'Esquemas', 'Procs') {
                $r = Invoke-SqlScript -Servidor $servidor -BaseDatos $WarehouseName -Ruta $archivos[$clave]
                Add-Resumen $r.Archivo 'ejecutado' "$($r.Lotes) lotes"
            }
        }
        elseif (-not $servidor) { Add-Resumen 'SQL 01/02' 'simulado' 'requiere el Warehouse' }
        if ($EjecutarPruebas -and $servidor -and (Test-Aplicar 'ejecutar 03_pruebas.sql')) {
            $r = Invoke-SqlScript -Servidor $servidor -BaseDatos $WarehouseName -Ruta $archivos.Pruebas -MostrarResultados
            Add-Resumen $r.Archivo ($r.Fallas -eq 0 ? 'OK' : 'FALLAS') "$($r.Lotes) lotes; fallas: $($r.Fallas)"
            if ($r.Fallas -gt 0) { $script:HayFallas = $true }
        }
        if ($RestablecerDemo -and $servidor -and (Test-Aplicar 'ejecutar 04_estado_inicial.sql (vaciar bitácora y recargar una vez)')) {
            $r = Invoke-SqlScript -Servidor $servidor -BaseDatos $WarehouseName -Ruta $archivos.Inicial -MostrarResultados
            Add-Resumen $r.Archivo ($r.Fallas -eq 0 ? 'OK' : 'FALLAS') "$($r.Lotes) lotes; fallas: $($r.Fallas)"
            if ($r.Fallas -gt 0) { $script:HayFallas = $true }
        }
        if ($EjecutarComparacion -and $servidor -and (Test-Aplicar 'ejecutar comparacion_tsql.sql')) {
            $r = Invoke-SqlScript -Servidor $servidor -BaseDatos $WarehouseName -Ruta $archivos.Comparar -MostrarResultados
            Add-Resumen $r.Archivo ($r.Fallas -eq 0 ? 'OK' : 'FALLAS') "$($r.Lotes) lotes; fallas: $($r.Fallas)"
            if ($r.Fallas -gt 0) { $script:HayFallas = $true }
        }
    }

    # --- Módulo en Files (variante 3) -------------------------------------------------------------
    if (-not $OmitirModulo) {
        Write-Paso 'Módulo fac_utils_lh.py en Files/libs'
        if ($lhFac -and (Test-Aplicar "subir fac_utils_lh.py a Files/libs de $LakehouseFacName")) {
            Send-OneLakeArchivo $wsId $lhFac.id 'Files/libs/fac_utils_lh.py' ([IO.File]::ReadAllBytes($archivos.Modulo))
            Add-Resumen 'Files/libs/fac_utils_lh.py' 'subido' $LakehouseFacName
        }
        else { Add-Resumen 'Files/libs/fac_utils_lh.py' 'simulado' 'requiere el Lakehouse' }
    }

    # --- Environment (variante 2) -----------------------------------------------------------------
    $env_ = $null
    Write-Paso "Environment $EnvironmentName"
    $env_ = Find-Elemento $wsId 'Environment' $EnvironmentName 'spark-cli'
    if (-not $OmitirEnvironment) {
        if (-not $env_ -and (Test-Aplicar "crear Environment $EnvironmentName")) {
            $null = Invoke-Fabric -Metodo POST -Ruta "/workspaces/$wsId/environments" -Skill 'spark-cli' -Cuerpo @{ displayName = $EnvironmentName; description = 'Paquete fac_utils para el demo de bibliotecas (taller)' }
            $env_ = Find-Elemento $wsId 'Environment' $EnvironmentName 'spark-cli'
            Add-Resumen $EnvironmentName 'creado' $env_.id
        }
        elseif ($env_) { Add-Resumen $EnvironmentName 'ya existía' $env_.id }
        if ($env_) { Set-EnvironmentWheel $wsId $env_.id $wheel.FullName }
        else { Add-Resumen $EnvironmentName 'simulado' 'crear y publicar' }
    }

    # --- Notebooks --------------------------------------------------------------------------------
    if (-not $OmitirNotebooks) {
        Write-Paso 'Notebooks'
        $marcadores = @{
            '{{WORKSPACE_ID}}' = $wsId
            '{{FAC_LH_ID}}'    = ($lhFac ? $lhFac.id : '00000000-0000-0000-0000-000000000000')
            '{{FAC_ENV_ID}}'   = ($env_ ? $env_.id : '00000000-0000-0000-0000-000000000000')
        }
        $notebooks = @(
            @('FAC_NB_Utils', 'librerias\B1_notebook_run\FAC_NB_Utils.ipynb', 'Funciones comunes (variante 1: %run)'),
            @('FAC_NB_Demo_Libreria_A', 'librerias\B1_notebook_run\FAC_NB_Demo_Libreria_A.ipynb', 'Demo A: %run y notebookutils.notebook.run'),
            @('FAC_NB_Demo_Libreria_B', 'librerias\B2_paquete_environment\FAC_NB_Demo_Libreria_B.ipynb', 'Demo B: paquete en Environment'),
            @('FAC_NB_Demo_Libreria_C', 'librerias\B3_modulo_files\FAC_NB_Demo_Libreria_C.ipynb', 'Demo C: módulo en Files'),
            @('FAC_NB_Spark_vs_TSQL', 'comparacion\FAC_NB_Spark_vs_TSQL.ipynb', 'Spark SQL frente a T-SQL')
        )
        foreach ($n in $notebooks) {
            $null = Set-Notebook $wsId $n[0] (Join-Path $RaizDemo $n[1]) $marcadores $n[2]
        }
    }

    # --- Pipeline (opcional) ----------------------------------------------------------------------
    if ($DesplegarPipeline) {
        Write-Paso 'Pipeline FAC_PL_Gold_Warehouse'
        if ($wh -and $servidor) {
            $json = Get-Content -LiteralPath $archivos.Pipeline -Raw -Encoding UTF8
            $json = $json.Replace('{{WORKSPACE_ID}}', $wsId).Replace('{{WAREHOUSE_ID}}', $wh.id).Replace('{{WAREHOUSE_NAME}}', $WarehouseName).Replace('{{WAREHOUSE_ENDPOINT}}', $servidor)
            $objeto = $json | ConvertFrom-Json -Depth 30
            $objeto.PSObject.Properties.Remove('_comentario')
            $contenido = $objeto | ConvertTo-Json -Depth 30 -Compress
            $definicion = @{ parts = @(@{ path = 'pipeline-content.json'; payload = (ConvertTo-Base64 ([Text.Encoding]::UTF8.GetBytes($contenido))); payloadType = 'InlineBase64' }) }
            $pl = Find-Elemento $wsId 'DataPipeline' 'FAC_PL_Gold_Warehouse' 'spark-cli'
            if (Test-Aplicar ($pl ? 'actualizar pipeline FAC_PL_Gold_Warehouse' : 'crear pipeline FAC_PL_Gold_Warehouse')) {
                if ($pl) { $null = Invoke-Fabric -Metodo POST -Ruta "/workspaces/$wsId/dataPipelines/$($pl.id)/updateDefinition" -Cuerpo @{ definition = $definicion } -Skill 'spark-cli' }
                else { $null = Invoke-Fabric -Metodo POST -Ruta "/workspaces/$wsId/dataPipelines" -Cuerpo @{ displayName = 'FAC_PL_Gold_Warehouse'; definition = $definicion } -Skill 'spark-cli' }
                Add-Resumen 'FAC_PL_Gold_Warehouse' ($pl ? 'actualizado' : 'creado')
            }
        }
        else { Add-Resumen 'FAC_PL_Gold_Warehouse' 'simulado' 'requiere el Warehouse' }
    }

    Write-Paso 'Resumen'
    $script:Resumen | Format-Table -AutoSize -Wrap | Out-String -Width 200 | Write-Host
    if (-not $script:EsSimulacion) {
        $registro = [ordered]@{
            fecha_utc = (Get-Date).ToUniversalTime().ToString('s'); workspace_id = $wsId
            lakehouse_fac = $lhFac.id; warehouse = $wh.id; environment = $env_.id; elementos = $script:Resumen
        }
        $registro | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath (Join-Path ([IO.Path]::GetTempPath()) 'fac-ultimo-despliegue.json') -Encoding UTF8
    }
    if ($script:HayFallas) { exit 1 }
}

# Al ejecutar el archivo se despliega; al cargarlo con punto (. .\deploy.ps1) solo se definen las funciones.
if ($MyInvocation.InvocationName -ne '.') { Start-Despliegue }
