# Complementos del facilitador

Material **opcional** para quien facilita el entrenamiento. Amplía algunos momentos de las cinco sesiones con demostraciones ya construidas, hojas interactivas y referencias de estudio, sin cambiar la duración de ninguna sesión.

| Característica | Detalle |
|---|---|
| Qué son | Demostraciones y material de apoyo del facilitador para mostrar cómo se llevaría el patrón del laboratorio a un proyecto real |
| Evidencias | **No forman parte de las evidencias** de ninguna sesión: los participantes no los ejecutan ni los registran |
| Datos | **Sintéticos**: son los mismos CSV y tablas plata/oro del laboratorio |
| Requisitos | Según el complemento: una capacidad de Fabric activa (de pago o Trial, según lo que permita el tenant) para los que se despliegan, y solo un navegador para las hojas HTML |
| Alcance | Apoyo didáctico, **no una implementación productiva** ni documentación oficial de Microsoft |

## Qué complemento usar en cada sesión

| Sesión | Complemento | Qué demuestra | Requisitos |
|---|---|---|---|
| 1 · Fundamentos | [Referencias complementarias](../docs/referencias-complementarias.md), secciones 1 y 4 | Pausa y reanudación de la capacidad, Capacity Metrics, medallion y accesos directos (shortcuts) | Ninguno: es lectura |
| 2 · Ingesta | [`metadata-driven/`](metadata-driven/README-metadata-driven.md) | Un pipeline y un cuaderno parametrizado que cargan varias tablas porque un **catálogo** lo describe (Lookup + ForEach + Notebook); carga completa frente a incremental con **marca de agua**; bitácora de corridas | Capacidad activa; el Lakehouse de las Sesiones 1 y 2 con los CSV; PowerShell 7 y Azure CLI si se despliega con el script |
| 3 · Capa plata | [`warehouse-librerias/`](warehouse-librerias/README-warehouse-librerias.md) | Un Warehouse con esquema por dominio y procedimientos T-SQL que leen el Lakehouse del mismo workspace (idempotencia, atomicidad y el cuadre 72.360 − 288 − 72 = 72.000); tres formas de compartir código entre notebooks; Spark frente a T-SQL | Capacidad activa con Warehouse y Environments; el Lakehouse con las tablas plata/oro de la Sesión 3; PowerShell 7 y Azure CLI si se despliega con el script; el `.whl` se construye localmente |
| 4 · Modelo y gobernanza | [Referencias complementarias](../docs/referencias-complementarias.md), secciones 5, 6 y 8 | Seguridad a nivel de objeto con TMDL, consumo de un modelo, seguridad en Direct Lake, catálogo de OneLake, dominios y Fabric Apps (vista previa) | Ninguno: es lectura |
| 5 · Cierre | [`git-cicd/`](git-cicd/fabric-cicd-git-flujo.html) | Hoja interactiva: el viaje de un cambio con integración de Git, ramas, pipelines de despliegue, `fabric-cicd` y Terraform | Un navegador; no necesita conexión |
| 5 · Cierre | [`desarrollo-asistido-ia/`](desarrollo-asistido-ia/fabric-desarrollo-asistido-ia-flujo.html) y [guion](desarrollo-asistido-ia/guion-demo.md) | Demostración de ≈8 minutos de desarrollo asistido por IA (reglas, skills, servidor MCP, Git y supervisión humana); la guía de estudio opcional está en el [bonus](../docs/bonus-desarrollo-asistido/guia.md) | Un navegador para la hoja; para la demostración en vivo, VS Code con GitHub Copilot, Azure CLI y un workspace de pruebas |

## Estructura

```text
complementos/
  README.md                         este índice
  metadata-driven/                  S2: notebooks, pipelines y deploy.ps1 de la ingesta guiada por catálogo
  warehouse-librerias/              S3: Warehouse, bibliotecas compartidas, Spark frente a T-SQL, herramientas
  git-cicd/                         S5: hoja interactiva de Git, ambientes, despliegue y Terraform
  desarrollo-asistido-ia/           S5: hoja interactiva y guion de la demostración
```

Las hojas HTML son archivos únicos y autocontenidos: no cargan recursos externos ni guardan datos en el navegador. Se abren con doble clic.

## Cómo desplegar los complementos que lo requieren

Cada complemento trae su propio README con los pasos, las pruebas y los controles esperados:

1. [`metadata-driven/README-metadata-driven.md`](metadata-driven/README-metadata-driven.md), sección 9.
2. [`warehouse-librerias/README-warehouse-librerias.md`](warehouse-librerias/README-warehouse-librerias.md), sección 11. Antes de desplegar hay que construir el `.whl` con `python -m build` (no se versiona).

Reglas comunes de los scripts de despliegue:

- Usan la **sesión actual de Azure CLI**: quien despliega ejecuta antes `az login`. Los scripts nunca inician sesión; `-AzureConfigDir` es opcional y solo apunta a otro perfil de Azure CLI.
- **`-WorkspaceName` es obligatorio.** El nombre del workspace lo elige quien despliega; en el laboratorio, un nombre con su prefijo propio. Usar siempre un workspace de práctica.
- Crean solo elementos con prefijo `FAC_` y no modifican los elementos del participante. **No pausan, reanudan ni escalan la capacidad**: la activación o la pausa son decisiones humanas (el despliegue de `warehouse-librerias` se detiene con un mensaje si la capacidad no está activa).
- Ejecutar primero con `-WhatIf`, que solo lee y muestra lo que haría.
- Las pruebas sin Fabric (`python -m unittest discover -s tests` desde la raíz del repositorio) comprueban que estos archivos están completos y sin información sensible; no sustituyen una verificación en un workspace.

## Avisos

- Los resultados que traen los README (conteos, tiempos y pruebas) se **verificaron en un workspace de laboratorio (nov-2026)**. Son valores observados, sin línea base, y varían con el entorno, la región y la capacidad.
- Las funciones en vista previa (por ejemplo, Fabric Apps) pueden cambiar. Confirmar el estado vigente en la documentación antes de usarlas.
- No subir a este repositorio evidencias completadas, capturas del tenant, nombres de organizaciones, identificadores reales ni credenciales.
- Referencias de estudio: [`docs/referencias-complementarias.md`](../docs/referencias-complementarias.md).
