# Guion de demo · Sesión 5 — Desarrollo en Fabric asistido por GitHub Copilot

> **Complemento del facilitador (opcional).** No forma parte de las evidencias de las sesiones. Usa datos sintéticos y es apoyo didáctico, no una implementación productiva. Guía de estudio relacionada: [bonus de desarrollo asistido por IA](../../docs/bonus-desarrollo-asistido/guia.md).

**Formato:** demo de **8 min** dentro de un bloque de **10 min** (los últimos 2 min son colchón y preguntas).
**Público:** equipo técnico en la última sesión de un taller didáctico (datos sintéticos).
**Idioma:** guion y notas en español; **prompts en inglés** (los skills funcionan mejor así).
**Apoyo visual:** `fabric-desarrollo-asistido-ia-flujo.html` (5 pestañas: Flujo animado · Guardarraíles · Para replicarlo · Prompts de ejemplo · Referencias).

> **Aviso importante:** el armado en vivo de un reporte completo **no cabe** en el tiempo. En un ensayo previo, planear, aprobar, construir, validar y publicar el reporte llevó cerca de **23 min de tiempo de agente**. Es un tiempo **observado en un ensayo, sin línea base manual**: no es una cifra de beneficio y no debe usarse para comparar. Por eso el reporte se muestra **prearmado**.
>
> **Este guion se preparó sin ejecutar nada contra Fabric.** Los prompts están generalizados a partir de un ensayo previo; haz un ensayo completo antes de la sesión.

## Regla de oro: dos pistas, nunca mezcladas

| Pista | Qué es | En esta demo |
|---|---|---|
| **1 · Flujo de desarrollo asistido** | Agente de GitHub Copilot + reglas + skills + servidor MCP + herramientas + Git, para construir artefactos de Fabric de forma revisable. | **Es la demo.** |
| **2 · Copilot dentro de Fabric y Power BI** | Asistencia dentro del portal (notebooks, Data Factory, warehouse, Power BI) y preguntas en lenguaje natural. | Solo una mención. No se demuestra. |

---

## 1. Plan minuto a minuto

| Min | Qué haces | Modo | Dónde |
|---|---|---|---|
| **0:00–0:45** | Apertura: el problema, las dos pistas y el mapa del flujo (agente → reglas → skills → MCP → herramientas → Git → Fabric). Haz clic en *Reglas*, *Skills* y *Servidor MCP* para anclar las tres capas. **No reproduzcas la animación completa** (dura ~1:53 a 1×). | HTML | Pestaña 1 |
| **0:45–1:30** | **En vivo:** estructura del proyecto en VS Code (~45 s): `.github/skills`, `.github/agents`, `.github/copilot-instructions.md`, `.vscode/mcp.json`, `models/`, `reports/`, panel de Git. | **EN VIVO** | VS Code |
| **1:30–2:10** | **En vivo:** **Prompt 0** (~20 s de ejecución) y lectura de la respuesta: cuenta, tenant y los únicos workspaces permitidos. | **EN VIVO** | VS Code (chat) |
| **2:10–3:30** | Datos: lakehouse con bronze/silver/gold, notebook y pipeline con su historial de ejecución. Muestra el chat guardado de los Prompts 1–2. | PREARMADO | Fabric + chat guardado |
| **3:30–4:40** | Modelo semántico: TMDL en `models/`, chat del Prompt 3, y el Prompt 4 con el MCP. Cierra con `git diff --stat`. | PREARMADO | VS Code + Fabric |
| **4:40–6:15** | Reporte: `_brief/report-spec.md` (la puerta de aprobación humana) y el reporte ya publicado. Di el tiempo observado y que no hay línea base manual. | PREARMADO | VS Code + Fabric |
| **6:15–7:15** | Guardarraíles y cuidados: 4 mensajes (ver §4). | HTML | Pestaña 2 |
| **7:15–8:00** | Cierre: cómo replicarlo, dónde copiar los prompts y siguiente paso. | HTML | Pestañas 3 y 4 |
| **8:00–10:00** | Colchón y preguntas (ver §6). | — | — |

**Si vas corto de tiempo:** salta el Prompt 4 (MCP) y el detalle de cuidados; conserva Prompt 0, el modelo y la puerta de aprobación del reporte.

---

## 2. Qué mostrar en vivo y qué prearmado

