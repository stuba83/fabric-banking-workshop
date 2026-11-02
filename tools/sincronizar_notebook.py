"""Render the self-contained Fabric notebooks from their reusable source modules."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import notebook_percent
from notebook_percent import NotebookPercent


ROOT = Path(__file__).resolve().parents[1]
BONUS = ROOT / "notebooks" / "bonus_ml"

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


# Notebooks narrativos del bonus de ML, escritos en formato percent (# %%).
PERCENT_NOTEBOOKS: tuple[NotebookPercent, ...] = (
    NotebookPercent(BONUS / "b1_preparacion_datos.py", BONUS / "B1_preparacion_datos.ipynb", "bonus-b1"),
    NotebookPercent(BONUS / "b2_entrenamiento_mlflow.py", BONUS / "B2_entrenamiento_mlflow.ipynb", "bonus-b2"),
    NotebookPercent(BONUS / "b3_registro_puntuacion.py", BONUS / "B3_registro_puntuacion.ipynb", "bonus-b3"),
    NotebookPercent(BONUS / "b4_mlops.py", BONUS / "B4_mlops.ipynb", "bonus-b4"),
    NotebookPercent(BONUS / "b5_ia_en_notebooks.py", BONUS / "B5_ia_en_notebooks.ipynb", "bonus-b5"),
    NotebookPercent(BONUS / "b6_anomalias_en_linea.py", BONUS / "B6_anomalias_en_linea.ipynb", "bonus-b6"),
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


def _esperados() -> dict[Path, str]:
    esperados = {spec.notebook_path: render_notebook(spec) for spec in NOTEBOOKS}
    for nb in PERCENT_NOTEBOOKS:
        esperados[nb.destino] = notebook_percent.renderizar(nb.fuente, nb.prefijo)
    return esperados


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="fail if a notebook is missing or differs from its rendered source",
    )
    args = parser.parse_args()
    esperados = _esperados()

    if args.check:
        failed = False
        for ruta, texto in esperados.items():
            if not ruta.is_file():
                print(f"Notebook is missing: {ruta}", file=sys.stderr)
                failed = True
            elif ruta.read_text(encoding="utf-8") != texto:
                print(f"Notebook is stale: {ruta}", file=sys.stderr)
                failed = True
        if failed:
            return 1
        print("Notebooks are synchronized.")
        return 0

    for ruta, texto in esperados.items():
        ruta.parent.mkdir(parents=True, exist_ok=True)
        with ruta.open("w", encoding="utf-8", newline="\n") as notebook_file:
            notebook_file.write(texto)
        print(f"Rendered {ruta}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
