# Sesión 5 — Cierre: revisión de entregables y siguientes pasos

**Audiencia:** Ingenieros de datos  
**Duración en vivo:** 60 minutos, sin extensión  
**Fecha y horario:** por definir en cada entrenamiento  
**Modalidad:** Revisión guiada de entregables, recorrido de punta a punta y consolidación de dudas

## Resultado esperado

Al cierre, cada participante podrá **explicar y demostrar en su propio ambiente** el recorrido completo —CSV, bronce, plata, oro, modelo semántico y reporte— apoyándose en números que midió él mismo. Las evidencias de las Sesiones 1 a 4 estarán revisadas, los bloqueos acumulados resueltos o documentados, y el equipo tendrá una lista de siguientes pasos con responsable.

La cuenta que debe cuadrar de punta a punta:

```text
72.360 filas bronce
  -  288 copias exactas  -  72 registros inválidos  =  72.000 movimientos plata
72.000 movimientos plata  =  72.000 transacciones en el modelo y en el reporte
```

**Esta sesión no introduce una práctica nueva.** Consolida lo construido, aclara lo que quedó pendiente y prepara el paso del laboratorio a un proyecto real.

## 1. Pre-work

### Estado de partida

Completar los accionables de las Sesiones [1](../sesion-01/guia.md), [2](../sesion-02/guia.md), [3](../sesion-03/guia.md) y [4](../sesion-04/guia.md), o dejar **registrado el bloqueo** de lo que no se pudo terminar, con el mensaje observado y quién lo debe desbloquear. Mantener los [requisitos del laboratorio](../requisitos.md).

### Reejecución de punta a punta

1. Ejecutar el pipeline completo una vez más (ingesta y plata) con los parámetros de siempre y `p_confirmar_reemplazo = SI`.
2. Medir de nuevo, sin copiar los valores esperados: las tablas bronce y plata con T-SQL, y las tres tarjetas del reporte.
3. Comprobar que **nada cambió**: la carga es idempotente, así que los conteos y los montos deben ser los mismos. Si el reporte muestra otra cosa, actualizar el modelo y revisar las relaciones antes de buscar otras causas.

### Preparar el recorrido de cinco minutos

Preparar una explicación breve, con el **linaje del workspace** como apoyo visual, que recorra estos cinco pasos. Cada paso debe incluir **un número medido por el participante**:

| Paso | Qué explicar | Número que se espera ver |
|---|---|---|
| 1. Fuentes | Qué CSV se usan y dónde se cargan | Seis CSV de entrada |
| 2. Bronce | Qué hace la ingesta y por qué conserva los errores como texto | 72.360 filas de transacciones |
| 3. Plata | Qué se limpia, qué se aparta y por qué | 72.000 / 72 en cuarentena / 288 duplicadas |
| 4. Oro y modelo | Para qué sirve la tabla oro y qué entra al modelo | 30 filas en oro; seis tablas en el modelo |
| 5. Reporte y seguridad | A quién aplica la seguridad por filas y a quién no | Rol `Heredia` con 8.971 transacciones |

### Consolidar hallazgos y dudas

- Escribir **tres hallazgos propios**: qué funcionó, qué resultó difícil y qué cambiarías al llevarlo a tu entorno real.
- Traer **hasta tres dudas prioritarias**. El punto focal las consolida y lleva a la sesión **hasta cinco**.

**Preparación orientativa:** 30–45 minutos, además de resolver bloqueos de ambiente.

## 2. Agenda — 60 minutos

| Minutos | Actividad | Resultado |
|---|---|---|
| 00–10 | Matriz de entregables de las Sesiones 1 a 4 | Qué está completo, qué no y quién desbloquea cada pendiente |
| 10–30 | Recorrido de punta a punta, hasta cinco minutos por participante | Cada participante explica el flujo con números propios |
| 30–42 | Bloqueos y dudas consolidadas | Resolver, o asignar responsable y fecha |
| 42–52 | Del laboratorio al proyecto real (sección 3) | Decidir qué temas se llevan al plan del equipo |
| 52–60 | Siguientes pasos, limpieza y cierre | Lista de pasos con responsable y confirmación de qué se conserva |

Si hay más participantes de los que caben en el bloque de recorridos, el equipo elige voluntarios y el resto entrega su guion por escrito al punto focal. Un recorrido que no cabe se completa como accionable. **La sesión no se extiende.**

## 3. Del laboratorio al proyecto real

El laboratorio simplifica a propósito. Estas son las simplificaciones principales y las preguntas que conviene responder antes de llevar el patrón a un proyecto real. Se discuten los temas que el tiempo permita; el resto queda como tarea del equipo.

