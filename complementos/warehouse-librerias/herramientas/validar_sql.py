"""Validación estática de los .sql contra la superficie T-SQL de Fabric Warehouse.

Uso:  python validar_sql.py [carpeta-raiz]
Comprueba (sin conectarse a nada):
  - construcciones NO soportadas o no documentadas para Warehouse (ver README),
  - llaves solo con ALTER TABLE y siempre NOT ENFORCED (PK/UNIQUE además NONCLUSTERED),
  - balance de BEGIN/END, TRY/CATCH, paréntesis y transacciones,
  - cada procedimiento con transacción: ROLLBACK condicionado a @@TRANCOUNT y THROW; en CATCH,
  - THROW precedido de ';', MERGE terminado en ';',
  - objetos referenciados (Lakehouse y Warehouse) que existen en la lista documentada,
  - INSERT con lista de columnas: columnas existentes y misma cantidad que la lista SELECT/VALUES,
  - literales de cadena en ASCII (los scripts viajan por clientes TDS distintos).
Termina con código 1 si hay errores.
"""

import re
import sys
from pathlib import Path

RAIZ = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent
ARCHIVOS = [
    RAIZ / "warehouse" / "01_esquemas_tablas.sql",
    RAIZ / "warehouse" / "02_procedimientos.sql",
    RAIZ / "warehouse" / "03_pruebas.sql",
    RAIZ / "warehouse" / "04_estado_inicial.sql",
    RAIZ / "comparacion" / "comparacion_tsql.sql",
]

TABLAS_LAKEHOUSE = {
    "ab_bronze_transacciones", "ab_silver_clientes", "ab_silver_cuentas", "ab_silver_sucursales",
    "ab_silver_productos", "ab_silver_calendario", "ab_silver_transacciones",
    "ab_silver_transacciones_cuarentena", "ab_silver_transacciones_duplicadas",
    "ab_gold_transacciones_mes_canal",
}

PROHIBIDOS = [
    (r"\bn?varchar\s*\(\s*max\s*\)", None),  # permitido (16 MB); se deja para documentar
    (r"\bnvarchar\b|\bnchar\b|\bntext\b", "tipo Unicode no soportado en tablas (usar varchar)"),
    (r"\bdatetime\b", "datetime no soportado (usar datetime2)"),
    (r"\bsmalldatetime\b|\bdatetimeoffset\b", "tipo de fecha no soportado"),
    (r"\bmoney\b|\bsmallmoney\b", "money no soportado (usar decimal)"),
    (r"\btinyint\b", "tinyint no soportado (usar smallint)"),
    (r"\bxml\b|\bgeography\b|\bgeometry\b|\bimage\b|\bsql_variant\b", "tipo no soportado"),
    (r"@@ROWCOUNT", "@@ROWCOUNT no está documentado para Warehouse (usar COUNT_BIG)"),
    (r"(?s)INSERT\s+INTO\s+#\w+\s*(?:\([^)]*\))?\s*SELECT[^;]*?\bFROM\b|INSERT\s+INTO\s+[\w.]+\s*\([^)]*\)\s*SELECT[^;]*?\bFROM\s+#", "INSERT ... SELECT hacia/desde #temp con datos de otras tablas: error 15816 en Fabric (usar tabla permanente)"),
    (r"\bERROR_LINE\b|\bERROR_PROCEDURE\b|\bERROR_SEVERITY\b|\bERROR_STATE\b", "ERROR_LINE (verificado: no soportado); evitar también las demás ERROR_* salvo NUMBER y MESSAGE"),
    (r"\bXACT_STATE\b|\bXACT_ABORT\b", "XACT_STATE/XACT_ABORT no están documentados para Warehouse"),
    (r"\bCURSOR\b", "cursores no soportados"),
    (r"\bCREATE\s+TRIGGER\b|\bCREATE\s+SYNONYM\b", "triggers/synonyms no soportados"),
    (r"\bSAVE\s+TRAN(SACTION)?\b", "savepoints no soportados"),
    (r"\bFOR\s+XML\b", "FOR XML no soportado"),
    (r"\bSET\s+ROWCOUNT\b", "SET ROWCOUNT no soportado"),
    (r"\bSET\s+TRANSACTION\s+ISOLATION\b", "SET TRANSACTION ISOLATION LEVEL no soportado"),
    (r"\bIDENTITY\b", "IDENTITY no se usa en esta demo"),
    (r"\bDEFAULT\s*\(|\bDEFAULT\s+[\w'\"-]", "constraints DEFAULT no soportadas"),
    (r"\bCHECK\s*\(", "constraints CHECK no soportadas"),
    (r"\bMATERIALIZED\s+VIEW\b", "vistas materializadas no soportadas"),
    (r"\bDECLARE\s+@\w+\s+TABLE\b", "variables de tabla: no documentadas (usar #temp)"),
    (r"\bBULK\s+INSERT\b", "BULK INSERT no soportado"),
    (r"##\w+", "tablas temporales globales no soportadas"),
    (r"\bPREDICT\s*\(", "PREDICT no soportado"),
    (r"\bSTATISTICS\s+TIME\b|\bSTATISTICS\s+IO\b", "SET STATISTICS no se usa"),
]


