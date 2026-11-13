# Bonus — Desarrollo en Fabric asistido por IA

**Audiencia:** Ingenieros de datos que quieren saber cómo un agente de IA puede ayudar a construir y mantener artefactos de Fabric de forma revisable  
**Formato:** Guía de estudio opcional, sin ejercicios obligatorios ni evidencias  
**Dedicación orientativa:** de 20 a 30 minutos de lectura; replicar el entorno depende de las herramientas y los permisos del equipo  
**Verificado contra la documentación:** 12 de noviembre de 2026

Este bonus **no forma parte de las cinco sesiones** ni de sus evidencias. Amplía el tema «Desarrollo asistido por IA» de la sección 3 de la [Sesión 5](../sesion-05/guia.md) y acompaña la demostración del facilitador (≈8 minutos), cuyo material está en [`complementos/desarrollo-asistido-ia`](../../complementos/desarrollo-asistido-ia/fabric-desarrollo-asistido-ia-flujo.html). Usa el mismo caso sintético y es apoyo didáctico, no una implementación productiva.

## Resultado esperado

Al terminar, cada participante podrá:

1. **Explicar qué es** un agente, las reglas del proyecto, un skill y un servidor MCP, y cómo se combinan.
2. **Replicar el entorno** en un proyecto de pruebas, con las herramientas y los permisos mínimos.
3. **Poner guardarraíles**: qué decide una persona, qué controla la identidad y qué deja evidencia en Git.
4. **Distinguir lo disponible de lo que está en vista previa** (Fabric Apps con la CLI de Rayfin, servidor MCP de Power BI, formato de configuración MCP) y no prometer más de lo verificado.

## Dos pistas que no se mezclan

