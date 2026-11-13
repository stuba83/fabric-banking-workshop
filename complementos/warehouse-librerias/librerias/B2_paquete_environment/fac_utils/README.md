# fac_utils

Paquete de demostración con las mismas funciones utilitarias que `FAC_NB_Utils` (notebook) y
`fac_utils_lh.py` (módulo en Files): normalizar columnas, validar un rango de fechas, hash de fila,
bitácora y lectura de otro Lakehouse.

No declara dependencias: PySpark y `notebookutils` los aporta el runtime de Fabric. Es Python puro
(`py3-none-any`), así que el mismo `.whl` sirve para los runtimes con Python 3.10 o superior.

Construir y probar localmente:

```powershell
python -m pip install build
python -m build --wheel          # genera dist/fac_utils-<versión>-py3-none-any.whl
python -m unittest discover -s tests -v
```

La fuente de `src/fac_utils/funciones.py` es `../../fuente/funciones.py`; no se edita aquí.