def quitar_comentarios_y_literales(texto):
    """Devuelve (codigo, literales). Reemplaza literales por '' y comentarios por espacio."""
    literales = []
    salida = []
    i, n = 0, len(texto)
    while i < n:
        c = texto[i]
        if texto.startswith("--", i):
            j = texto.find("\n", i)
            i = n if j < 0 else j
        elif texto.startswith("/*", i):
            j = texto.find("*/", i + 2)
            if j < 0:
                raise ValueError("comentario de bloque sin cerrar")
            salida.append(" " * 1)
            i = j + 2
        elif c == "'":
            j = i + 1
            while True:
                k = texto.find("'", j)
                if k < 0:
                    raise ValueError("literal sin cerrar")
                if texto.startswith("''", k):
                    j = k + 2
                    continue
                break
            literales.append(texto[i + 1:k])
            salida.append("''")
            i = k + 1
        else:
            salida.append(c)
            i += 1
    return "".join(salida), literales


def lotes(texto):
    return [b for b in re.split(r"(?im)^\s*GO\s*$", texto) if b.strip()]


def parentesis_balanceados(codigo):
    nivel = 0
    for c in codigo:
        nivel += (c == "(") - (c == ")")
        if nivel < 0:
            return False
    return nivel == 0


def cuerpo_parentesis(codigo, inicio):
    """Texto entre el '(' que está en codigo[inicio] y su ')' de cierre."""
    nivel = 0
    for j in range(inicio, len(codigo)):
        if codigo[j] == "(":
            nivel += 1
        elif codigo[j] == ")":
            nivel -= 1
            if nivel == 0:
                return codigo[inicio + 1:j], j
    raise ValueError("paréntesis sin cerrar")


def dividir_nivel0(texto):
    partes, nivel, actual = [], 0, []
    for c in texto:
        if c == "(":
            nivel += 1
        elif c == ")":
            nivel -= 1
        if c == "," and nivel == 0:
            partes.append("".join(actual).strip())
            actual = []
        else:
            actual.append(c)
    if "".join(actual).strip():
        partes.append("".join(actual).strip())
    return partes