| Pista | Qué es | En esta guía |
|---|---|---|
| **1 · Flujo de desarrollo asistido** | Un agente de GitHub Copilot en VS Code o en la línea de comandos, con reglas, skills, un servidor MCP, herramientas y Git, para construir artefactos de Fabric (notebooks, pipelines, modelos, reportes) de forma revisable | **Es el tema** |
| **2 · Copilot dentro de Fabric y Power BI** | Asistencia en el portal (notebooks, Data Factory, Warehouse, Power BI) y preguntas en lenguaje natural. Depende de la capacidad, la región y el gobierno del tenant | Solo se menciona; ver las [referencias](#referencias) |

Son además licencias distintas: **GitHub Copilot** (suscripción de GitHub), **Copilot en Fabric y Power BI** (según la documentación, habilitado por defecto en tenants con capacidades de pago F2 o superior, y consume capacidad) y **Microsoft 365 Copilot**. Tener uno no habilita los otros: confirmar cada licencia con el administrador. En el laboratorio, con capacidad Trial, esas funciones pueden no estar disponibles.

## 1. Qué es cada pieza

| Pieza | Qué es | Dónde vive |
|---|---|---|
| **Agente** | El asistente de GitHub Copilot en modo *Agent*. Planifica una tarea acotada, ejecuta herramientas (comandos, APIs, servidores MCP) y pide aprobación para las acciones sensibles. Una persona define, aprueba y revisa | VS Code con GitHub Copilot Chat o Copilot CLI |
| **Reglas del proyecto** | Instrucciones persistentes que el agente lee antes de actuar: alcance, datos permitidos, qué no debe tocar. **Guían; no son un control técnico** | `.github/copilot-instructions.md` |
| **Skill** | Una carpeta con un archivo `SKILL.md` (y recursos) que enseña al agente **cómo** hacer bien una tarea, por ejemplo construir un notebook medallion o un modelo semántico. El agente carga el skill que corresponde a la tarea | `.github/skills/` |
| **Servidor MCP** | Un proceso que expone **herramientas** al agente mediante el protocolo MCP (*Model Context Protocol*). Por ejemplo, el servidor de modelado de Power BI edita un modelo semántico en lote (buenas prácticas, nombres, traducciones) | Configuración del proyecto (`mcp.json`) |
| **Agente personalizado** (opcional) | Un perfil en Markdown con instrucciones y herramientas propias para un rol (administración, ingeniería de datos, consultas) | `.github/agents/*.agent.md` |

Dicho de forma corta: los **skills** son el *cómo*; las **herramientas** (Azure CLI, APIs de Fabric y el servidor MCP) son el *qué*; las **reglas** fijan el alcance; y **Git** deja cada cambio como un *diff* que se revisa o se revierte.

## 2. El flujo

```text
Persona (pide, revisa y aprueba)
  -> Agente de GitHub Copilot
      -> Reglas del proyecto        (qué puede y qué no)
      -> Skills de Fabric           (cómo se hace bien)
      -> Herramientas               (Azure CLI, APIs REST de Fabric y Power BI, servidor MCP, CLI de reportes)
          -> Archivos en Git local  (TMDL del modelo, PBIR del reporte, notebooks)
              -> Workspace de pruebas en Fabric
```

Un recorrido típico del caso: un Lakehouse con capas bronce, plata y oro y un notebook (prompt 1), un pipeline de datos que lo ejecuta (prompt 2), un modelo semántico Direct Lake guardado como TMDL (prompt 3), una revisión del modelo con el servidor MCP (prompt 4) y un reporte que **primero se especifica y solo se construye tras la aprobación de una persona** (prompts 5 y 6). Los prompts de ejemplo, con botón para copiarlos, están en la hoja interactiva. Se escriben en inglés porque los skills están escritos en inglés y, según la experiencia del ensayo, funcionan mejor así; las notas pueden ser en español.

## 3. Cómo replicar el entorno

Hacerlo en un proyecto y un workspace de **pruebas**, con datos sintéticos.

**Estación de trabajo**

- [ ] VS Code con la extensión de GitHub Copilot (Chat) y el agente en modo **Agent**; una cuenta de GitHub con acceso a Copilot. En cuentas de organización, algunas capacidades (por ejemplo, los servidores MCP) las controla una política del administrador de GitHub.
- [ ] Node.js y npm (los usan `npx` y la CLI de Rayfin; la receta de Fabric Apps con Copilot pide Node.js 20 o posterior).
- [ ] Azure CLI instalada y una sesión iniciada con la cuenta de pruebas: `az account show` debe mostrar la cuenta y el tenant esperados.
- [ ] Git instalado, con la carpeta del proyecto inicializada y un primer *commit* (la línea base para ver los diffs).
- [ ] Terminal predeterminada en PowerShell (en `.vscode/settings.json`).
- [ ] Un modelo de razonamiento profundo elegido en el selector de modelos del chat.

**Estructura del proyecto**

```text
proyecto-fabric-ia/
├─ .github/
│  ├─ copilot-instructions.md   reglas y guardarraíles
│  ├─ agents/                   agentes personalizados (opcional)
│  └─ skills/                   skills de Fabric (carpetas con SKILL.md)
├─ .vscode/                     configuración de VS Code (terminal, aprobaciones)
├─ models/                      modelos semánticos (TMDL)
├─ reports/                     reportes (PBIR)
└─ _brief/                      especificaciones aprobadas
```

**Skills.** El repositorio público [`microsoft/skills-for-fabric`](https://github.com/microsoft/skills-for-fabric) (licencia MIT) publica skills de Fabric. Según su README, se pueden instalar como plugins en Copilot CLI (`/plugin marketplace add microsoft/skills-for-fabric`, luego `/plugin install fabric-skills@fabric-collection` y `/plugin install powerbi-authoring@fabric-collection`), de a uno con APM, o copiando las carpetas a `.github/skills` para versionarlas con Git. Verificar la versión instalada: el contenido cambia. Un prompt de comprobación útil: *«Which Fabric skills do you have available in this project? List their names only.»*

**Servidor MCP de modelado de Power BI.** Se registra en la configuración MCP del proyecto. La documentación vigente de VS Code recomienda un archivo `.mcp.json` en la raíz con la clave `mcpServers`; el formato `.vscode/mcp.json` con la clave `servers` se asocia al arnés «Local», marcado como deprecado. Ejemplo con el formato recomendado:

```json
{
  "mcpServers": {
    "powerbi-authoring-local": {
      "type": "stdio",
      "command": "npx",
      "args": ["-y", "@microsoft/powerbi-modeling-mcp@1.0.0", "--start"]
    }
  }
}
```

La versión fijada (`1.0.0`) es la que se usó en el ensayo; al preparar este material npm mostraba la `1.0.1`. Fijar y probar la que se use. La primera vez, **una persona** revisa y acepta el EULA del servidor. No registrar a la vez el servidor local y el hospedado: el agente vería herramientas duplicadas.

**Capacidad y permisos.** Una capacidad de Fabric asignada al workspace de pruebas, que administra y verifica **una persona** (el agente no la opera), y permiso para crear el workspace de pruebas o un rol Contributor, Member o Admin en uno existente.

## 4. Guardarraíles

| Guardarraíl | Cómo se aplica |
|---|---|
| **Alcance de workspaces** | Las reglas nombran el prefijo donde el agente puede crear o modificar (por ejemplo, `ws-ia-dev*`) y qué no debe tocar nunca |
| **Datos sintéticos** | El notebook genera los datos; el agente no lee ni copia datos reales |
| **Aprobación humana** | El skill de reportes escribe una especificación (`_brief/report-spec.md`) y se detiene: nada se construye ni se publica hasta que una persona aprueba |
| **Sin operaciones de capacidad** | El agente no pausa, reanuda, escala ni borra la capacidad: es una decisión humana |
| **Cambios revisables** | Modelos (TMDL) y reportes (PBIR) son archivos de texto: cada edición es un diff en Git |
| **Identidad explícita** | Antes de llamar a Azure o a Fabric, el agente comprueba la cuenta con `az account show` y no ejecuta `az login` ni `az account set` sin que se lo pidan |

Un ejemplo mínimo de reglas (el archivo es para el agente, por eso va en inglés; adaptarlo y usar nombres propios):

```text
# AI-assisted Fabric development (synthetic data only)
- Before any Fabric or Azure call, run `az account show` and confirm the account and tenant. If they are not the expected ones, stop and tell the user.
- Never run `az login` or `az account set` unless the user asks.
- Create or modify items only in workspaces named `ws-ia-dev*`. Never touch any other workspace.
- Never pause, resume, scale or delete the Fabric capacity.
- Synthetic data only. Never read or copy real data.
- Keep semantic models (TMDL) and reports (PBIR) as files in this repo so every change is a Git diff.
- For reports: write a spec first, show it, and wait for explicit approval before building or publishing.
```

**Honestidad técnica.** Las reglas **guían** al agente, pero no son un control técnico. El control real son los permisos de la identidad (rol en el workspace y acceso a la capacidad), la aprobación de comandos de terminal en VS Code y la revisión del diff en Git. Hay que usar las tres capas juntas.

## 5. Límites y vista previa

| Pieza | Estado según la documentación | Qué tener presente |
|---|---|---|
| **Fabric Apps y la CLI de Rayfin** | **Vista previa** | Aplicaciones de datos (React y TypeScript) con alojamiento y autenticación de Fabric. Un administrador habilita *Fabric Apps (preview)* en el portal de administración; no está disponible en todas las regiones; consume capacidad. Comandos de referencia: `npm create @microsoft/rayfin@latest -- app-banca --workspace ws-ia-dev`, `npm run dev`, `npx rayfin up --dry-run` (vista previa del despliegue, sin cambios), `npx rayfin up` y `npx rayfin up status`. Confirmar los comandos en la versión instalada |
| **Servidor MCP de modelado de Power BI** | **Local: disponible; hospedado: vista previa** | El local trabaja con archivos TMDL y PBIP en disco; para un modelo dentro de un workspace, la documentación recomienda el hospedado. Con el servidor local sobre un workspace se necesita el punto de conexión XMLA en lectura y escritura y permiso de escritura. **Solo modela: no cambia las páginas de un reporte**. No se probó con otros orígenes (por ejemplo, Analysis Services): verificar |
| **Formato de configuración MCP** | **Verificar** | `.mcp.json` con `mcpServers` es lo que la documentación vigente recomienda; `.vscode/mcp.json` con `servers` pertenece al arnés «Local», deprecado. Confirmar contra la documentación de VS Code |
| **Skills de Fabric** | **Verificar** | Repositorio público con versiones; algunos skills se marcan como experimentales. Verificar la versión instalada |
| **Copilot en notebooks de Fabric** | **Vista previa** | Otra pista; depende de la capacidad (F2 o superior) y del tenant |

**Qué se observó en un ensayo, sin generalizar.** (1) Direct Lake creado sobre el **endpoint SQL** del Lakehouse funcionó; la variante sobre OneLake creada por API falló al refrescar. Es una observación de un entorno concreto: verificarla en el propio. (2) Armar, aprobar y publicar el reporte llevó cerca de **23 minutos de tiempo de agente**. Es un tiempo observado en un ensayo, **sin línea base manual**: no es una cifra de beneficio ni sirve para comparar. Por eso la demostración muestra el reporte prearmado. Para medir de verdad hay que repetir la misma tarea de la forma habitual y con el agente, y comparar.

**Otras advertencias.** Los metadatos y resultados que el agente lee viajan al proveedor del modelo: definir la política antes de usar entornos reales y no compartir sesiones de chat con información sensible. Esta guía no reemplaza la revisión de seguridad ni el gobierno de cada organización.

## 6. Material del facilitador

- [Hoja interactiva del flujo](../../complementos/desarrollo-asistido-ia/fabric-desarrollo-asistido-ia-flujo.html): animación del flujo, guardarraíles, lista para replicar el entorno, prompts de ejemplo y referencias. Se abre en el navegador, sin conexión.
- [Guion de la demostración](../../complementos/desarrollo-asistido-ia/guion-demo.md): minuto a minuto, qué mostrar en vivo y qué prearmado, plan B y preguntas probables.
- [Índice de complementos](../../complementos/README.md): todo el material opcional del facilitador.

## Estado de verificación

El flujo se observó en un ensayo previo del facilitador; los prompts de esta guía y de la hoja están generalizados a partir de él, y el material se preparó **sin ejecutar nada contra Fabric** desde este repositorio. Los enlaces respondieron HTTP 200 el 12 de noviembre de 2026. Los pasos y los nombres de menús pueden cambiar con la versión. Hacer un ensayo completo en un entorno de pruebas antes de mostrar el flujo a otras personas.

## Bloqueos frecuentes

| Síntoma | Revisar |
|---|---|
| El agente dice estar firmado con otra cuenta o tenant, o `az` falla con «subscription not found» | Abrir una terminal PowerShell **nueva** dentro del proyecto y ejecutar `az account show`; evitar WSL si su `az` apunta a otro tenant. No ejecutar `az login` salvo que el token haya expirado, y que lo haga una persona |
| El servidor MCP bloquea las llamadas o no conecta | Que una persona haya revisado y aceptado el EULA; comprobar con «MCP: List Servers» que está iniciado; en cuentas de organización, la política «MCP servers in Copilot» puede estar deshabilitada |
| El agente carga un skill de despliegue o de sincronización con Git cuando se quería un pipeline de datos o archivos locales | Detenerlo y ser más específico: «(not a deployment pipeline)» o «do not use Fabric Git integration». El prompt también enruta el skill |
| El refresh del modelo Direct Lake falla | Volver a la variante sobre el endpoint SQL del Lakehouse; en un Lakehouse con esquemas, listar las tablas por OneLake o por el endpoint SQL |
| La lista de skills sale vacía | Que se abrió la carpeta del proyecto (no una carpeta padre) y que el agente está en modo Agent |
| No hay vista previa local del reporte | Sin Power BI Desktop el agente puede validar y publicar el PBIR, pero la verificación visual se hace en el servicio, tras publicar |
| La capacidad está pausada | No pedirle al agente que la reanude: es una decisión humana. Coordinarlo con el administrador |

## Siguiente paso

Volver a la [Sesión 5](../sesion-05/guia.md) y elegir, junto con el equipo, si el desarrollo asistido por IA entra en el plan del proyecto real. Si es así, repetir el flujo en una sesión práctica contra un entorno de pruebas **midiendo con una línea base**: tiempo hasta el primer reporte publicado, pasos manuales evitados, defectos detectados antes de publicar y tiempo de revisión del diff. Para el caso de ciencia de datos y ML, ver el [bonus de ML](../bonus-ml/guia.md).

## Referencias

- [Instrucciones personalizadas del repositorio (GitHub Docs)](https://docs.github.com/en/copilot/how-tos/copilot-on-github/customize-copilot/add-custom-instructions/add-repository-instructions).
- [Agent skills (GitHub Docs)](https://docs.github.com/en/copilot/concepts/customizations/agent-skills) y [custom agents (GitHub Docs)](https://docs.github.com/en/copilot/concepts/customizations/custom-agents).
- [Añadir y usar servidores MCP en VS Code](https://code.visualstudio.com/docs/agent-customization/mcp-servers) y [referencia de configuración MCP](https://code.visualstudio.com/docs/agents/reference/mcp-configuration).
- [Servidor MCP de modelado de Power BI (GitHub)](https://github.com/microsoft/powerbi-modeling-mcp) y [su documentación en Learn](https://learn.microsoft.com/en-us/power-bi/developer/mcp/power-bi-authoring-mcp).
- [Skills de Fabric (GitHub)](https://github.com/microsoft/skills-for-fabric).
- [Fabric Apps: visión general](https://learn.microsoft.com/en-us/fabric/apps/overview), [crear una app con la CLI de Rayfin](https://learn.microsoft.com/en-us/fabric/apps/create-app-with-cli), [referencia de la CLI](https://learn.microsoft.com/en-us/fabric/apps/cli-reference) y [Rayfin (GitHub)](https://github.com/microsoft/rayfin).
- [Funciones en vista previa de Fabric](https://learn.microsoft.com/en-us/fabric/fundamentals/preview) y [disponibilidad por región](https://learn.microsoft.com/en-us/fabric/admin/region-availability).
- [Copilot en Fabric: visión general](https://learn.microsoft.com/en-us/fabric/fundamentals/copilot-fabric-overview) y [Copilot en notebooks](https://learn.microsoft.com/en-us/fabric/data-engineering/copilot-notebooks-overview).
- [Planes de GitHub Copilot](https://docs.github.com/en/copilot/get-started/plans) y [¿Qué es Microsoft Copilot?](https://learn.microsoft.com/en-us/copilot/plan/copilot-overview).
- Más enlaces de estudio: [referencias complementarias](../referencias-complementarias.md), sección 8.

Los enlaces se consultaron al preparar esta versión; la documentación y las funciones en vista previa pueden cambiar. Este recurso es de práctica independiente: no es documentación oficial de Microsoft ni una implementación productiva.
