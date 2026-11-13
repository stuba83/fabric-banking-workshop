# Referencias complementarias

Enlaces a la documentación oficial para estudiar los temas que el laboratorio **no ejecuta** (capacidad de pago, gateways, Key Vault, Git, despliegue entre ambientes, seguridad avanzada del modelo, gobierno y desarrollo asistido por IA). Acompañan a los [complementos del facilitador](../complementos/README.md) y a las guías de las cinco sesiones; **no forman parte de las evidencias** ni añaden ejercicios.

Las URL respondieron HTTP 200 el 12-nov-2026. La documentación cambia y varias funciones están en **vista previa**: validar el estado vigente antes de usarlas en un proyecto real. Este repositorio es un recurso de práctica independiente, con datos sintéticos; no es documentación oficial de Microsoft ni una implementación productiva.

**Qué sección consultar según la sesión**

| Sesión | Secciones |
|---|---|
| 1 · Fundamentos | [§1 Capacidad](#1-capacidad-pausa-reanudación-y-monitoreo-s1-y-s5), [§4 Medallion, Lakehouse y Warehouse](#4-medallion-lakehouse-y-warehouse-s1-y-s3) |
| 2 · Ingesta con pipeline | [§2 Conectividad y secretos](#2-conectividad-y-secretos-s2-y-s5), [§3 Ingesta metadata-driven](#3-ingesta-metadata-driven-e-incremental-s2) |
| 3 · Capa plata | [§4 Medallion, Lakehouse y Warehouse](#4-medallion-lakehouse-y-warehouse-s1-y-s3) |
| 4 · Modelo y gobernanza | [§5 Seguridad del modelo](#5-seguridad-del-modelo-y-consumo-s4), [§6 Gobierno](#6-gobierno-s4), [§8 Fabric Apps](#8-desarrollo-asistido-por-ia-y-aplicaciones-de-datos-s5) |
| 5 · Cierre | [§1 Capacidad](#1-capacidad-pausa-reanudación-y-monitoreo-s1-y-s5), [§2](#2-conectividad-y-secretos-s2-y-s5), [§7 Git y despliegue](#7-git-despliegue-e-infraestructura-como-código-s5), [§8 Desarrollo asistido por IA](#8-desarrollo-asistido-por-ia-y-aplicaciones-de-datos-s5) |

## 1. Capacidad: pausa, reanudación y monitoreo (S1 y S5)

| Tema | Referencia |
|---|---|
| Pausar y reanudar una capacidad (portal, API, runbook) | https://learn.microsoft.com/en-us/fabric/enterprise/pause-resume |
| API REST «Suspend» (Microsoft.Fabric/capacities) | https://learn.microsoft.com/en-us/rest/api/microsoftfabric/fabric-capacities/suspend |
| API REST «Resume» | https://learn.microsoft.com/en-us/rest/api/microsoftfabric/fabric-capacities/resume |
| Azure Automation (runbooks programados) | https://learn.microsoft.com/en-us/azure/automation/overview |
| Escalar una capacidad | https://learn.microsoft.com/en-us/fabric/enterprise/scale-capacity |
| Suavizado y limitación (throttling) | https://learn.microsoft.com/en-us/fabric/enterprise/throttling |
| App Capacity Metrics: instalación | https://learn.microsoft.com/en-us/fabric/enterprise/metrics-app-install |
| App Capacity Metrics: página de cómputo | https://learn.microsoft.com/en-us/fabric/enterprise/metrics-app-compute-page |

**Opciones para automatizar la pausa y la reanudación**

| Opción | Cuándo | Nota |
|---|---|---|
| Portal de Azure | Pruebas y demos | Manual |
| `az rest` / API REST `POST …/Microsoft.Fabric/capacities/{nombre}/suspend` o `/resume?api-version=2023-11-01` | Scripts y automatización | Requiere rol de Azure sobre la capacidad |
| **Runbook de Azure Automation (PowerShell)** con identidad administrada y un rol personalizado de solo pausa y reanudación, con dos programaciones (pausar / reanudar) | **Recomendada para horarios fijos** | La propia página de Learn la menciona |
| Logic App, Azure Function con temporizador, o un flujo programado de GitHub Actions / Azure Pipelines que llama a la API | Si ya se usan en la organización | Mismo rol de Azure |
| Pausa desde Fabric (último paso de un pipeline o notebook que llama a la API) | Pausar al terminar un lote | **Un notebook o pipeline no puede reanudar su propia capacidad**: pausada, no corre. La reanudación debe venir de fuera (runbook, Logic App) |

Al pausar, el contenido de la capacidad queda no disponible y el sobreuso acumulado se factura.

## 2. Conectividad y secretos (S2 y S5)

| Tema | Referencia |
|---|---|
| Gateway de datos local (on-premises) | https://learn.microsoft.com/en-us/data-integration/gateway/service-gateway-onprem |
| Clústeres de alta disponibilidad del gateway | https://learn.microsoft.com/en-us/data-integration/gateway/service-gateway-high-availability-clusters |
| Gateway de datos de red virtual (VNet), sin instalar nada | https://learn.microsoft.com/en-us/data-integration/vnet/overview |
| Acceder a datos locales desde Data Factory en Fabric | https://learn.microsoft.com/en-us/fabric/data-factory/how-to-access-on-premises-data |
| Conectores de Copy job (orígenes y destinos) | https://learn.microsoft.com/en-us/fabric/data-factory/copy-job-connectors |
| Referencias de Azure Key Vault en conexiones de Fabric | https://learn.microsoft.com/en-us/fabric/data-factory/azure-key-vault-reference-configure |
| `notebookutils` (credenciales, secretos, ejecución de notebooks) | https://learn.microsoft.com/en-us/fabric/data-engineering/notebook-utilities |

## 3. Ingesta metadata-driven e incremental (S2)

| Tema | Referencia |
|---|---|
| Actividad Lookup | https://learn.microsoft.com/en-us/fabric/data-factory/lookup-activity |
| Actividad ForEach | https://learn.microsoft.com/en-us/fabric/data-factory/foreach-activity |
| Actividad Notebook | https://learn.microsoft.com/en-us/fabric/data-factory/notebook-activity |
| Parámetros en pipelines | https://learn.microsoft.com/en-us/fabric/data-factory/parameters |
| Actividad de procedimiento almacenado | https://learn.microsoft.com/en-us/fabric/data-factory/stored-procedure-activity |
| Copy job (carga incremental y CDC) | https://learn.microsoft.com/en-us/fabric/data-factory/what-is-copy-job |
| Base de datos SQL en Fabric (para catálogo y bitácora de control) | https://learn.microsoft.com/en-us/fabric/database/sql/overview |

## 4. Medallion, Lakehouse y Warehouse (S1 y S3)

| Tema | Referencia |
|---|---|
| Arquitectura medallion en un Lakehouse | https://learn.microsoft.com/en-us/fabric/onelake/onelake-medallion-lakehouse-architecture |
| Accesos directos (shortcuts) de OneLake | https://learn.microsoft.com/en-us/fabric/onelake/onelake-shortcuts |
| Lakehouse frente a Warehouse: guía de decisión | https://learn.microsoft.com/en-us/fabric/fundamentals/decision-guide-lakehouse-warehouse |
| Consultar el Warehouse y consultas entre bases (mismo workspace) | https://learn.microsoft.com/en-us/fabric/data-warehouse/query-warehouse |
| Superficie de T-SQL soportada en Fabric | https://learn.microsoft.com/en-us/fabric/data-warehouse/tsql-surface-area |
| Administración de bibliotecas | https://learn.microsoft.com/en-us/fabric/data-engineering/library-management |
| Environments | https://learn.microsoft.com/en-us/fabric/data-engineering/create-and-use-environment |
| Ejecutar un notebook desde otro (`%run`, `notebookutils`) | https://learn.microsoft.com/en-us/fabric/data-engineering/author-execute-notebook |

## 5. Seguridad del modelo y consumo (S4)

| Tema | Referencia |
|---|---|
| Seguridad a nivel de objeto (OLS) | https://learn.microsoft.com/en-us/fabric/security/service-admin-object-level-security |
| Seguridad por filas (RLS) | https://learn.microsoft.com/en-us/fabric/security/service-admin-row-level-security |
| Seguridad en Direct Lake (SSO, identidad fija, OLS/RLS, OneLake security) | https://learn.microsoft.com/en-us/fabric/fundamentals/direct-lake-security-integration |
| TMDL: descripción general | https://learn.microsoft.com/en-us/analysis-services/tmdl/tmdl-overview |
| Vista TMDL | https://learn.microsoft.com/en-us/power-bi/transform-model/desktop-tmdl-view |

**¿Qué es TMDL?** Tabular Model Definition Language: la definición de un modelo semántico escrita como texto legible, con una sangría parecida a YAML. Sirve para leer, editar y versionar el modelo con Git. La vista TMDL del editor permite escribir un script y aplicarlo al modelo; con eso se define el OLS sin herramientas externas. Ejemplo (de Learn):

```text
createOrReplace

  role SeguridadPorObjetos
    modelPermission: read

    tablePermission Clientes
      columnPermission Direccion
        metadataPermission: none
```

`none`: la columna queda oculta para ese rol, como si no existiera. `read`: visible. Para ocultar una tabla completa, `metadataPermission: none` va directamente en el `tablePermission`.

## 6. Gobierno (S4)

| Tema | Referencia |
|---|---|
| Catálogo de OneLake | https://learn.microsoft.com/en-us/fabric/governance/onelake-catalog-overview |
| Dominios | https://learn.microsoft.com/en-us/fabric/governance/domains |
| Endoso (promovido y certificado) | https://learn.microsoft.com/en-us/fabric/governance/endorsement-overview |
| Linaje | https://learn.microsoft.com/en-us/fabric/governance/lineage |
| Etiquetas de sensibilidad (Information Protection) | https://learn.microsoft.com/en-us/fabric/governance/information-protection |

## 7. Git, despliegue e infraestructura como código (S5)

| Tema | Referencia |
|---|---|
| Integración de Git: introducción | https://learn.microsoft.com/en-us/fabric/cicd/git-integration/intro-to-git-integration |
| Administrar ramas (branch out, workspaces por rama) | https://learn.microsoft.com/en-us/fabric/cicd/git-integration/manage-branches |
| Automatizar Git con las API | https://learn.microsoft.com/en-us/fabric/cicd/git-integration/git-automation |
| Pipelines de despliegue: introducción | https://learn.microsoft.com/en-us/fabric/cicd/deployment-pipelines/intro-to-deployment-pipelines |
| Automatizar pipelines de despliegue | https://learn.microsoft.com/en-us/fabric/cicd/deployment-pipelines/pipeline-automation-fabric |
| Buenas prácticas de CI/CD | https://learn.microsoft.com/en-us/fabric/cicd/best-practices-cicd |
| Bibliotecas de variables (valores por ambiente) | https://learn.microsoft.com/en-us/fabric/cicd/variable-library/variable-library-overview |
| Biblioteca `fabric-cicd` (despliegue desde Git, para CI) | https://microsoft.github.io/fabric-cicd/ · https://github.com/microsoft/fabric-cicd |
| Proveedor de Terraform para Fabric | https://registry.terraform.io/providers/microsoft/fabric/latest/docs |

## 8. Desarrollo asistido por IA y aplicaciones de datos (S5)

| Tema | Referencia |
|---|---|
| Copilot en notebooks de Fabric | https://learn.microsoft.com/en-us/fabric/data-engineering/copilot-notebooks-overview |
| Copilot en Fabric: visión general | https://learn.microsoft.com/en-us/fabric/fundamentals/copilot-fabric-overview |
| Habilidades de agente de GitHub Copilot (skills) | https://docs.github.com/en/copilot/concepts/customizations/agent-skills |
| Servidores MCP en VS Code | https://code.visualstudio.com/docs/agent-customization/mcp-servers |
| Servidor MCP de modelado de Power BI | https://github.com/microsoft/powerbi-modeling-mcp |
| Fabric Apps: crear y desplegar con la CLI de Rayfin | https://learn.microsoft.com/en-us/fabric/apps/create-app-with-cli |
| Rayfin (código y plugin para agentes) | https://github.com/microsoft/rayfin |

Fabric Apps y varias de las funciones anteriores están en **vista previa**: validar el estado en la documentación antes de usarlas en producción.
