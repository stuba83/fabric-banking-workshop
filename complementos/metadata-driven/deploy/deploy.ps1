#Requires -Version 7.0
<#
.SYNOPSIS
    Despliega de forma idempotente la demo de ingesta metadata-driven (elementos FAC_*) en un workspace de Fabric.

.DESCRIPTION
    Crea o actualiza, por REST y resolviendo los IDs por nombre:
      - cuatro notebooks (ipynb -> definición base64, con el Lakehouse predeterminado enlazado en los metadatos):
        FAC_NB_Preparar_Control, FAC_NB_Carga_Generica, FAC_NB_Leer_Catalogo, FAC_NB_Resumen_Bitacora
      - el pipeline FAC_PL_Ingesta_Metadata (variante 'Lookup' = principal, 'Notebook' = alternativa),
        sustituyendo los marcadores {{WORKSPACE_ID}}, {{LAKEHOUSE_ID}}, {{NOTEBOOK_ID_*}}, {{ESQUEMA}}, {{ESQUEMA_LOOKUP}}.
    Nunca toca elementos que no empiecen por FAC_ (por ejemplo, los AB_*): solo crea/actualiza los suyos.
    Con -Run lanza el pipeline y espera el resultado; con -RunPreparar lanza FAC_NB_Preparar_Control.
    Con -WhatIf muestra qué haría sin crear, actualizar ni ejecutar nada.

    Autenticación: usa la sesión actual de Azure CLI (quien despliega ya ejecutó 'az login'). Si necesita otro
    perfil de Azure CLI, -AzureConfigDir fija AZURE_CONFIG_DIR solo mientras corre el script.
    Este script nunca ejecuta 'az login' ni 'az account set': la sesión debe estar autenticada de antemano.
    Todas las llamadas a api.fabric.microsoft.com llevan la cabecera x-ms-fabric-skill (ver -SkillHeader).

.PARAMETER WorkspaceName
    OBLIGATORIO. Nombre del workspace donde se despliega (se resuelve a ID). Lo elige quien despliega; en el
    laboratorio, un nombre con su prefijo propio. Con -WorkspaceId el ID se toma directamente.
.PARAMETER WorkspaceId
    Opcional. GUID del workspace; evita la búsqueda por nombre (por ejemplo, si hay nombres repetidos).
.PARAMETER AzureConfigDir
    Opcional. Carpeta de configuración de Azure CLI (AZURE_CONFIG_DIR) solo si se necesita un perfil distinto del
    predeterminado. Si se omite, se usa la sesión actual de Azure CLI.
.PARAMETER LakehouseName
    Lakehouse que se enlaza como predeterminado de los notebooks y que usa el Lookup (ya debe existir).
.PARAMETER Variante
    Lookup (principal) o Notebook (alternativa con FAC_NB_Leer_Catalogo). Ambas se despliegan con el mismo nombre de pipeline.
.PARAMETER Esquema
    auto (detecta con la propiedad defaultSchema del Lakehouse: 'fac' si tiene esquemas, 'ninguno' si no), 'ninguno' o un nombre.
.PARAMETER SkipDeploy
    No crea ni actualiza nada: solo resuelve IDs y, si se piden, ejecuta -RunPreparar / -Run.
.PARAMETER SoloNotebooks
    Despliega solo estos notebooks FAC_NB_* (acelera la iteración tras un cambio).
.PARAMETER SinPipeline
    No despliega el pipeline.
.PARAMETER RunPreparar
    Ejecuta FAC_NB_Preparar_Control como job on-demand con -Accion (preparar | incremento | reiniciar) y espera.
.PARAMETER RunNotebook
    Nombre de otro notebook FAC_NB_* que se ejecuta como job on-demand (con -NotebookParametros) y cuyo exitValue se muestra.
.PARAMETER Run
    Ejecuta el pipeline como job on-demand y espera. -RunParametros permite pasar forzar_completa y filtro_tabla.

.EXAMPLE
    ./deploy.ps1 -WorkspaceName 'MI-WORKSPACE' -WhatIf
