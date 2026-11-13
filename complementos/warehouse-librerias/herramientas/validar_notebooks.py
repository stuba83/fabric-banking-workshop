"""Valida los notebooks del demo: json.load, estructura nbformat 4.5, ids únicos, sintaxis Python.

    python validar_notebooks.py [carpeta-raiz]

Las órdenes mágicas (%run, %%sql, ...) se sustituyen por `pass` antes de comprobar la sintaxis.
Los marcadores {{WORKSPACE_ID}}, {{FAC_LH_ID}} y {{FAC_ENV_ID}} deben seguir en metadata.dependencies.
"""

import ast
import json
import os
import re
import sys
from pathlib import Path

RAIZ = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent
NOTEBOOKS = sorted(RAIZ.rglob("*.ipynb"))
MARCADORES = {"{{WORKSPACE_ID}}", "{{FAC_LH_ID}}", "{{FAC_ENV_ID}}"}
# Términos a excluir (separados por coma): variable de entorno FAC_TERMINOS_PROHIBIDOS.
PROHIBIDAS = [p.strip() for p in os.environ.get("FAC_TERMINOS_PROHIBIDOS", "").split(",") if p.strip()]


def main():
    errores = []
    if not NOTEBOOKS:
        errores.append("no se encontraron notebooks")
    for ruta in NOTEBOOKS:
        nombre = ruta.relative_to(RAIZ).as_posix()
        texto = ruta.read_text(encoding="utf-8")
        try:
            nb = json.loads(texto)
        except json.JSONDecodeError as exc:
            errores.append(f"{nombre}: JSON inválido: {exc}")
            continue
        if nb.get("nbformat") != 4 or nb.get("nbformat_minor") != 5:
            errores.append(f"{nombre}: se esperaba nbformat 4.5")
        ids = [c.get("id") for c in nb["cells"]]
        if len(ids) != len(set(ids)) or not all(ids):
            errores.append(f"{nombre}: ids de celda repetidos o vacíos")
        meta = nb["metadata"]
        if meta.get("kernelspec", {}).get("name") != "synapse_pyspark":
            errores.append(f"{nombre}: kernel distinto de synapse_pyspark")
        for celda in nb["cells"]:
            fuente = "".join(celda["source"])
            if celda["cell_type"] not in ("markdown", "code"):
                errores.append(f"{nombre}: tipo de celda inesperado")
            if celda["cell_type"] == "code":
                if celda.get("outputs") != [] or celda.get("execution_count") is not None:
                    errores.append(f"{nombre}: celda {celda['id']} con salidas guardadas")
                lineas = ["pass" if l.lstrip().startswith("%") else l for l in fuente.split("\n")]
                try:
                    ast.parse("\n".join(lineas))
                except SyntaxError as exc:
                    errores.append(f"{nombre}: celda {celda['id']}: error de sintaxis línea {exc.lineno}: {exc.msg}")
        usados = set(re.findall(r"\{\{[A-Z_]+\}\}", texto))
        if not usados <= MARCADORES:
            errores.append(f"{nombre}: marcadores desconocidos {usados - MARCADORES}")
        dependencias = meta.get("dependencies", {})
        if "lakehouse" in dependencias and dependencias["lakehouse"]["default_lakehouse_name"] != "FAC_LH_Utils":
            errores.append(f"{nombre}: el Lakehouse predeterminado debe ser FAC_LH_Utils")
        if "AB_Lakehouse" in json.dumps(dependencias):
            errores.append(f"{nombre}: no debe adjuntar AB_Lakehouse como dependencia (solo lectura por código)")
        for palabra in PROHIBIDAS:
            if palabra.lower() in texto.lower():
                errores.append(f"{nombre}: contiene el término prohibido {palabra!r}")
        print(f"{nombre}: {len(nb['cells'])} celdas | marcadores: {sorted(usados) or '-'}")
    if errores:
        print(*["ERROR " + e for e in errores], sep="\n")
        sys.exit(1)
    print(f"OK: {len(NOTEBOOKS)} notebooks válidos")


if __name__ == "__main__":
    main()
