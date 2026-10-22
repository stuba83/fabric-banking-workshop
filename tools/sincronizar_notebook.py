"""Render the self-contained Fabric notebook from the reusable source module."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE_PATH = ROOT / "notebooks" / "ingesta_bronce.py"
NOTEBOOK_PATH = ROOT / "notebooks" / "02_ingesta_bronce.ipynb"

INTRO = """# Sesión 2 — Ingesta Bronze

Este notebook realiza la carga CSV → Delta; el pipeline de Data Factory solo
orquesta la ejecución de este notebook. Los seis CSV deben estar previamente
cargados en `Files/bronze/banca_sintetica` del Lakehouse predeterminado.

Antes de ejecutar, fija los parámetros a los valores de tu entorno (por ejemplo,
`AB_Lakehouse`, `AB`, `SI`). El Lakehouse predeterminado debe estar adjunto a este
notebook en el mismo workspace. No se cambia la base de datos actual.

El preflight valida hash SHA-256, encabezados, ancho y cantidad de filas de todas
las fuentes antes de la primera escritura. Bronze conserva cada columna como
texto, incluidos blancos, espacios, duplicados y anomalías; aquí no se castea,
limpia ni deduplica. `creditos.csv` queda excluido.

`SI` autoriza reemplazar únicamente las seis tablas con el prefijo elegido.
Las escrituras Delta de varias tablas no son atómicas: si una falla, las tablas
anteriores podrían haberse reemplazado. Corrige el problema y vuelve a ejecutar
el lote completo. No es una estrategia de lectura escalable para CSV de varios
GB; este conjunto didáctico completo es menor de 7 MB.
"""


def _markdown_cell(cell_id: str, text: str) -> dict[str, object]:
    return {
        "cell_type": "markdown",
        "id": cell_id,
        "metadata": {},
        "source": text.splitlines(keepends=True),
    }


def _code_cell(
    cell_id: str,
    text: str,
    metadata: dict[str, object] | None = None,
) -> dict[str, object]:
    return {
        "cell_type": "code",
        "execution_count": None,
        "id": cell_id,
        "metadata": metadata or {},
        "outputs": [],
        "source": text.splitlines(keepends=True),
    }


def render_notebook() -> str:
    source = SOURCE_PATH.read_text(encoding="utf-8")
    parameter_cell = (
        "p_lakehouse_esperado = ''\n"
        "p_prefijo = ''\n"
        "p_confirmar_reemplazo = 'NO'\n"
    )
    execution_cell = (
        "import notebookutils\n"
        "\n"
        "resultado = ejecutar_ingesta(\n"
        "    spark,\n"
        "    notebookutils.runtime.context,\n"
        "    p_lakehouse_esperado,\n"
        "    p_prefijo,\n"
        "    p_confirmar_reemplazo,\n"
        ")\n"
    )
    notebook = {
        "cells": [
            _markdown_cell("session2-intro", INTRO),
            _code_cell(
                "session2-parameters",
                parameter_cell,
                {"tags": ["parameters"]},
            ),
            _code_cell("session2-definitions", source),
            _code_cell("session2-execution", execution_cell),
        ],
        "metadata": {
            "kernelspec": {
                "display_name": "Synapse PySpark",
                "language": "Python",
                "name": "synapse_pyspark",
            },
            "language_info": {"name": "python"},
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }
    return json.dumps(notebook, ensure_ascii=False, indent=1) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="fail if the notebook is missing or differs from the rendered source",
    )
    args = parser.parse_args()
    expected = render_notebook()

    if args.check:
        if not NOTEBOOK_PATH.is_file():
            print(f"Notebook is missing: {NOTEBOOK_PATH}", file=sys.stderr)
            return 1
        observed = NOTEBOOK_PATH.read_text(encoding="utf-8")
        if observed != expected:
            print(f"Notebook is stale: {NOTEBOOK_PATH}", file=sys.stderr)
            return 1
        print("Notebook is synchronized.")
        return 0

    NOTEBOOK_PATH.parent.mkdir(parents=True, exist_ok=True)
    with NOTEBOOK_PATH.open("w", encoding="utf-8", newline="\n") as notebook_file:
        notebook_file.write(expected)
    print(f"Rendered {NOTEBOOK_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