.EXAMPLE
    ./deploy.ps1 -WorkspaceName 'MI-WORKSPACE'
.EXAMPLE
    ./deploy.ps1 -WorkspaceName 'MI-WORKSPACE' -SkipDeploy -RunPreparar -Accion preparar
.EXAMPLE
    ./deploy.ps1 -WorkspaceName 'MI-WORKSPACE' -SkipDeploy -Run -RunParametros @{ forzar_completa = $false; filtro_tabla = '' }
#>
[CmdletBinding(SupportsShouldProcess = $true, ConfirmImpact = 'Medium')]
param(
    [Parameter(Mandatory)][ValidateNotNullOrEmpty()][string]$WorkspaceName,
    [string]$WorkspaceId,
    [string]$LakehouseName = 'AB_Lakehouse',
    [ValidateSet('Lookup', 'Notebook')][string]$Variante = 'Lookup',
    [string]$Esquema = 'auto',
    [string]$FolderName,
    [string]$AzureConfigDir,
    [string]$SkillHeader = 'spark-cli',
    [switch]$SkipDeploy,
    [string[]]$SoloNotebooks,
    [switch]$SinPipeline,
    [switch]$RunPreparar,
    [string]$RunNotebook,
    [hashtable]$NotebookParametros,
    [ValidateSet('preparar', 'incremento', 'reiniciar')][string]$Accion = 'preparar',
    [ValidateRange(1, 20)][int]$NumeroIncremento = 1,
    [switch]$Run,
    [hashtable]$RunParametros,
    [ValidateRange(1, 240)][int]$TimeoutMinutos = 45,
    [ValidateRange(3, 120)][int]$PollSegundos = 8
)

$ErrorActionPreference = 'Stop'
$ApiBase = 'https://api.fabric.microsoft.com/v1'
$Raiz = Split-Path -Parent $PSScriptRoot
$GuidVacio = '00000000-0000-0000-0000-000000000000'
$Notebooks = @('FAC_NB_Preparar_Control', 'FAC_NB_Carga_Generica', 'FAC_NB_Leer_Catalogo', 'FAC_NB_Resumen_Bitacora')
$NombrePipeline = 'FAC_PL_Ingesta_Metadata'
$script:Token = $null

function Write-Paso([string]$Texto) { Write-Host "`n==> $Texto" -ForegroundColor Cyan }
function Write-Info([string]$Texto) { Write-Host "    $Texto" }

function Get-FabricToken {
    # Solo lectura de la sesión actual de Azure CLI: jamás se ejecuta 'az login' ni 'az account set' desde aquí.
    $t = & az account get-access-token --resource https://api.fabric.microsoft.com --query accessToken -o tsv --only-show-errors 2>$null
    if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($t)) {
        throw "No se pudo obtener un token de Azure CLI. Ejecute 'az login' antes (este script no inicia sesión) o indique -AzureConfigDir si usa otro perfil."
    }
    return $t.Trim()
}

function ConvertFrom-FabricContent($Respuesta) {
    if ([string]::IsNullOrWhiteSpace($Respuesta.Content)) { return $null }
    try { return $Respuesta.Content | ConvertFrom-Json -Depth 30 } catch { return $null }
}

function Get-Cabecera($Respuesta, [string]$Nombre) {
    $v = $null
    if ($Respuesta.Headers.TryGetValue($Nombre, [ref]$v)) { return @($v)[0] }
    return $null
}

