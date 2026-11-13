<#
.SYNOPSIS
    Ejecuta un notebook FAC_* como trabajo (RunNotebook) y espera el resultado. Solo para elementos FAC_*.
.EXAMPLE
    pwsh -File .\herramientas\ejecutar_notebook.ps1 -WorkspaceName 'MI-WORKSPACE' -Nombre FAC_NB_Demo_Libreria_A
#>
#Requires -Version 7.0
[CmdletBinding()]
param(
    [Parameter(Mandatory)][ValidatePattern('^FAC_NB_')][string]$Nombre,
    [Parameter(Mandatory)][ValidateNotNullOrEmpty()][string]$WorkspaceName,
    [string]$WorkspaceId = '',
    [string]$AzureConfigDir = '',
    [hashtable]$Parametros = @{},
    [int]$TimeoutMin = 20
)
$ErrorActionPreference = 'Stop'
if ($AzureConfigDir) { $env:AZURE_CONFIG_DIR = $AzureConfigDir }   # opcional: si no, se usa la sesión actual de Azure CLI
$token = (az account get-access-token --resource https://api.fabric.microsoft.com --query accessToken --output tsv).Trim()
$h = @{ Authorization = "Bearer $token"; 'x-ms-fabric-skill' = 'spark-cli' }
$api = 'https://api.fabric.microsoft.com/v1'
if (-not $WorkspaceId) {
    $WorkspaceId = ((Invoke-RestMethod -Headers $h -Uri "$api/workspaces").value | Where-Object { $_.displayName -ceq $WorkspaceName } | Select-Object -First 1).id
    if (-not $WorkspaceId) { throw "No se encontró el workspace $WorkspaceName" }
}
$item = (Invoke-RestMethod -Headers $h -Uri "$api/workspaces/$WorkspaceId/items?type=Notebook").value | Where-Object { $_.displayName -ceq $Nombre } | Select-Object -First 1
if (-not $item) { throw "No existe el notebook $Nombre" }
$cuerpo = if ($Parametros.Count) {
    @{ executionData = @{ parameters = @{} + ($Parametros.GetEnumerator() | ForEach-Object { @{ $_.Key = @{ value = $_.Value; type = ($_.Value -is [bool] ? 'bool' : ($_.Value -is [int] ? 'int' : 'string')) } } }) } } | ConvertTo-Json -Depth 8
} else { $null }
$inicio = Get-Date
$r = Invoke-WebRequest -Method Post -Uri "$api/workspaces/$WorkspaceId/items/$($item.id)/jobs/instances?jobType=RunNotebook" -Headers $h -SkipHttpErrorCheck -ContentType 'application/json' -Body $(if ($cuerpo) { $cuerpo } else { '{}' })
if ($r.StatusCode -ne 202) { throw "HTTP $($r.StatusCode): $($r.Content)" }
$ubicacion = [string]($r.Headers['Location'] | Select-Object -First 1)
Write-Host "Trabajo enviado: $Nombre -> $ubicacion"
$limite = (Get-Date).AddMinutes($TimeoutMin)
do {
    Start-Sleep -Seconds 10
    $estado = Invoke-RestMethod -Headers $h -Uri $ubicacion
    Write-Host ("  {0:HH:mm:ss} {1}" -f (Get-Date), $estado.status)
} while ($estado.status -in 'NotStarted', 'InProgress' -and (Get-Date) -lt $limite)
$duracion = if ($estado.startTimeUtc -and $estado.endTimeUtc) { ([datetime]$estado.endTimeUtc - [datetime]$estado.startTimeUtc).TotalSeconds } else { $null }
[pscustomobject]@{
    Notebook = $Nombre; Estado = $estado.status; Inicio = $estado.startTimeUtc; Fin = $estado.endTimeUtc
    SegundosDelTrabajo = $duracion; EsperaTotalSeg = [math]::Round(((Get-Date) - $inicio).TotalSeconds, 1)
    Falla = ($estado.failureReason | ConvertTo-Json -Compress -Depth 5); Id = $estado.id
} | Format-List
if ($estado.status -ne 'Completed') { exit 1 }