### En vivo (≈ 1 min 40 s en total)
1. **Estructura del proyecto** (~45 s). Abre el explorador y recorre solo lo que importa:
   - `.github/copilot-instructions.md` → *las reglas* (alcance, datos sintéticos, sin operar la capacidad).
   - `.github/skills/` → *el cómo* (carpetas con `SKILL.md`; origen público: `microsoft/skills-for-fabric`).
   - `.github/agents/` → perfiles de agente (opcional).
   - `.vscode/mcp.json` (o `.mcp.json`) → *las herramientas* (solo la configuración).
   - `models/`, `reports/`, `_brief/` y el panel de Git → *cada cambio es un diff*.
2. **Prompt 0** (~20 s):

```text
Which Azure account and tenant are you using, and which Fabric workspaces are you allowed to create or modify in this project? Answer from the project rules and a read-only `az account show`; do not change anything.
```

*Esperado:* la cuenta de pruebas y solo workspaces `ws-ia-dev*`; los demás están protegidos.

### Prearmado (no se ejecuta en vivo)
| Artefacto | Qué abrir | Prompt de origen | Tiempo observado en un ensayo* |
|---|---|---|---|
| Lakehouse `lh_banca` + notebook `nb_medallion` | Workspace `ws-ia-dev`; las tres celdas del notebook | 1 | — |
| Pipeline `pl_medallion` | Historial de ejecución; tablas bronze/silver/gold | 2 | ~80–104 s (sesión caliente), ~3.5 min (en frío) |
| Modelo `sm_kpis` | `models/…SemanticModel/` (TMDL) y el modelo publicado | 3 | ~3.5 min |
| Revisión con MCP + traducción | Chat guardado + `git diff --stat` | 4 | — |
| Especificación del reporte | `_brief/report-spec.md` | 5 | — |
| Reporte `rpt_ejecutivo` | `reports/…Report/` (PBIR) y el reporte publicado | 6 (y 7) | ~23 min de agente, con aprobación humana |

\* *Tiempos observados en un ensayo, sin línea base manual; varían con el entorno.*

---

## 3. Guion hablado por tramo (notas en español)

### 0:00–0:45 · Apertura
> «Hoy no vamos a construir IA sobre sus datos: vamos a ver cómo un agente de desarrollo ayuda a **construir los artefactos de Fabric** —notebook, pipeline, modelo y reporte— de forma **revisable**.»
> «Tiene tres capas: **reglas** que dicen qué puede y qué no puede hacer, **skills** que le enseñan cómo se hace bien, y **herramientas** (Azure CLI, APIs de Fabric, el servidor MCP) que hacen el trabajo. Todo termina como **archivos en Git**.»
> «Hay otra conversación, Copilot dentro de Fabric y Power BI, que no vamos a mezclar con esta.»

### 0:45–1:30 · Estructura del proyecto (en vivo)
> «Los skills son carpetas de instrucciones: el agente carga el que corresponde a la tarea. Las reglas fijan el alcance. El MCP le da herramientas para editar modelos. Y Git nos deja ver cada cambio como un diff.»

### 1:30–2:10 · Prompt 0 (en vivo)
> «Lo primero que hace el agente es comprobar **quién es**: cuenta, tenant y en qué workspaces puede tocar. No se autentica solo: usa la sesión de mi terminal.»
> «Las reglas **guían**; el control real son los permisos de mi identidad y mi revisión.»

### 2:10–3:30 · Datos (prearmado)
> «Nadie escribió este notebook ni el JSON del pipeline a mano: el agente siguió el patrón medallion del skill. Datos **sintéticos**, solo en el workspace permitido.»
> «Fíjense en el pipeline: le pedimos explícitamente un pipeline **de datos, no de implementación**. El prompt también enruta el skill.»

### 3:30–4:40 · Modelo y MCP (prearmado)
> «El modelo es TMDL en el repo local, publicado, refrescado y validado con una consulta DAX. En el ensayo, Direct Lake funcionó sobre el **endpoint SQL** del lakehouse; **verifíquenlo en su entorno**.»
> «El MCP brilla en cambios en lote sobre un modelo que ya existe: buenas prácticas, nombres, traducciones. Y después, `git diff --stat`: cada cambio se puede revisar o revertir.»
> *(Solo muestra la configuración del MCP. No afirmes que funciona con otros orígenes, p. ej. Analysis Services, si no lo probaste.)*

### 4:40–6:15 · Reporte (prearmado)
> «Aquí está la parte que no es opcional: el skill **escribe una especificación y se detiene**. Nada se construye hasta que una persona la aprueba.»
> «Armar y publicar este reporte llevó unos **23 minutos de tiempo de agente** en un ensayo. No tengo una línea base manual con la que compararlo, y no voy a inventar una; por eso lo traigo prearmado.»

