# Requisitos del ambiente de laboratorio

**Entrenamiento:** Microsoft Fabric — Etapa 1, ingeniería de datos  
**Audiencia:** Ingenieros de datos  
**Preparado:** 22 de octubre de 2026  
**Responsable de habilitación:** por designar

## Objetivo

Habilitar un entorno de práctica aislado para los workshops de Microsoft Fabric. El equipo trabajará en un único workspace compartido con datos sintéticos; no se deben usar datos, credenciales ni conexiones de producción de una entidad real.

## Requisitos del taller

| Área | Requisito |
|---|---|
| Capacidad | Usar una capacidad **Fabric Trial nueva para el laboratorio**, si está disponible en el tenant. Debe estar habilitada y activa durante las sesiones prácticas. |
| Aislamiento | Mantener el laboratorio separado de los workspaces productivos y de otros proyectos. No conectar fuentes productivas ni depender de artefactos existentes. |
| Workspace | Crear **un único workspace compartido** para los participantes, asignado a la capacidad Trial. Nombre sugerido: `LAB-Fabric-Banca`. |
| Usuarios | Confirmar que los participantes pueden iniciar sesión con sus cuentas corporativas y abrir el workspace. |
| Licencias | Cada participante debe tener una **licencia Power BI Pro activa y asignada a su cuenta corporativa**, ya que al finalizar el recorrido deberá crear reportes de Power BI. La capacidad Fabric Trial no sustituye este requisito del taller. |
| Permisos | Asignar a cada participante el rol **Member como mínimo, o Admin**, en el workspace de laboratorio. El rol Contributor no cumple el requisito de este entrenamiento. Designar un administrador del laboratorio para gestionar acceso y configuración. |
| Organización | Cada participante debe **crear y usar su propia carpeta dentro del workspace** y mantener allí sus artefactos. Además, debe usar una **nomenclatura propia, consistente y distinguible de la de los demás participantes** para identificarlos, por ejemplo `AB_Lakehouse`, `AB_Notebook`, `AB_Pipeline`, `AB_Modelo` y `AB_Reporte`. La nomenclatura no sustituye el uso de la carpeta individual. |
| Datos | Usar exclusivamente el dataset **sintético** incluido en este repositorio. No cargar datos personales, información confidencial ni registros de entidades reales. |
| Artefactos | Poder crear y ejecutar los artefactos previstos para las prácticas: Lakehouse, notebook, pipeline y modelo semántico. **Cada participante deberá crear reportes de Power BI al finalizar el recorrido.** |
| Acceso | Disponer de acceso al portal de Microsoft Fabric desde el navegador y de conectividad corporativa para trabajar durante las sesiones virtuales. |

Los requisitos de Pro y Member/Admin se establecen para este taller; no describen los permisos mínimos de todas las funciones de Fabric. Usar únicamente un entorno aislado de práctica, ya que Member y Admin permiten acciones sobre el contenido compartido.

## Validaciones que debe completar el administrador del tenant

Antes de la primera práctica, el administrador de Fabric/Power BI de la organización debe confirmar:

1. Que el uso de Fabric Trial está permitido por las políticas del tenant y que la capacidad Trial puede asignarse al workspace de laboratorio.
2. Que el workspace está efectivamente asignado a esa capacidad y que la capacidad no está vencida, pausada ni bloqueada.
3. Que cada participante tiene una **licencia Power BI Pro activa** y rol **Member o Admin** en el workspace. Como prueba de acceso, **cada usuario debe iniciar sesión con su propia cuenta, crear su carpeta individual dentro del workspace y crear allí un artefacto de prueba con su nomenclatura**. No basta con que el administrador cree las carpetas por ellos.
4. Que las políticas de seguridad del tenant permiten las experiencias de Fabric necesarias para el laboratorio (Lakehouse, notebooks, pipelines, modelo semántico y reportes de Power BI). Si alguna experiencia está restringida, confirmar la alternativa antes de la sesión.
5. Que el entorno y la capacidad tienen vigencia suficiente para las prácticas previstas. Si la Trial no está disponible o no puede cubrir el laboratorio, coordinar con el administrador una alternativa antes de agendar las sesiones prácticas.

## Configuración sugerida

- Un workspace compartido, una carpeta y un Lakehouse por participante, y un administrador designado.
- Cada participante crea su propia carpeta y trabaja dentro de ella con artefactos identificados mediante su nomenclatura; no se requiere un workspace independiente por persona.
- Mantener únicamente los artefactos necesarios para los ejercicios y limpiarlos al concluir el entrenamiento.
- Compartir con el equipo el nombre del workspace, instrucciones de acceso y contacto del administrador antes de la primera sesión.

## Fuera del alcance del ambiente Trial

**Copilot en Fabric no forma parte de los requisitos de este laboratorio:** no está soportado en la capacidad Trial del laboratorio. Una demostración opcional de Copilot requiere un entorno compatible separado; no se debe configurar el laboratorio asumiendo que Copilot estará habilitado.

## Checklist de preparación

- [ ] Administrador del laboratorio designado.
- [ ] Trial habilitada y asignada al workspace `LAB-Fabric-Banca`.
- [ ] Workspace aislado creado y accesible por los participantes.
- [ ] Licencia **Power BI Pro activa** verificada para cada participante.
- [ ] Rol **Member o Admin** verificado para cada participante en el workspace.
- [ ] Cada usuario creó su propia carpeta dentro del workspace usando su cuenta.
- [ ] Cada usuario creó un artefacto de prueba dentro de su carpeta con su nomenclatura.
- [ ] Políticas del tenant verificadas para los ejercicios de Power BI y Fabric.
- [ ] Acceso a Lakehouse, notebooks, pipelines, modelos semánticos y creación de reportes de Power BI comprobado.
- [ ] Dataset sintético cargado o listo para cargar.
- [ ] Confirmado que no se usarán datos ni conexiones de producción.

> Estos requisitos describen el entorno mínimo propuesto para el entrenamiento; el administrador de la organización debe validar la configuración final conforme a las políticas del tenant.
