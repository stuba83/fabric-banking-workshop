from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ENLACE = re.compile(r"\]\(([^)\s]+)\)")


def _documentos() -> list[Path]:
    return [ROOT / "README.md", *sorted((ROOT / "docs").rglob("*.md")),
            *sorted((ROOT / "dataset").glob("*.md"))]


class DocumentacionTests(unittest.TestCase):
    def test_every_relative_link_resolves(self) -> None:
        rotos = []
        for documento in _documentos():
            for destino in ENLACE.findall(documento.read_text(encoding="utf-8")):
                if destino.startswith(("http://", "https://", "mailto:", "#")):
                    continue
                ruta = destino.split("#", 1)[0]
                if not (documento.parent / ruta).resolve().exists():
                    rotos.append(f"{documento.relative_to(ROOT)} -> {destino}")
        self.assertEqual(rotos, [])

    def test_readme_route_lists_the_guide_and_evidence_of_all_five_sessions(self) -> None:
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        for numero in range(1, 6):
            for archivo in ("guia.md", "evidencias.md"):
                relativa = f"docs/sesion-0{numero}/{archivo}"
                with self.subTest(archivo=relativa):
                    self.assertTrue((ROOT / relativa).is_file())
                    self.assertIn(relativa, readme)

    def test_each_guide_points_to_the_next_session(self) -> None:
        for numero in range(1, 5):
            guia = (ROOT / "docs" / f"sesion-0{numero}" / "guia.md").read_text(encoding="utf-8")
            with self.subTest(sesion=numero):
                self.assertIn(f"sesion-0{numero + 1}/guia.md", guia)

    def test_notebooks_listed_in_the_readme_exist(self) -> None:
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        for notebook in ("02_ingesta_bronce.ipynb", "03_plata_silver.ipynb"):
            with self.subTest(notebook=notebook):
                self.assertIn(f"notebooks/{notebook}", readme)
                self.assertTrue((ROOT / "notebooks" / notebook).is_file())

    def test_the_readme_explains_how_the_training_works(self) -> None:
        readme = (ROOT / "README.md").read_text(encoding="utf-8").lower()
        for fragmento in ("aula invertida", "no se extienden", "45–60 minutos", "punto focal"):
            with self.subTest(fragmento=fragmento):
                self.assertIn(fragmento, readme)


if __name__ == "__main__":
    unittest.main()