function Invoke-Fabric {
    param(
        [Parameter(Mandatory)][ValidateSet('GET', 'POST')][string]$Method,
        [Parameter(Mandatory)][string]$Uri,
        $Body = $null,
        [switch]$NoThrow
    )
    for ($intento = 1; $intento -le 6; $intento++) {
        $p = @{
            Method             = $Method
            Uri                = $Uri
            Headers            = @{ Authorization = "Bearer $script:Token"; 'x-ms-fabric-skill' = $SkillHeader }
            SkipHttpErrorCheck = $true
            ContentType        = 'application/json'
        }
        if ($null -ne $Body) { $p.Body = ($Body -is [string]) ? $Body : ($Body | ConvertTo-Json -Depth 30 -Compress) }
        elseif ($Method -eq 'POST') { $p.Body = '{}' }

        $resp = Invoke-WebRequest @p
        $estado = [int]$resp.StatusCode
        if ($estado -eq 401 -and $intento -eq 1) { $script:Token = Get-FabricToken; continue }
        if (($estado -in 429, 503) -and $intento -lt 6) {
            $espera = [int](Get-Cabecera $resp 'Retry-After'); if ($espera -lt 1) { $espera = 10 }
            Write-Info "Respuesta $estado; reintento en $espera s (intento $intento)"
            Start-Sleep -Seconds $espera
            continue
        }
        $r = [pscustomobject]@{ Status = $estado; Headers = $resp.Headers; Json = (ConvertFrom-FabricContent $resp); Raw = $resp.Content }
        if ($estado -ge 400 -and -not $NoThrow) { throw (Format-FabricError $r $Method $Uri) }
        return $r
    }
}

function Format-FabricError($R, [string]$Method = '', [string]$Uri = '') {
    $codigo = $R.Json.errorCode; $mensaje = $R.Json.message
    $detalle = if ($codigo -or $mensaje) { "$codigo - $mensaje" } else { ([string]$R.Raw).Substring(0, [Math]::Min(300, ([string]$R.Raw).Length)) }
    return "Fabric devolvió HTTP $($R.Status) en $Method $Uri : $detalle"
}

function Get-Paged([string]$Url) {
    $todo = @(); $siguiente = $Url
    while ($siguiente) {
        $r = Invoke-Fabric GET $siguiente
        if ($r.Json.value) { $todo += @($r.Json.value) }
        $siguiente = if ($r.Json.continuationUri) { $r.Json.continuationUri } else { $null }
    }
    return $todo
}

function Wait-FabricOperation($Respuesta) {
    $url = Get-Cabecera $Respuesta 'Location'
    if (-not $url) { throw 'La operación asíncrona no devolvió cabecera Location.' }
    $limite = (Get-Date).AddMinutes(15)
    $espera = [int](Get-Cabecera $Respuesta 'Retry-After'); if ($espera -lt 2) { $espera = 3 }
    while ((Get-Date) -lt $limite) {
        Start-Sleep -Seconds $espera
        $r = Invoke-Fabric GET $url
        $estado = $r.Json.status
        if ($estado -eq 'Succeeded') { return $r }
        if ($estado -eq 'Failed') { throw "La operación falló: $($r.Json.error.errorCode) - $($r.Json.error.message)" }
        $espera = [int](Get-Cabecera $r 'Retry-After'); if ($espera -lt 2) { $espera = 5 }
    }
    throw 'Tiempo agotado esperando la operación de Fabric.'
}

function Get-Items { Get-Paged "$ApiBase/workspaces/$script:WorkspaceId/items" }

function Find-Item($Items, [string]$Tipo, [string]$Nombre) {
    $m = @($Items | Where-Object { $_.type -eq $Tipo -and $_.displayName -eq $Nombre })
    if ($m.Count -gt 1) { throw "Hay $($m.Count) elementos $Tipo llamados '$Nombre'; resuelve la ambigüedad a mano." }
    if ($m.Count -eq 1) { return $m[0] }
    return $null
}

function ConvertTo-Base64Utf8([string]$Texto) { [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($Texto)) }

function New-NotebookJson {
    param([Parameter(Mandatory)][string]$Ruta, [Parameter(Mandatory)][string]$LakehouseId)
    $nb = [System.Text.Json.Nodes.JsonNode]::Parse([IO.File]::ReadAllText($Ruta, [Text.UTF8Encoding]::new($false)))
    $dependencias = @{
        lakehouse = @{
            default_lakehouse              = $LakehouseId
            default_lakehouse_name         = $LakehouseName
            default_lakehouse_workspace_id = $script:WorkspaceId
            known_lakehouses               = @(@{ id = $LakehouseId })
        }
    } | ConvertTo-Json -Depth 6 -Compress
    $meta = $nb['metadata'].AsObject()
    [void]$meta.Remove('dependencies')
    $meta.Add('dependencies', [System.Text.Json.Nodes.JsonNode]::Parse($dependencias))
    return $nb.ToJsonString()
}

