"""Convierte un notebook escrito en formato `percent` (`# %%`) en un .ipynb de Fabric.

Formato de la fuente:

    # %% [markdown]
    # Texto en Markdown; cada linea empieza con "# ".

    # %% parameters
    p_prefijo = ''

    # %% embed ml_actividad.py

    # %%
    codigo normal

`embed` inserta, como una celda de codigo, el contenido de un archivo que esta
junto a la fuente. Asi el notebook importable es autocontenido y el mismo codigo
se prueba fuera de Fabric.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path


MARCADOR = re.compile(r"^# %%(?:[ \t]+(.*?))?[ \t]*$")


@dataclass(frozen=True)
class Celda:
    tipo: str  # markdown, parameters, embed o code
    argumento: str
    contenido: str


def parsear(texto: str, origen: str = "<texto>") -> list[Celda]:
    celdas: list[Celda] = []
    tipo: str | None = None
    argumento = ""
    lineas: list[str] = []

    def cerrar() -> None:
        if tipo is None:
            if any(linea.strip() for linea in lineas):
                raise ValueError(f"{origen}: expected a '# %%' marker before any content")
            return
        celdas.append(Celda(tipo, argumento, "\n".join(lineas).strip("\n")))

    for numero, linea in enumerate(texto.splitlines(), start=1):
        encontrada = MARCADOR.match(linea)
        if encontrada is None:
            lineas.append(linea)
            continue
        cerrar()
        lineas = []
        cabecera = (encontrada.group(1) or "").strip()
        if cabecera == "[markdown]":
            tipo, argumento = "markdown", ""
        elif cabecera == "parameters":
            tipo, argumento = "parameters", ""
        elif cabecera.startswith("embed "):
            tipo, argumento = "embed", cabecera[len("embed "):].strip()
        elif cabecera == "":
            tipo, argumento = "code", ""
        else:
            raise ValueError(f"{origen}:{numero}: expected a known cell header; observed {cabecera!r}")
    cerrar()
    if not celdas:
        raise ValueError(f"{origen}: expected at least one cell; observed none")
    return celdas


def _markdown(contenido: str, origen: str) -> str:
    salida = []
    for linea in contenido.splitlines():
        if linea == "#":
            salida.append("")
        elif linea.startswith("# "):
            salida.append(linea[2:])
        else:
            raise ValueError(f"{origen}: expected markdown lines starting with '# '; observed {linea!r}")
    return "\n".join(salida)


def _celdas_ipynb(ruta: Path, prefijo: str) -> list[dict[str, object]]:
    texto = ruta.read_text(encoding="utf-8")
    resultado: list[dict[str, object]] = []
    for indice, celda in enumerate(parsear(texto, ruta.name)):
        identificador = f"{prefijo}-{indice:02d}"
        if celda.tipo == "markdown":
            cuerpo = _markdown(celda.contenido, f"{ruta.name} cell {indice}")
            resultado.append(
                {
                    "cell_type": "markdown",
                    "id": identificador,
                    "metadata": {},
                    "source": (cuerpo + "\n").splitlines(keepends=True),
                }
            )
            continue
        if celda.tipo == "embed":
            cuerpo = (ruta.parent / celda.argumento).read_text(encoding="utf-8")
            if not cuerpo.endswith("\n"):
                cuerpo += "\n"
        else:
            if not celda.contenido.strip():
                raise ValueError(f"{ruta.name} cell {indice}: expected code; observed an empty cell")
            cuerpo = celda.contenido + "\n"
        metadatos: dict[str, object] = {"tags": ["parameters"]} if celda.tipo == "parameters" else {}
        resultado.append(
            {
                "cell_type": "code",
                "execution_count": None,
                "id": identificador,
                "metadata": metadatos,
                "outputs": [],
                "source": cuerpo.splitlines(keepends=True),
            }
        )
    return resultado


def renderizar(ruta: Path, prefijo: str) -> str:
    cuaderno = {
        "cells": _celdas_ipynb(ruta, prefijo),
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
    return json.dumps(cuaderno, ensure_ascii=False, indent=1) + "\n"


def celdas_codigo(ruta: Path) -> list[str]:
    """Texto de cada celda de codigo, en orden, para ejecutarlas por separado en pruebas locales."""
    celdas = []
    for celda in parsear(ruta.read_text(encoding="utf-8"), ruta.name):
        if celda.tipo == "embed":
            celdas.append((ruta.parent / celda.argumento).read_text(encoding="utf-8"))
        elif celda.tipo in ("code", "parameters"):
            celdas.append(celda.contenido + "\n")
    return celdas


@dataclass(frozen=True)
class NotebookPercent:
    fuente: Path
    destino: Path
    prefijo: str