### 6:15–7:15 · Guardarraíles y cuidados (pestaña 2)
> «Cuatro cosas que aprendimos: **uno**, la autenticación de la terminal; **dos**, el EULA del MCP se acepta una vez y lo decide una persona; **tres**, si el agente elige el skill de despliegue o de sincronización Git, se le corrige con la frase explícita; **cuatro**, el tiempo del reporte es observado, no una promesa.»

### 7:15–8:00 · Cierre (pestañas 3 y 4)
> «Para replicarlo necesitan VS Code con GitHub Copilot, la carpeta de skills, las reglas, el MCP y Azure CLI. Está todo en la pestaña “Para replicarlo”, y los prompts están listos para copiar.»
> «Siguiente paso sugerido: repetir este flujo en una sesión práctica contra un entorno de pruebas, **midiendo con una línea base** (ver §6, pregunta 2).»

---

## 4. Frases clave (para memorizar)

1. «Las **reglas** guían; los **permisos** protegen; **Git** deja evidencia.»
2. «Los skills son el **cómo**; el MCP y las APIs son el **qué**.»
3. «El agente no se autentica solo: usa **mi** sesión.»
4. «El prompt también **enruta** el skill: sé específico.»
5. «La **aprobación humana** de la especificación es parte del proceso, no un extra.»
6. «Cada cambio es un **diff**: se revisa o se revierte.»
7. «Tiempo **observado en un ensayo**, sin línea base manual.»
8. «Direct Lake sobre el endpoint SQL funcionó en el ensayo: **verifíquenlo** en su entorno.»

---

## 5. Plan B

| Si pasa esto | Haz esto | Qué decir |
|---|---|---|
| El Prompt 0 tarda o falla | Muestra la captura/chat guardado del Prompt 0 y sigue. | «Les enseño la respuesta de un ensayo; lo importante es que lee las reglas y comprueba su identidad.» |
| El agente responde con otra cuenta o tenant | Abre una **terminal PowerShell nueva** dentro del proyecto, ejecuta `az account show`, y repite el Prompt 0. Si sigue mal, pasa al chat guardado. | «Justo para esto existe la comprobación: el agente usa la sesión de la terminal.» |
| Copilot no está firmado o el modelo va lento | Pasa a la pestaña 1 y recorre el flujo con «Paso ▶»; muestra los artefactos prearmados. | «Veamos el flujo y los resultados ya construidos.» |
| El MCP pide el EULA o no conecta | No lo aceptes por el público: una persona lo revisa. Comprueba «MCP: List Servers». Si no responde, muestra el chat guardado del Prompt 4 y el diff. | «El EULA lo acepta una persona; el agente solo lo ejecuta si lo autorizo.» |
| El agente carga el skill equivocado (despliegue o Git) | Detenlo y repite la frase explícita: «(not a deployment pipeline)» o «do not use Fabric Git integration». | «Es la señal para ser más específico: el prompt también enruta.» |
| El refresh del modelo falla | No improvises: abre el modelo prearmado y el TMDL del repo. Menciona la variante del endpoint SQL. | «Esto es lo que validan el agente y el validador; la variante del endpoint SQL fue la que funcionó en el ensayo.» |
| No abre el portal de Fabric o no hay red | Usa capturas de cada artefacto y los archivos del repo (`models/`, `reports/`, `_brief/`). | «Todo está como archivos: se puede revisar sin abrir el portal.» |
| El reporte no se ve bien | Muestra la especificación aprobada y los archivos PBIR. | «Aquí está lo que se pidió y lo que se generó; la verificación visual se hace en el servicio.» |
| La capacidad está pausada | **No la toques durante la demo** (el agente no la opera). Pasa a capturas y a los archivos del repo. | «La capacidad la gestiona una persona; hoy muestro lo ya construido.» |
| Se acaba el tiempo | Salta el Prompt 4 y los cuidados; conserva Prompt 0, modelo y puerta de aprobación. | — |

---

## 6. Preguntas probables (respuestas cortas y honestas)