function Remove-SchemaNinguno($Nodo) {
    # El Lookup solo lleva 'schema' en un Lakehouse con esquemas; si es 'ninguno' se quita la propiedad de texto
    # (el 'schema': [] del dataset, que es un arreglo, no se toca).
    if ($Nodo -is [System.Text.Json.Nodes.JsonObject]) {
        $quitar = [System.Collections.Generic.List[string]]::new()
        $hijos = [System.Collections.Generic.List[object]]::new()
        foreach ($kv in $Nodo.GetEnumerator()) {
            if ($kv.Key -eq 'schema' -and $kv.Value -is [System.Text.Json.Nodes.JsonValue] -and $kv.Value.ToString() -eq 'ninguno') { $quitar.Add($kv.Key) }
            elseif ($null -ne $kv.Value) { $hijos.Add($kv.Value) }
        }
        foreach ($k in $quitar) { [void]$Nodo.Remove($k) }
        foreach ($h in $hijos) { Remove-SchemaNinguno $h }
    }
    elseif ($Nodo -is [System.Text.Json.Nodes.JsonArray]) {
        foreach ($h in @($Nodo)) { if ($null -ne $h) { Remove-SchemaNinguno $h } }
    }
}

function New-PipelineJson {
    param([Parameter(Mandatory)][string]$Plantilla, [Parameter(Mandatory)][hashtable]$Valores)
    $texto = [IO.File]::ReadAllText($Plantilla, [Text.UTF8Encoding]::new($false))
    foreach ($k in $Valores.Keys) { $texto = $texto.Replace('{{' + $k + '}}', [string]$Valores[$k]) }
    $restantes = [regex]::Matches($texto, '\{\{[A-Z_]+\}\}') | ForEach-Object Value | Sort-Object -Unique
    if ($restantes) { throw "Quedaron marcadores sin sustituir en $Plantilla : $($restantes -join ', ')" }
    $nodo = [System.Text.Json.Nodes.JsonNode]::Parse($texto)
    Remove-SchemaNinguno $nodo
    return $nodo.ToJsonString()
}

function Publish-Item {
    param(
        [Parameter(Mandatory)][string]$Tipo,
        [Parameter(Mandatory)][string]$Nombre,
        [Parameter(Mandatory)][string]$Contenido,
        [Parameter(Mandatory)][string[]]$RutasParte,
        [string]$Formato,
        [string]$Descripcion = 'Demo didáctica de ingesta metadata-driven (datos sintéticos)',
        $Existente,
        $FolderId
    )
    $accion = if ($Existente) { 'Actualizar definición' } else { 'Crear' }
    if (-not $PSCmdlet.ShouldProcess("$Tipo '$Nombre' en el workspace $script:WorkspaceId", $accion)) { return $Existente.id }
    $payload = ConvertTo-Base64Utf8 $Contenido
    for ($i = 0; $i -lt $RutasParte.Count; $i++) {
        $def = @{ parts = @(@{ path = $RutasParte[$i]; payload = $payload; payloadType = 'InlineBase64' }) }
        if ($Formato) { $def.format = $Formato }
        if ($Existente) {
            $uri = "$ApiBase/workspaces/$script:WorkspaceId/items/$($Existente.id)/updateDefinition"
            $cuerpo = @{ definition = $def }
        }
        else {
            $uri = "$ApiBase/workspaces/$script:WorkspaceId/items"
            $cuerpo = @{ displayName = $Nombre; type = $Tipo; description = $Descripcion; definition = $def }
            if ($FolderId) { $cuerpo.folderId = $FolderId }
        }
        $r = Invoke-Fabric POST $uri $cuerpo -NoThrow
        if ($r.Status -eq 202) { [void](Wait-FabricOperation $r); break }
        if ($r.Status -in 200, 201) { break }
        if ($r.Status -eq 400 -and $i -lt $RutasParte.Count - 1) {
            Write-Info "HTTP 400 con la parte '$($RutasParte[$i])' ($($r.Json.errorCode)); pruebo '$($RutasParte[$i + 1])'"
            continue
        }
        throw (Format-FabricError $r 'POST' $uri)
    }
    Write-Info "$accion : $Tipo '$Nombre' OK"
    return $true
}