def main():
    errores, avisos = [], []

    def error(archivo, mensaje):
        errores.append(f"{archivo.name}: {mensaje}")

    # 1. Esquema declarado en 01 (tablas y columnas)
    codigo01, _ = quitar_comentarios_y_literales(ARCHIVOS[0].read_text(encoding="utf-8"))
    tablas = {}
    for m in re.finditer(r"CREATE\s+TABLE\s+(\w+\.\w+)\s*\(", codigo01, re.I):
        cuerpo, _ = cuerpo_parentesis(codigo01, m.end() - 1)
        columnas = []
        for definicion in dividir_nivel0(cuerpo):
            columnas.append(definicion.split()[0].lower())
            if re.search(r"\b(CONSTRAINT|PRIMARY\s+KEY|FOREIGN\s+KEY|UNIQUE)\b", definicion, re.I):
                error(ARCHIVOS[0], f"{m.group(1)}: llave dentro de CREATE TABLE (Fabric exige ALTER TABLE)")
        tablas[m.group(1).lower()] = columnas
    for m in re.finditer(r"ALTER\s+TABLE\s+[\w.]+\s+ADD\s+CONSTRAINT\s+(\w+)\s+(.*?);", codigo01, re.I | re.S):
        definicion = m.group(2)
        if not re.search(r"NOT\s+ENFORCED\s*$", definicion.strip(), re.I):
            error(ARCHIVOS[0], f"constraint {m.group(1)} sin NOT ENFORCED")
        if re.match(r"(PRIMARY\s+KEY|UNIQUE)", definicion.strip(), re.I) and not re.search(r"NONCLUSTERED", definicion, re.I):
            error(ARCHIVOS[0], f"constraint {m.group(1)} sin NONCLUSTERED")
    esquemas = {t.split(".")[0] for t in tablas}
    procedimientos = set()
    codigo02, _ = quitar_comentarios_y_literales(ARCHIVOS[1].read_text(encoding="utf-8"))
    for m in re.finditer(r"CREATE\s+OR\s+ALTER\s+PROCEDURE\s+(\w+\.\w+)", codigo02, re.I):
        procedimientos.add(m.group(1).lower())
    objetos_wh = set(tablas) | procedimientos

    totales = {"lotes": 0, "tablas": len(tablas), "procedimientos": len(procedimientos)}
    for archivo in ARCHIVOS:
        texto = archivo.read_text(encoding="utf-8")
        try:
            codigo, literales = quitar_comentarios_y_literales(texto)
        except ValueError as exc:
            error(archivo, str(exc))
            continue
        for literal in literales:
            if not literal.isascii():
                error(archivo, f"literal con caracteres no ASCII: {literal[:50]!r}")
        for patron, motivo in PROHIBIDOS:
            if motivo is None:
                continue
            for m in re.finditer(patron, codigo, re.I):
                linea = codigo[:m.start()].count("\n") + 1
                error(archivo, f"línea ~{linea}: {motivo} -> {m.group(0)!r}")

        for numero, lote in enumerate(lotes(codigo), 1):
            totales["lotes"] += 1
            if not parentesis_balanceados(lote):
                error(archivo, f"lote {numero}: paréntesis desbalanceados")
            inicios = len(re.findall(r"\bBEGIN\b(?!\s+TRAN)", lote, re.I))
            finales = len(re.findall(r"\bEND\b", lote, re.I))
            casos = len(re.findall(r"\bCASE\b", lote, re.I))
            if inicios + casos != finales:
                error(archivo, f"lote {numero}: BEGIN({inicios}) + CASE({casos}) != END({finales})")
            if len(re.findall(r"\bBEGIN\s+TRY\b", lote, re.I)) != len(re.findall(r"\bEND\s+TRY\b", lote, re.I)):
                error(archivo, f"lote {numero}: TRY desbalanceado")
            if len(re.findall(r"\bBEGIN\s+CATCH\b", lote, re.I)) != len(re.findall(r"\bEND\s+CATCH\b", lote, re.I)):
                error(archivo, f"lote {numero}: CATCH desbalanceado")
            if re.search(r"BEGIN\s+TRAN(SACTION)?[^;]*;.*BEGIN\s+TRAN(SACTION)?[^;]*;", lote, re.I | re.S) and \
                    archivo.name == "02_procedimientos.sql" and "CREATE OR ALTER" not in lote.upper():
                error(archivo, f"lote {numero}: dos BEGIN TRANSACTION en el mismo lote")
            es_proc = re.search(r"CREATE\s+OR\s+ALTER\s+PROCEDURE", lote, re.I)
            if es_proc:
                abre = len(re.findall(r"\bBEGIN\s+TRAN(SACTION)?\b", lote, re.I))
                cierra = len(re.findall(r"\bCOMMIT\s+TRAN(SACTION)?\b", lote, re.I))
                if abre != cierra:
                    error(archivo, f"lote {numero}: BEGIN TRANSACTION({abre}) != COMMIT({cierra})")
                if abre > 1:
                    error(archivo, f"lote {numero}: más de una transacción (anidadas no soportadas)")
                if abre:
                    if not re.search(r"BEGIN\s+CATCH\s+IF\s+@@TRANCOUNT\s*>\s*0\s+ROLLBACK\s+TRAN(SACTION)?\s*;", lote, re.I):
                        error(archivo, f"lote {numero}: CATCH sin 'IF @@TRANCOUNT > 0 ROLLBACK TRANSACTION;'")
                if re.search(r"\bBEGIN\s+CATCH\b", lote, re.I) and not re.search(r"THROW\s*;\s*END\s+CATCH", lote, re.I):
                    error(archivo, f"lote {numero}: CATCH sin 'THROW;' final")
                if re.search(r"\bBEGIN\s+TRAN(SACTION)?\b", lote, re.I) is None and "usp_cargar_gold" not in lote:
                    pass
            # THROW con ';' previo (o precedido de IF/BEGIN/ELSE)
            lineas = [l.strip() for l in lote.split("\n") if l.strip()]
            for idx, linea in enumerate(lineas):
                if re.match(r"THROW\b", linea, re.I) and idx > 0:
                    previa = lineas[idx - 1]
                    if re.match(r"IF\b", previa, re.I):
                        previa = lineas[idx - 2] if idx > 1 else ";"
                    if not (previa.endswith(";") or re.search(r"\b(BEGIN|CATCH|ELSE|THEN)$", previa, re.I)):
                        error(archivo, f"lote {numero}: THROW no precedido de ';' ({previa[-40:]!r})")
            for m in re.finditer(r"\bMERGE\b(?!\s*\()", lote, re.I):
                resto = lote[m.start():]
                fin = re.search(r"THEN\s+DELETE\s*;|THEN\s+UPDATE.*?;|;", resto, re.I | re.S)
                if not fin or not resto[:fin.end()].rstrip().endswith(";"):
                    error(archivo, f"lote {numero}: MERGE sin ';' final")
            # tablas del Lakehouse
            for m in re.finditer(r"\bAB_Lakehouse\.dbo\.(\w+)", lote):
                if m.group(1) not in TABLAS_LAKEHOUSE:
                    error(archivo, f"tabla de Lakehouse desconocida: {m.group(1)}")
            for m in re.finditer(r"\b(clientes|cuentas|transacciones|operacion)\.(\w+)", lote, re.I):
                nombre = f"{m.group(1)}.{m.group(2)}".lower()
                if nombre not in objetos_wh:
                    error(archivo, f"objeto de Warehouse desconocido: {nombre}")
            for m in re.finditer(r"\b(?:EXEC|EXECUTE)\s+([\w.]+)", lote, re.I):
                if m.group(1).lower() not in procedimientos and m.group(1).lower() != "sp_executesql":
                    error(archivo, f"EXEC de procedimiento inexistente: {m.group(1)}")

        # INSERT con lista de columnas
        for m in re.finditer(r"\bINSERT\s+INTO\s+(#?[\w.]+)\s*\(", codigo, re.I):
            nombre = m.group(1).lower()
            lista, fin = cuerpo_parentesis(codigo, m.end() - 1)
            columnas = [c.strip().lower() for c in lista.split(",")]
            if nombre in tablas:
                faltan = [c for c in columnas if c not in tablas[nombre]]
                if faltan:
                    error(archivo, f"INSERT {nombre}: columnas inexistentes {faltan}")
            resto = codigo[fin + 1:].lstrip()
            if re.match(r"VALUES\b", resto, re.I):
                inicio = resto.index("(")
                valores, _ = cuerpo_parentesis(resto, inicio)
                if len(dividir_nivel0(valores)) != len(columnas):
                    error(archivo, f"INSERT {nombre}: {len(columnas)} columnas y {len(dividir_nivel0(valores))} valores")
            elif re.match(r"SELECT\b", resto, re.I):
                seleccion = resto[len("SELECT"):]
                m_from = None
                nivel = 0
                for pos, c in enumerate(seleccion):
                    if c == "(":
                        nivel += 1
                    elif c == ")":
                        nivel -= 1
                    elif nivel == 0 and re.match(r"\s+FROM\b", seleccion[pos:], re.I):
                        m_from = pos
                        break
                lista_select = seleccion[:m_from] if m_from is not None else seleccion.split(";")[0]
                lista_select = re.sub(r"^\s*(TOP\s+\d+\s+)", "", lista_select, flags=re.I)
                if len(dividir_nivel0(lista_select)) != len(columnas):
                    error(archivo, f"INSERT {nombre}: {len(columnas)} columnas y {len(dividir_nivel0(lista_select))} expresiones SELECT")

    print(f"Archivos: {len(ARCHIVOS)} | lotes: {totales['lotes']} | tablas: {totales['tablas']} | procedimientos: {totales['procedimientos']}")
    for a in avisos:
        print("AVISO", a)
    if errores:
        for e in errores:
            print("ERROR", e)
        sys.exit(1)
    print("OK: sin errores de validación estática")


if __name__ == "__main__":
    main()