| Tema | En el laboratorio | En un proyecto real | Pregunta guía |
|---|---|---|---|
| Datos y escala | CSV pequeños leídos en la memoria del proceso conductor | Orígenes reales y volúmenes mayores; las mismas reglas se expresan con Spark (ventanas para deduplicar, anti-joins para las referencias, conversiones seguras de tipos) | ¿Qué volumen y qué ventana de carga tienen las fuentes? |
| Calidad | Reglas y controles dentro del notebook, con una tabla de cuarentena | Reglas y controles como código con pruebas, y un dueño definido para la cuarentena | ¿Quién decide qué se corrige en origen y qué se aparta? |
| Acceso | Un workspace compartido, todos Member o Admin | Grupos por rol, entornos separados y usuarios finales con rol Viewer sobre el contenido publicado | ¿Qué roles reales existen y quién aprueba cada acceso? |
| Operación | Ejecución manual y relanzamiento del lote completo | Programación, monitoreo, alertas y una estrategia de reintentos y recuperación | ¿Qué ocurre si una carga falla de madrugada? Las escrituras no son atómicas |
| Ciclo de vida | Elementos creados a mano, con prefijo propio | Control de versiones y despliegue entre entornos (por ejemplo, integración con Git y pipelines de despliegue) | ¿Cómo se promueve un cambio de desarrollo a producción? |
| Capacidad y costo | Capacidad de prueba de vigencia limitada | Capacidad de pago dimensionada para la carga y su consumo monitoreado | ¿Qué capacidad necesita la carga real y quién vigila el consumo? |

La demostración de **Copilot en Fabric** depende de la capacidad y del tenant, y requiere un entorno compatible distinto del laboratorio. Si el facilitador la muestra, es desde su propio ambiente y **no forma parte de las evidencias**.

Este recorrido no cubre ciencia de datos ni modelos de aprendizaje automático. Tampoco describe una implementación productiva.

## 4. Matriz de entregables

Cada participante lleva su matriz, con el estado real de cada sesión:

| Sesión | Qué debe existir | Estado posible |
|---|---|---|
| 1 | Carga manual, conteos de las vistas previas y evidencias | completa / parcial / pendiente / bloqueada |
| 2 | Pipeline con la ingesta, seis tablas bronce y evidencias | completa / parcial / pendiente / bloqueada |
| 3 | Actividad de plata, nueve tablas, controles medidos con T-SQL y evidencias | completa / parcial / pendiente / bloqueada |
| 4 | Modelo, reporte, dos roles probados, linaje revisado y modelo promovido | completa / parcial / pendiente / bloqueada |
| 5 | Reejecución de punta a punta, recorrido y hallazgos | completa / parcial / pendiente / bloqueada |

**Parcial, pendiente o bloqueada no es un fracaso:** es información. Lo que no puede afirmarse como completo se registra así, con su causa. No se rellenan las evidencias con los valores esperados.

## 5. Después de la sesión

### Qué se conserva y qué se limpia

- Conservar **dentro de la organización** las evidencias completadas, el guion del recorrido y la lista de siguientes pasos. No subirlos a este repositorio público.
- Conservar los artefactos que el equipo quiera reutilizar o revisar de nuevo. Eliminar el resto al concluir el entrenamiento, como indican los [requisitos](../requisitos.md), **solo los propios y de acuerdo con el administrador del laboratorio**.
- No eliminar elementos de otros participantes ni de otros proyectos. La carpeta individual organiza, no aísla permisos.
- La capacidad de prueba tiene vigencia limitada. Si algo debe conservarse más allá de ella, coordinarlo con el administrador antes de que venza.

### Reutilizar el material

Este repositorio permite **repetir todo el recorrido desde cero**: basta un prefijo nuevo y las guías de las Sesiones 1 a 4, en orden. Los notebooks, las pruebas y los controles esperados están incluidos. Antes de reutilizarlo con otro dataset, revisar las reglas y los valores de control, que están fijados al conjunto sintético incluido.

### Siguientes pasos

Registrar en la sesión, con responsable y fecha acordada por el equipo:

| Siguiente paso | Responsable | Fecha |
|---|---|---|
| | | |

## 6. Bloqueos frecuentes

| Síntoma | Revisar |
|---|---|
| El pipeline completo falla al reejecutar | Los bloqueos de las Sesiones 2 y 3, que `p_confirmar_reemplazo` sea `SI` y que el Lakehouse predeterminado sea el propio en ambos notebooks |
| El reporte no coincide tras reejecutar | Los conteos con T-SQL; actualizar el modelo; las relaciones y que la tabla oro y las de auditoría no estén en el modelo |
| Las evidencias de una sesión están incompletas | Marcar el estado real y la causa; no copiar valores esperados |
| La capacidad venció o se limpió por error | Coordinar con el administrador; repetir las Sesiones 2 a 4 con un prefijo nuevo |
| No se llega a explicar los cinco pasos en cinco minutos | Recortar a un número por paso; entregar el guion completo por escrito |

Un bloqueo de identidad, licencia o capacidad no se resuelve ampliando la sesión. El punto focal lo coordina con el administrador.

## Referencias

- [Requisitos del laboratorio](../requisitos.md), [guía del dataset](../../dataset/README.md) y [diccionario de datos](../../dataset/diccionario.md).
- Sesiones anteriores: [1](../sesion-01/guia.md), [2](../sesion-02/guia.md), [3](../sesion-03/guia.md) y [4](../sesion-04/guia.md).
- [Documentación de Microsoft Fabric](https://learn.microsoft.com/en-us/fabric/).

Los controles de esta sesión repiten los de las anteriores y se comprueban en el ambiente de cada participante. Este repositorio no se conecta a ningún tenant ni despliega artefactos automáticamente.
