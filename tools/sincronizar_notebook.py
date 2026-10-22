"""Render the self-contained Fabric notebooks from their reusable source modules."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

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


INTRO_PLATA = """# Sesión 3 — Capa plata y tabla oro

Este notebook transforma las seis tablas Bronze de la Sesión 2 en tablas Silver
tipadas y publica una tabla Gold de consumo; el pipeline de Data Factory solo
orquesta su ejecución después de la ingesta. Las tablas Bronze no se modifican.

Antes de ejecutar, fija los parámetros a los valores de tu entorno (por ejemplo,
`AB_Lakehouse`, `AB`, `SI`). El Lakehouse predeterminado debe estar adjunto a este
notebook, en el mismo workspace, con las seis tablas Bronze del mismo prefijo.

El notebook valida primero las tablas Bronze, aplica los tipos, separa las copias
exactas y los registros inválidos (cada uno con un único motivo), y comprueba los
controles esperados. Si algo falla, no escribe nada. Después escribe seis tablas
Silver, dos tablas de auditoría (cuarentena y duplicadas) y una tabla Gold, y
verifica el conteo, el esquema y el contenido de cada una antes de informar
`status: success`.

`SI` autoriza reemplazar únicamente las nueve tablas con el prefijo elegido. Las
escrituras Delta de varias tablas no son atómicas: si una falla, las anteriores
podrían haberse reemplazado. Corrige el problema y vuelve a ejecutar el lote
completo. Las tablas pequeñas se leen en la memoria del proceso conductor por
claridad didáctica; no es un patrón para GB o TB.
"""


@dataclass(frozen=True)
class NotebookSpec:
    source_path: Path
    notebook_path: Path
    cell_prefix: str
    intro: str
    execution_cell: str


NOTEBOOKS = (
    NotebookSpec(
        source_path=ROOT / "notebooks" / "ingesta_bronce.py",
        notebook_path=ROOT / "notebooks" / "02_ingesta_bronce.ipynb",
        cell_prefix="session2",
        intro=INTRO,
        execution_cell=(
            "import notebookutils\n"
            "\n"
            "resultado = ejecutar_ingesta(\n"
            "    spark,\n"
            "    notebookutils.runtime.context,\n"
            "    p_lakehouse_esperado,\n"
            "    p_prefijo,\n"
            "    p_confirmar_reemplazo,\n"
            ")\n"
        ),
    ),
    NotebookSpec(
        source_path=ROOT / "notebooks" / "plata_silver.py",
        notebook_path=ROOT / "notebooks" / "03_plata_silver.ipynb",
        cell_prefix="session3",
        intro=INTRO_PLATA,
        execution_cell=(
            "import notebookutils\n"
            "\n"
            "resultado = ejecutar_plata(\n"
            "    spark,\n"
            "    notebookutils.runtime.context,\n"
            "    p_lakehouse_esperado,\n"
            "    p_prefijo,\n"
            "    p_confirmar_reemplazo,\n"
            ")\n"
        ),
    ),
)


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


def render_notebook(spec: NotebookSpec) -> str:
    source = spec.source_path.read_text(encoding="utf-8")
    parameter_cell = (
        "p_lakehouse_esperado = ''\n"
        "p_prefijo = ''\n"
        "p_confirmar_reemplazo = 'NO'\n"
    )
    notebook = {
        "cells": [
            _markdown_cell(f"{spec.cell_prefix}-intro", spec.intro),
            _code_cell(
                f"{spec.cell_prefix}-parameters",
                parameter_cell,
                {"tags": ["parameters"]},
            ),
            _code_cell(f"{spec.cell_prefix}-definitions", source),
            _code_cell(f"{spec.cell_prefix}-execution", spec.execution_cell),
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
        help="fail if a notebook is missing or differs from its rendered source",
    )
    args = parser.parse_args()

    if args.check:
        failed = False
        for spec in NOTEBOOKS:
            if not spec.notebook_path.is_file():
                print(f"Notebook is missing: {spec.notebook_path}", file=sys.stderr)
                failed = True
            elif spec.notebook_path.read_text(encoding="utf-8") != render_notebook(spec):
                print(f"Notebook is stale: {spec.notebook_path}", file=sys.stderr)
                failed = True
        if failed:
            return 1
        print("Notebooks are synchronized.")
        return 0

    for spec in NOTEBOOKS:
        spec.notebook_path.parent.mkdir(parents=True, exist_ok=True)
        with spec.notebook_path.open("w", encoding="utf-8", newline="\n") as notebook_file:
            notebook_file.write(render_notebook(spec))
        print(f"Rendered {spec.notebook_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
