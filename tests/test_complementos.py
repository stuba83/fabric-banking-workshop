from __future__ import annotations

import importlib.util
import json
import re
import sys
import unittest
from html.parser import HTMLParser
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(ROOT / "tools"))

from test_bonus_docs import TERMINOS_PROHIBIDOS as TERMINOS_BASE  # noqa: E402

COMPLEMENTOS = ROOT / "complementos"
REFERENCIAS = ROOT / "docs" / "referencias-complementarias.md"
BONUS_IA = ROOT / "docs" / "bonus-desarrollo-asistido"
GUIAS = [ROOT / "docs" / f"sesion-0{n}" / "guia.md" for n in range(1, 6)]
SUFIJOS_TEXTO = {".md", ".html", ".json", ".ipynb", ".ps1", ".py", ".sql", ".toml", ".txt", ".yml",
                 ".ts", ".tsx", ".mjs", ".css"}

TERMINOS_EXTENDIDOS = re.compile(
    TERMINOS_BASE.pattern
    + r"|caribbean|\bcdb\b|mcaps|mydse|clawpilot|azure-mcaps|lab-fabric-banca|fabdemo|rg-fabric"
    + r"|[A-Za-z]:[\\/]+Users[\\/]|OneDrive",
    re.IGNORECASE,
)
GUID = re.compile(r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b")
GUID_CENTINELA = re.compile(r"^([0-9a-fA-F])\1{7}-(\1{4}-){3}\1{12}$")
CORREO = re.compile(r"[\w.+-]+@[\w-]+\.[A-Za-z]{2,}")
ENLACE = re.compile(r"\]\(([^)\s]+)\)")
ENCABEZADO = re.compile(r"^#{1,6}\s+(.*?)\s*#*\s*$", re.MULTILINE)


def _archivos_de_texto() -> list[Path]:
    ruta = [p for p in COMPLEMENTOS.rglob("*") if p.is_file() and p.suffix.lower() in SUFIJOS_TEXTO]
    ruta += [REFERENCIAS, *sorted(p for p in BONUS_IA.rglob("*") if p.is_file())]
    return ruta


def _leer(ruta: Path) -> str:
    return ruta.read_text(encoding="utf-8")


def _relativa(ruta: Path) -> str:
    return ruta.relative_to(ROOT).as_posix()


def _slug(titulo: str) -> str:
    texto = re.sub(r"[`*_]", "", titulo.strip().lower())
    texto = re.sub(r"[^\w\s-]", "", texto)
    return re.sub(r"\s", "-", texto)


def _anclas(ruta: Path) -> set[str]:
    sin_codigo = re.sub(r"```.*?```", "", _leer(ruta), flags=re.DOTALL)
    return {_slug(t) for t in ENCABEZADO.findall(sin_codigo)}


class _Equilibrio(HTMLParser):
    VACIAS = {"meta", "link", "br", "hr", "img", "input", "path", "circle", "rect", "line", "polygon", "polyline",
              "ellipse", "use", "stop", "source", "col", "base", "wbr", "area", "param", "track", "embed"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.pila: list[str] = []
        self.errores: list[str] = []

    def handle_starttag(self, tag, attrs) -> None:
        if tag not in self.VACIAS:
            self.pila.append(tag)

    def handle_endtag(self, tag) -> None:
        if tag in self.VACIAS:
            return
        if self.pila and self.pila[-1] == tag:
            self.pila.pop()
        else:
            self.errores.append(f"</{tag}> en la línea {self.getpos()[0]}; abierto: {self.pila[-1:] or '-'}")


class ComplementosEstructuraTests(unittest.TestCase):
    def test_every_json_and_notebook_parses(self) -> None:
        archivos = [p for p in COMPLEMENTOS.rglob("*") if p.suffix in {".json", ".ipynb"}]
        self.assertGreaterEqual(len(archivos), 12)
        for archivo in archivos:
            with self.subTest(archivo=_relativa(archivo)):
                datos = json.loads(_leer(archivo))
                if archivo.suffix == ".ipynb":
                    self.assertEqual(datos["nbformat"], 4)
                    self.assertTrue(datos["cells"])

    @unittest.skipUnless(importlib.util.find_spec("nbformat"), "requires nbformat")
    def test_notebooks_are_valid_nbformat(self) -> None:
        import nbformat

        for archivo in COMPLEMENTOS.rglob("*.ipynb"):
            with self.subTest(archivo=_relativa(archivo)):
                nbformat.validate(nbformat.read(str(archivo), as_version=4))

    def test_no_build_artifacts_are_left_under_the_complements(self) -> None:
        sobrantes = [_relativa(p) for p in COMPLEMENTOS.rglob("*")
                     if p.name in {"dist", "__pycache__", "build"} or p.suffix in {".whl", ".pyc"} or p.name.endswith(".egg-info")]
        self.assertEqual(sobrantes, [])

    def test_gitignore_excludes_build_artifacts_of_the_complements(self) -> None:
        reglas = _leer(ROOT / ".gitignore").splitlines()
        self.assertIn("complementos/**/dist/", reglas)
        self.assertIn("complementos/**/__pycache__/", reglas)

    def test_the_expected_complements_are_present(self) -> None:
        for relativa in (
            "README.md",
            "metadata-driven/README-metadata-driven.md",
            "metadata-driven/deploy/deploy.ps1",
            "warehouse-librerias/README-warehouse-librerias.md",
            "warehouse-librerias/deploy/deploy.ps1",
            "warehouse-librerias/valores_esperados.json",
            "git-cicd/fabric-cicd-git-flujo.html",
            "desarrollo-asistido-ia/fabric-desarrollo-asistido-ia-flujo.html",
            "desarrollo-asistido-ia/guion-demo.md",
            "fabric-apps/fac-banca-sintetica/README.md",
            "fabric-apps/fac-banca-sintetica/package.json",
            "fabric-apps/fac-banca-sintetica/rayfin/rayfin.yml",
        ):
            with self.subTest(archivo=relativa):
                self.assertTrue((COMPLEMENTOS / relativa).is_file())
        self.assertTrue(REFERENCIAS.is_file())
        self.assertTrue((BONUS_IA / "guia.md").is_file())


class ComplementosSaneamientoTests(unittest.TestCase):
    def test_no_prohibited_terms_names_or_local_paths(self) -> None:
        archivos = _archivos_de_texto()
        self.assertGreater(len(archivos), 30)
        for archivo in archivos:
            with self.subTest(archivo=_relativa(archivo)):
                encontrado = TERMINOS_EXTENDIDOS.search(_leer(archivo))
                self.assertIsNone(encontrado, encontrado.group(0) if encontrado else "")

    def test_no_guid_in_documents_and_only_markers_or_sentinels_elsewhere(self) -> None:
        for archivo in _archivos_de_texto():
            texto = _leer(archivo)
            for coincidencia in GUID.finditer(texto):
                guid = coincidencia.group(0)
                if archivo.suffix in {".md", ".html"}:
                    motivo = "un GUID no se permite en documentos"
                elif archivo.suffix in {".json", ".ipynb"}:
                    entorno = texto[max(0, coincidencia.start() - 2):coincidencia.end() + 2]
                    motivo = None if entorno == "{{" + guid + "}}" else "un GUID en JSON solo puede ser un marcador {{...}}"
                else:
                    motivo = None if GUID_CENTINELA.match(guid) else "un GUID en código solo puede ser un valor centinela (todos los dígitos iguales)"
                with self.subTest(archivo=_relativa(archivo), guid=guid[:8]):
                    self.assertIsNone(motivo)

    def test_no_email_addresses(self) -> None:
        for archivo in _archivos_de_texto():
            with self.subTest(archivo=_relativa(archivo)):
                self.assertEqual(CORREO.findall(_leer(archivo)), [])

    def test_deploy_scripts_require_the_workspace_name_and_use_the_current_azure_session(self) -> None:
        scripts = [
            COMPLEMENTOS / "metadata-driven" / "deploy" / "deploy.ps1",
            COMPLEMENTOS / "warehouse-librerias" / "deploy" / "deploy.ps1",
            COMPLEMENTOS / "warehouse-librerias" / "herramientas" / "ejecutar_notebook.ps1",
        ]
        for script in scripts:
            texto = _leer(script)
            with self.subTest(script=_relativa(script)):
                self.assertRegex(texto, r"\[Parameter\(Mandatory\)\][^\n]*\$WorkspaceName")
                self.assertRegex(texto, r"\[string\]\$AzureConfigDir(\s*=\s*'')?\s*,")
                self.assertIn("if ($AzureConfigDir)", texto)
                self.assertNotIn("USERPROFILE", texto)
                self.assertNotRegex(texto, r"WorkspaceName\s*=\s*'")


class ComplementosHtmlTests(unittest.TestCase):
    HTML = sorted(p for p in COMPLEMENTOS.rglob("*.html") if "fabric-apps" not in p.parts)

    def test_there_are_two_sheets(self) -> None:
        self.assertEqual(len(self.HTML), 2)

    def test_sheets_are_self_contained(self) -> None:
        prohibidos = {
            "script con src": r"<script\b[^>]*\bsrc\s*=",
            "link externo": r"<link\b[^>]*\bhref\s*=\s*[\"'](?!data:|#)",
            "recurso remoto": r"\b(?:src|srcset)\s*=\s*[\"']\s*(?:https?:)?//",
            "iframe": r"<iframe\b",
            "@import": r"@import\b",
            "url() remoto": r"url\(\s*[\"']?\s*(?:https?:)?//",
            "fetch(": r"\bfetch\s*\(",
            "XMLHttpRequest": r"XMLHttpRequest",
            "localStorage": r"localStorage",
            "sessionStorage": r"sessionStorage",
            "window.open": r"window\.open",
        }
        for hoja in self.HTML:
            texto = _leer(hoja)
            for nombre, patron in prohibidos.items():
                with self.subTest(hoja=hoja.name, prohibido=nombre):
                    self.assertIsNone(re.search(patron, texto, re.IGNORECASE))

    def test_sheets_are_well_formed_and_carry_no_vendor_logo(self) -> None:
        for hoja in self.HTML:
            texto = _leer(hoja)
            analizador = _Equilibrio()
            analizador.feed(texto)
            analizador.close()
            with self.subTest(hoja=hoja.name):
                self.assertTrue(texto.lstrip().lower().startswith("<!doctype html"))
                self.assertEqual(analizador.errores, [])
                self.assertEqual(analizador.pila, [])
                self.assertNotRegex(texto, r"--ms-(red|green|blue|yellow)|#f25022|#7fba00|#00a4ef")


class EnlacesTests(unittest.TestCase):
    def test_every_relative_link_in_the_complements_and_guides_resolves(self) -> None:
        documentos = [*(p for p in COMPLEMENTOS.rglob("*.md") if ".agents" not in p.parts), REFERENCIAS,
                      *BONUS_IA.glob("*.md"), *GUIAS, ROOT / "README.md"]
        rotos: list[str] = []
        for documento in documentos:
            for destino in ENLACE.findall(_leer(documento)):
                if destino.startswith(("http://", "https://", "mailto:")):
                    continue
                ruta, _, ancla = destino.partition("#")
                objetivo = documento if not ruta else (documento.parent / ruta).resolve()
                if not objetivo.exists():
                    rotos.append(f"{_relativa(documento)} -> {destino}")
                elif ancla and objetivo.suffix == ".md" and ancla not in _anclas(objetivo):
                    rotos.append(f"{_relativa(documento)} -> {destino} (ancla inexistente)")
        self.assertEqual(rotos, [])

    def test_the_root_readme_links_the_complements_the_references_and_the_new_bonus(self) -> None:
        readme = _leer(ROOT / "README.md")
        for destino in ("complementos/README.md", "docs/referencias-complementarias.md", "docs/bonus-desarrollo-asistido/guia.md"):
            with self.subTest(destino=destino):
                self.assertIn(destino, readme)

    def test_the_complements_index_links_every_complement(self) -> None:
        indice = _leer(COMPLEMENTOS / "README.md")
        for destino in (
            "metadata-driven/README-metadata-driven.md",
            "warehouse-librerias/README-warehouse-librerias.md",
            "git-cicd/fabric-cicd-git-flujo.html",
            "desarrollo-asistido-ia/fabric-desarrollo-asistido-ia-flujo.html",
            "desarrollo-asistido-ia/guion-demo.md",
            "fabric-apps/fac-banca-sintetica/README.md",
            "../docs/referencias-complementarias.md",
            "../docs/bonus-desarrollo-asistido/guia.md",
        ):
            with self.subTest(destino=destino):
                self.assertIn(destino, indice)
        for fragmento in ("no forman parte de las evidencias", "sintéticos", "no una implementación productiva"):
            with self.subTest(fragmento=fragmento):
                self.assertIn(fragmento, indice.lower())

    def test_each_guide_links_its_complement_or_the_complementary_references(self) -> None:
        esperado = {
            1: ("referencias-complementarias.md",),
            2: ("referencias-complementarias.md", "complementos/metadata-driven/README-metadata-driven.md"),
            3: ("referencias-complementarias.md", "complementos/warehouse-librerias/README-warehouse-librerias.md"),
            4: ("referencias-complementarias.md", "complementos/fabric-apps/fac-banca-sintetica/README.md"),
            5: ("referencias-complementarias.md", "complementos/git-cicd/fabric-cicd-git-flujo.html",
                "complementos/desarrollo-asistido-ia/", "bonus-desarrollo-asistido/guia.md"),
        }
        for numero, guia in enumerate(GUIAS, start=1):
            texto = _leer(guia)
            for destino in esperado[numero]:
                with self.subTest(sesion=numero, destino=destino):
                    self.assertIn(destino, texto)

    def test_the_complementary_boxes_state_that_they_are_not_evidence(self) -> None:
        for numero in (1, 2):
            with self.subTest(sesion=numero):
                self.assertIn("Complemento del facilitador (sin evidencia)", _leer(GUIAS[numero - 1]))
        self.assertIn("no forma parte de las evidencias", _leer(GUIAS[2]))
        self.assertIn("sin ejercicio ni evidencia", _leer(GUIAS[3]))
        self.assertIn("sin evidencia", _leer(GUIAS[4]))

    def test_the_guides_keep_the_original_session_constraints(self) -> None:
        for numero, guia in enumerate(GUIAS, start=1):
            texto = _leer(guia)
            with self.subTest(sesion=numero):
                self.assertIn("60 minutos, sin extensión", texto)
        self.assertIn("no se configuran conectores externos, gateways ni fuentes de producción", _leer(GUIAS[1]))
        for numero in (2, 3, 4, 5):
            with self.subTest(sesion=numero):
                self.assertIn("la sesión no se extiende", _leer(GUIAS[numero - 1]).lower())


if __name__ == "__main__":
    unittest.main()