function Resolve-FolderId {
    if (-not $FolderName) { return $null }
    $f = Get-Paged "$ApiBase/workspaces/$script:WorkspaceId/folders" | Where-Object { $_.displayName -eq $FolderName } | Select-Object -First 1
    if ($f) { return $f.id }
    if ($PSCmdlet.ShouldProcess("carpeta '$FolderName'", 'Crear')) {
        return (Invoke-Fabric POST "$ApiBase/workspaces/$script:WorkspaceId/folders" @{ displayName = $FolderName }).Json.id
    }
    return $null
}

function Start-FabricJob {
    # Cada intento = una forma distinta de URL/cuerpo; se prueban en orden hasta que la API acepta el job (202).
    param([Parameter(Mandatory)][object[]]$Intentos)
    $ultimo = $null; $ultimaUri = ''
    foreach ($i in $Intentos) {
        $r = Invoke-Fabric POST $i.Uri $i.Body -NoThrow
        if ($r.Status -eq 202) { return (Get-Cabecera $r 'Location') }
        Write-Info "El job no se aceptó con '$($i.Nombre)' (HTTP $($r.Status) $($r.Json.errorCode)); pruebo la siguiente forma."
        $ultimo = $r; $ultimaUri = $i.Uri
    }
    throw (Format-FabricError $ultimo 'POST' $ultimaUri)
}
function Wait-FabricJob([string]$Url) {
    $limite = (Get-Date).AddMinutes($TimeoutMinutos)
    $terminales = 'Completed', 'Failed', 'Cancelled', 'Deduped'
    while ((Get-Date) -lt $limite) {
        $r = Invoke-Fabric GET $Url
        $estado = $r.Json.status
        Write-Info ("{0:HH:mm:ss}  estado = {1}" -f (Get-Date), $estado)
        if ($estado -in $terminales) { return $r.Json }
        Start-Sleep -Seconds $PollSegundos   # no se respeta Retry-After (suele ser 60 s): alargaría la espera sin necesidad
    }
    throw "Tiempo agotado ($TimeoutMinutos min) esperando el job $Url"
}

function Show-ActivityRuns($Job) {
    # Mejor esfuerzo: muestra cada actividad con su estado y el exitValue del notebook (JSON de resultado).
    try {
        $desde = ([datetime]$Job.startTimeUtc).AddHours(-1).ToString('o'); $hasta = ([datetime]$Job.endTimeUtc).AddHours(1).ToString('o')
        $cuerpo = @{ filters = @(); orderBy = @(@{ orderBy = 'ActivityRunStart'; order = 'ASC' }); lastUpdatedAfter = $desde; lastUpdatedBefore = $hasta }
        $r = Invoke-Fabric POST "$ApiBase/workspaces/$script:WorkspaceId/datapipelines/pipelineruns/$($Job.id)/queryactivityruns" $cuerpo -NoThrow
        if ($r.Status -ne 200) { Write-Warning "No se pudieron leer las actividades (HTTP $($r.Status))."; return }
        foreach ($a in @($r.Json.value)) {
            $tabla = $a.input.parameters.tabla.value ?? $a.input.parameters.tabla
            $exit = $a.output.result.exitValue
            $texto = if ($exit) { [string]$exit } elseif ($a.error.message) { "ERROR: $($a.error.message)" } else { '' }
            $color = if ($a.status -eq 'Succeeded') { 'Green' } elseif ($a.status -eq 'Failed') { 'Red' } else { 'Gray' }
            Write-Host ("  [{0}] {1}{2}" -f $a.status, $a.activityName, $(if ($tabla) { " ($tabla)" } else { '' })) -ForegroundColor $color
            if ($texto) { Write-Host ("      " + $texto.Substring(0, [Math]::Min(900, $texto.Length))) }
        }
    }
    catch { Write-Warning "No se pudo mostrar el detalle de actividades: $($_.Exception.Message)" }
}