1. **¿Esto reemplaza a los desarrolladores?** No. El agente ejecuta tareas acotadas; una persona define, aprueba y revisa (la especificación del reporte y el diff lo muestran).
2. **¿Cuánto tiempo o dinero ahorra?** No lo sabemos: **no hay una línea base manual**. Propuesta: medir en una sesión práctica con la misma tarea hecha de forma habitual y con el agente (tiempo hasta el primer reporte publicado, pasos manuales evitados, defectos detectados antes de publicar, cobertura de documentación, tiempo de revisión del diff). No citamos casos de clientes.
3. **¿Qué licencias necesito?** Son tres productos distintos: **GitHub Copilot** (suscripción de GitHub; en organizaciones, algunas capacidades —p. ej. servidores MCP— las controla una política del administrador), **Copilot en Fabric/Power BI** (habilitado por defecto con capacidades de pago F2 o superior; consume capacidad; varias funciones en preview) y **Microsoft 365 Copilot** (otro producto). Confírmenlo con sus administradores.
4. **¿Qué ve el modelo de IA de mis datos?** Hoy: datos sintéticos. Los metadatos y resultados que el agente lee viajan al proveedor del modelo; la documentación del MCP advierte de no compartir sesiones de chat con información sensible y de hacer respaldo del modelo. Definan la política antes de usar entornos reales.
5. **¿Es seguro? ¿Puede romper algo?** Las reglas guían, pero no son un control técnico. Controlan: los permisos de su identidad, la aprobación de comandos en VS Code, y Git (diff y reversión). Por eso se usa un workspace de pruebas.
6. **¿Funciona con modelos que ya tenemos (Power BI Desktop, PBIP, Analysis Services)?** El servidor MCP local trabaja con modelos en Power BI Desktop, en un workspace de Fabric y con archivos TMDL/PBIP. **Analysis Services no se probó en esta demo**: verifíquenlo en la documentación y en una sesión práctica.
7. **¿Por qué no se construye el reporte en vivo?** Porque tardó cerca de 23 min de agente en un ensayo (con aprobación humana); no cabe en 8 min. Se muestra prearmado.
8. **¿El servidor MCP es GA?** El **local** es GA y el **hospedado** está en preview, según la documentación. Para modelos en un workspace, la documentación recomienda el hospedado; aquí se usa el local porque trabaja con archivos TMDL en disco. No registren los dos a la vez.
9. **¿Qué es Fabric Apps / Rayfin?** Una rama opcional en **preview**: apps de datos (React + TypeScript) creadas con la CLI de Rayfin. Requiere que un administrador habilite el workload y una región compatible. Confirmen los comandos en su versión.
10. **¿Por qué los prompts están en inglés?** Los skills están escritos en inglés y, en nuestra experiencia, funcionan mejor así; las notas y la conversación pueden ser en español. Verifíquenlo con su propio equipo.
11. **¿Qué modelo de IA uso?** Uno de razonamiento profundo; la documentación del MCP lo recomienda.
12. **¿Dónde consigo los skills?** En el repositorio público `microsoft/skills-for-fabric` (ver pestaña Referencias). Verifiquen la versión: el contenido cambia.

---

## 7. Lista de verificación previa

### El día anterior
- [ ] **Ensayo completo** de los Prompts 0 a 6 con los nombres genéricos (o los tuyos) en un entorno de pruebas.
- [ ] Capacidad de Fabric **activa**, verificada por una **persona** (el agente no la opera; no la pauses ni la reanudes durante la demo).
- [ ] Workspace `ws-ia-dev` con el lakehouse, el notebook, el pipeline (con una ejecución exitosa en el historial), el modelo y el reporte publicados.
- [ ] Repo con dos commits: **antes** y **después** del Prompt 4, para mostrar `git diff --stat`.
- [ ] Chats guardados o capturas de los Prompts 1 a 6 (Plan B).
- [ ] Servidor MCP: versión fijada y probada; **EULA revisado y aceptado por una persona**.
- [ ] Revisar el estado de preview/GA en la pestaña «Para replicarlo» (tabla de estado) y las referencias.

### 30 minutos antes
- [ ] Abrir la carpeta del **proyecto** (no una carpeta padre) en VS Code; terminal **PowerShell** nueva.
- [ ] `az account show` muestra la cuenta y el tenant de pruebas; el token de Fabric está vigente (`az account get-access-token --resource https://api.fabric.microsoft.com --query expiresOn`).
- [ ] GitHub Copilot con sesión iniciada; agente en modo **Agent**; modelo de razonamiento profundo elegido.
- [ ] Prompt «Pre-flight» (*Which Fabric skills do you have available in this project? List their names only.*) lista los skills esperados.
- [ ] «MCP: List Servers» muestra el servidor iniciado.
- [ ] Pestañas abiertas y ordenadas: HTML (`#tema=light&v=flow`), workspace, notebook, historial del pipeline, modelo, reporte publicado.
- [ ] Probar los botones **Copiar** de la pestaña «Prompts de ejemplo» en el navegador que usarás.