function ConvertTo-ParametrosJob {
    # Devuelve las dos formas de parámetros que acepta la API de jobs: Lista = parameters[] (name/value/type)
    # y Objeto = executionData.parameters (valores simples para pipelines; {value,type} para notebooks).
    param([Parameter(Mandatory)][hashtable]$Valores, [switch]$Notebook)
    $lista = @{
        parameters = @(foreach ($k in $Valores.Keys) {
                $v = $Valores[$k]
                $tipo = if ($v -is [bool]) { 'Boolean' } elseif ($v -is [int] -or $v -is [long]) { 'Integer' } elseif ($v -is [double]) { 'Number' } else { 'Text' }
                @{ name = $k; value = $v; type = $tipo }
            })
    }
    if ($Notebook) {
        $anidados = @{}
        foreach ($k in $Valores.Keys) {
            $v = $Valores[$k]
            $tipo = if ($v -is [bool]) { 'bool' } elseif ($v -is [int] -or $v -is [long]) { 'int' } elseif ($v -is [double]) { 'float' } else { 'string' }
            $anidados[$k] = @{ value = $v; type = $tipo }
        }
        $objeto = @{ executionData = @{ parameters = $anidados } }
    }
    else { $objeto = @{ executionData = @{ parameters = $Valores } } }
    return @{ Lista = $lista; Objeto = $objeto }
}
function Invoke-NotebookJob {
    # Lanza un notebook como job on-demand, espera el resultado y muestra su exitValue. Devuelve 0 si Completed.
    param([Parameter(Mandatory)][string]$Nombre, [Parameter(Mandatory)][hashtable]$Valores, [string]$IdNotebook)
    if (-not $IdNotebook) { throw "El notebook $Nombre no existe todavía." }
    $formas = ConvertTo-ParametrosJob -Valores $Valores -Notebook
    $base = "$ApiBase/workspaces/$script:WorkspaceId"
    $url = Start-FabricJob -Intentos @(
        @{ Nombre = 'notebooks/jobs/execute con parameters[]'; Uri = "$base/notebooks/$IdNotebook/jobs/execute/instances?beta=false"; Body = $formas.Lista },
        @{ Nombre = 'items/jobs con executionData.parameters'; Uri = "$base/items/$IdNotebook/jobs/instances?jobType=RunNotebook"; Body = $formas.Objeto },
        @{ Nombre = 'items/jobs con parameters[]'; Uri = "$base/items/$IdNotebook/jobs/instances?jobType=RunNotebook"; Body = $formas.Lista }
    )
    $job = Wait-FabricJob $url
    Write-Info "Resultado: $($job.status) $($job.failureReason.message)"
    $salida = $job.exitValue
    if (-not $salida -and $job.status -eq 'Completed') {
        $d = Invoke-Fabric GET "$base/notebooks/$IdNotebook/jobs/execute/instances/$($job.id)?beta=true" -NoThrow
        if ($d.Status -eq 200) { $salida = if ($d.Json.properties.exitValue) { $d.Json.properties.exitValue } else { $d.Json.exitValue } }
    }
    if ($salida) { Write-Host "    exitValue: $salida" }
    if ($job.status -ne 'Completed') { return 1 }
    return 0
}

# ======================================================================================================
# Programa principal. La guarda permite cargar las funciones con dot-sourcing (pruebas) sin ejecutarlo.
# ======================================================================================================
function Invoke-Main {
    if ($Esquema -notmatch '^(auto|ninguno|[A-Za-z][A-Za-z0-9_]{0,63})$') { throw "-Esquema debe ser auto, ninguno o un identificador simple; se recibió '$Esquema'." }

    if ($AzureConfigDir) { $env:AZURE_CONFIG_DIR = $AzureConfigDir }
    Write-Paso ('Autenticación (' + $(if ($AzureConfigDir) { "perfil de Azure CLI en $AzureConfigDir" } else { 'sesión actual de Azure CLI' }) + ')')
    $script:Token = Get-FabricToken
    Write-Info 'Token obtenido (no se muestra).'

    Write-Paso 'Resolución de IDs por nombre'
    $script:WorkspaceId = $WorkspaceId
    if (-not $script:WorkspaceId) {
        $ws = @(Get-Paged "$ApiBase/workspaces" | Where-Object { $_.displayName -eq $WorkspaceName })
        if ($ws.Count -ne 1) { throw "Se esperaba un workspace llamado '$WorkspaceName' y se encontraron $($ws.Count)." }
        $script:WorkspaceId = $ws[0].id
    }
    Write-Info "Workspace: $WorkspaceName ($script:WorkspaceId)"
    $items = Get-Items
    $lh = Find-Item $items 'Lakehouse' $LakehouseName
    if (-not $lh) { throw "No existe el Lakehouse '$LakehouseName' en el workspace." }
    Write-Info "Lakehouse: $LakehouseName ($($lh.id))"

    # ¿Esquemas habilitados? La propiedad defaultSchema solo aparece en Lakehouses con esquemas.
    $esquemaDemo = $Esquema
    if ($Esquema -eq 'auto') {
        $detalle = Invoke-Fabric GET "$ApiBase/workspaces/$script:WorkspaceId/lakehouses/$($lh.id)" -NoThrow
        if ($detalle.Status -eq 200) { $esquemaDemo = if ($detalle.Json.properties.defaultSchema) { 'fac' } else { 'ninguno' } }
        elseif ($WhatIfPreference) { Write-Warning "No se pudo leer el Lakehouse (HTTP $($detalle.Status): $($detalle.Json.errorCode)); en -WhatIf se supone esquema 'fac'."; $esquemaDemo = 'fac' }
        else { throw "No se pudo leer las propiedades del Lakehouse (HTTP $($detalle.Status): $($detalle.Json.errorCode)). ¿Capacidad activa? Indica -Esquema fac | ninguno para continuar." }
    }
    Write-Info "Esquema de las tablas fac_*: $esquemaDemo"

    $ids = @{}
    foreach ($n in $Notebooks) { $ids[$n] = (Find-Item $items 'Notebook' $n).id }

    if (-not $SkipDeploy) {
        Write-Paso 'Notebooks (ipynb -> definición base64, con el Lakehouse enlazado)'
        $folderId = Resolve-FolderId
        $aPublicar = if ($SoloNotebooks) { @($SoloNotebooks | ForEach-Object { $_ -split ',' } | ForEach-Object { $_.Trim() } | Where-Object { $_ }) } else { $Notebooks }
        foreach ($n in $aPublicar) {
            if ($Notebooks -notcontains $n) { throw "-SoloNotebooks admite solo: $($Notebooks -join ', ')" }
            $ruta = Join-Path $Raiz "$n.ipynb"
            if (-not (Test-Path $ruta)) { throw "Falta $ruta" }
            $contenido = New-NotebookJson -Ruta $ruta -LakehouseId $lh.id
            $existente = Find-Item $items 'Notebook' $n
            [void](Publish-Item -Tipo Notebook -Nombre $n -Contenido $contenido -Formato ipynb -RutasParte 'notebook-content.ipynb', 'artifact.content.ipynb' -Existente $existente -FolderId $folderId)
        }
        $items = Get-Items
        foreach ($n in $Notebooks) { $ids[$n] = (Find-Item $items 'Notebook' $n).id }

        if (-not $SinPipeline) {
            Write-Paso "Pipeline $NombrePipeline (variante $Variante)"
            $archivoPl = if ($Variante -eq 'Lookup') { 'FAC_PL_Ingesta_Metadata.json' } else { 'FAC_PL_Ingesta_Metadata.alt-notebook.json' }
            $plantilla = Join-Path (Join-Path $Raiz 'pipeline') $archivoPl
            $o = { param($n) if ($ids[$n]) { $ids[$n] } else { $GuidVacio } }
            $valores = @{
                WORKSPACE_ID                  = $script:WorkspaceId
                LAKEHOUSE_ID                  = $lh.id
                NOTEBOOK_ID_CARGA_GENERICA    = (& $o 'FAC_NB_Carga_Generica')
                NOTEBOOK_ID_RESUMEN_BITACORA  = (& $o 'FAC_NB_Resumen_Bitacora')
                NOTEBOOK_ID_LEER_CATALOGO     = (& $o 'FAC_NB_Leer_Catalogo')
                ESQUEMA                       = $esquemaDemo
                ESQUEMA_LOOKUP                = $esquemaDemo
            }
            $contenidoPl = New-PipelineJson -Plantilla $plantilla -Valores $valores
            $existentePl = Find-Item $items 'DataPipeline' $NombrePipeline
            [void](Publish-Item -Tipo DataPipeline -Nombre $NombrePipeline -Contenido $contenidoPl -RutasParte 'pipeline-content.json' -Existente $existentePl -FolderId $folderId)
        }
        $items = Get-Items
    }
    $idPipeline = (Find-Item $items 'DataPipeline' $NombrePipeline).id

    $codigoSalida = 0
    if ($RunPreparar -and $codigoSalida -eq 0) {
        Write-Paso "Ejecutando FAC_NB_Preparar_Control (accion = $Accion)"
        $idNb = $ids['FAC_NB_Preparar_Control']
        if (-not $idNb -and -not $WhatIfPreference) { throw 'FAC_NB_Preparar_Control no existe todavía.' }
        if ($PSCmdlet.ShouldProcess('FAC_NB_Preparar_Control', "Ejecutar job RunNotebook (accion=$Accion)")) {
            $codigoSalida = Invoke-NotebookJob -Nombre 'FAC_NB_Preparar_Control' -IdNotebook $idNb -Valores @{ accion = $Accion; destino = $esquemaDemo; numero_incremento = $NumeroIncremento }
        }
    }
    if ($RunNotebook -and $codigoSalida -eq 0) {
        if ($Notebooks -notcontains $RunNotebook) { throw "-RunNotebook debe ser uno de: $($Notebooks -join ', ')" }
        Write-Paso "Ejecutando $RunNotebook"
        $valores = @{ destino = $esquemaDemo }
        if ($NotebookParametros) { foreach ($k in @($NotebookParametros.Keys)) { $valores[$k] = $NotebookParametros[$k] } }
        if ($PSCmdlet.ShouldProcess($RunNotebook, 'Ejecutar job RunNotebook')) {
            $codigoSalida = Invoke-NotebookJob -Nombre $RunNotebook -IdNotebook $ids[$RunNotebook] -Valores $valores
        }
    }
    if ($Run -and $codigoSalida -eq 0) {
        Write-Paso "Ejecutando el pipeline $NombrePipeline"
        if (-not $idPipeline -and -not $WhatIfPreference) { throw "El pipeline $NombrePipeline no existe todavía." }
        if ($PSCmdlet.ShouldProcess($NombrePipeline, 'Ejecutar job Pipeline')) {
            $uriJob = "$ApiBase/workspaces/$script:WorkspaceId/items/$idPipeline/jobs/instances?jobType=Pipeline"
            if ($RunParametros -and $RunParametros.Count -gt 0) {
                $formas = ConvertTo-ParametrosJob -Valores $RunParametros
                $intentos = @(
                    @{ Nombre = 'executionData.parameters'; Uri = $uriJob; Body = $formas.Objeto },
                    @{ Nombre = 'parameters[]'; Uri = $uriJob; Body = $formas.Lista }
                )
            }
            else { $intentos = @(@{ Nombre = 'sin parámetros'; Uri = $uriJob; Body = @{} }) }
            $url = Start-FabricJob -Intentos $intentos
            $job = Wait-FabricJob $url
            Write-Info "Resultado: $($job.status) $($job.failureReason.message)"
            Show-ActivityRuns $job
            if ($job.status -ne 'Completed') { $codigoSalida = 1 }
        }
    }
    Write-Paso 'Listo'
    $script:CodigoSalida = $codigoSalida
}

if ($MyInvocation.InvocationName -ne '.') {
    Invoke-Main
    exit $script:CodigoSalida
}