### 5 minutos antes
- [ ] Cerrar Teams, correo y notificaciones; tamaño de fuente 16+; chat y terminal visibles.
- [ ] Reiniciar el HTML (botón «⟲ Reiniciar» y pausa) para empezar en estado limpio.
- [ ] Respirar: el Prompt 0 es lo único que se ejecuta en vivo.

---

## 8. Qué no decir

- No inventes cifras de ahorro ni comparativas con trabajo manual.
- No cites casos de clientes.
- No afirmes que el MCP funciona con orígenes que no probaste (p. ej. Analysis Services).
- No presentes Fabric Apps como disponible de forma general: está en **preview**.
- No aceptes el EULA del MCP en nombre de nadie.

## 9. Material de apoyo

| Necesitas… | Ve a… |
|---|---|
| Reglas de ejemplo para copiar | HTML · pestaña *Guardarraíles* |
| Checklist, JSON del MCP, comandos de skills y de Rayfin, licencias, estado preview/GA | HTML · pestaña *Para replicarlo* |
| Los prompts 0 a 7 (+ pre-flight y Fabric Apps) con botón **Copiar** | HTML · pestaña *Prompts de ejemplo* |
| Enlaces verificados (HTTP 200 el 12-nov-2026) | HTML · pestaña *Referencias* |

### Prompts 1 a 7 (copia exacta de la pestaña 4)

**Prompt 1**
```text
Using the Fabric skills, create a workspace named ws-ia-dev on the capacity defined in the project rules and a schema-enabled lakehouse named lh_banca in it. Then create a PySpark notebook nb_medallion bound to that lakehouse that generates 200,000 synthetic bank transactions (account_id, txn_ts within the last 90 days, channel ATM/POS/ONLINE/BRANCH, amount, currency USD) into bronze.transactions, cleans and de-duplicates them into silver.transactions, and builds gold.daily_channel_kpis (daily transaction count, total amount and distinct active accounts by channel). Do not run it yet.
```

**Prompt 2**
```text
Create a Fabric Data Factory data pipeline (not a deployment pipeline) named pl_medallion that runs nb_medallion, run it, and confirm through OneLake that the bronze, silver and gold tables exist.
```

**Prompt 3**
```text
Create a Direct Lake semantic model sm_kpis on gold.daily_channel_kpis in lh_banca. Use Direct Lake on the SQL endpoint. Use friendly column names, hide the raw numeric columns, and add measures Total Amount, Transactions and Avg Ticket with descriptions and format strings. Save it as TMDL under models/ in this local repo (do not use Fabric Git integration), publish it to ws-ia-dev, refresh it and validate it with a DAX query by channel.
```

**Prompt 4**
```text
Review sm_kpis against modeling best practices and naming conventions. Apply the fixes you are confident about and list the rest. Then add a Spanish translation for all tables, columns and measures.
```
Después, en la terminal: `git diff --stat`.

**Prompt 5**
```text
Plan a one-page executive report named rpt_ejecutivo on sm_kpis for the head of retail banking. Write the spec to _brief/report-spec.md and show it to me before building anything.
```

**Prompt 6**
```text
Approved. Build it as PBIR under reports/, validate it, publish it to ws-ia-dev bound to sm_kpis, and give me the URL.
```

**Prompt 7 (opcional)**
```text
Add a Channel slicer to rpt_ejecutivo, then validate and republish.
```
*Variante útil si los datos sintéticos tienen días parciales:* `End the trend and the 30-day windows on the last complete day, then validate and republish.`

**Opcional · Fabric Apps (preview)** — adaptado de la guía de Learn
```text
Set up a new Fabric App project called "app-banca".

1. Run: npx -y @microsoft/create-rayfin@latest --project-name app-banca --template blankapp
2. Open the scaffolded project directory and read any copilot-instructions.md or agent guidance it includes.
3. Explore the project structure and understand the Rayfin app framework.
4. Run: npm run dev
5. Make the changes I ask for next.
6. Show me the result of `npx rayfin up --dry-run` first; deploy with `npx rayfin up` only after I approve.
```

## 10. Después de la demo
- Si la capacidad se activó solo para la sesión, pausarla es una **decisión humana** posterior; el agente no lo hace.
- Si el workspace de pruebas ya no se necesita, elimínalo manualmente. No elimines el que contenga el modelo y el reporte hasta terminar las preguntas.
- Anota las preguntas que no pudiste responder para convertirlas en tema de la sesión práctica.
