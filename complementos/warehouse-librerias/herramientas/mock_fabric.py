"""Servidor Fabric simulado (solo localhost) para probar deploy.ps1 sin capacidad ni red.

    python mock_fabric.py --puerto 8765 --registro registro.json

Implementa solo los endpoints que usa deploy.ps1. Guarda cada solicitud (método, ruta, cabecera
x-ms-fabric-skill y, para las definiciones, el contenido decodificado) en el archivo de registro.
No es una réplica del servicio: sirve para comprobar el flujo y la idempotencia del script.
"""

import argparse
import base64
import json
import re
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

WS_NOMBRE = "ws-simulado"   # se puede cambiar con --workspace
WS_ID = "11111111-1111-1111-1111-111111111111"
CAP_ID = "22222222-2222-2222-2222-222222222222"
ITEMS = [
    {"id": "33333333-3333-3333-3333-333333333333", "type": "Lakehouse", "displayName": "AB_Lakehouse"},
    {"id": "44444444-4444-4444-4444-444444444444", "type": "SQLEndpoint", "displayName": "AB_Lakehouse"},
]
OPERACIONES = {}
PUBLICADAS = {}
REGISTRO = []
ARGS = None

TIPOS_POR_RUTA = {
    "lakehouses": "Lakehouse", "warehouses": "Warehouse", "environments": "Environment",
    "notebooks": "Notebook", "dataPipelines": "DataPipeline",
}


class Manejador(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def _responder(self, codigo, cuerpo=None, cabeceras=None):
        datos = b"" if cuerpo is None else json.dumps(cuerpo).encode()
        self.send_response(codigo)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(datos)))
        for k, v in (cabeceras or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(datos)

    def _cuerpo(self):
        largo = int(self.headers.get("Content-Length") or 0)
        crudo = self.rfile.read(largo) if largo else b""
        return json.loads(crudo) if crudo else None

    def _anotar(self, cuerpo):
        entrada = {"metodo": self.command, "ruta": self.path, "skill": self.headers.get("x-ms-fabric-skill"),
                   "autorizacion": bool(self.headers.get("Authorization"))}
        if isinstance(cuerpo, dict):
            definicion = cuerpo.get("definition") or {}
            partes = []
            for parte in definicion.get("parts", []):
                carga = base64.b64decode(parte["payload"])
                resumen = {"path": parte["path"], "bytes": len(carga)}
                if parte["path"].endswith((".ipynb", ".json")):
                    resumen["json_valido"] = True
                    try:
                        resumen["texto"] = carga.decode("utf-8")
                        json.loads(resumen["texto"])
                    except Exception:
                        resumen["json_valido"] = False
                partes.append(resumen)
            entrada["cuerpo"] = {k: v for k, v in cuerpo.items() if k != "definition"}
            entrada["partes"] = partes
        REGISTRO.append(entrada)
        with open(ARGS.registro, "w", encoding="utf-8") as archivo:
            json.dump(REGISTRO, archivo, ensure_ascii=False, indent=1)

    def do_GET(self):
        self._anotar(None)
        ruta = self.path.split("?")[0]
        consulta = self.path.split("?")[1] if "?" in self.path else ""
        if ruta == "/v1/workspaces":
            return self._responder(200, {"value": [{"id": WS_ID, "displayName": ARGS.workspace, "capacityId": CAP_ID}]})
        if ruta == f"/v1/workspaces/{WS_ID}":
            return self._responder(200, {"id": WS_ID, "displayName": ARGS.workspace, "capacityId": CAP_ID})
        if ruta == "/v1/capacities":
            return self._responder(200, {"value": [{"id": CAP_ID, "state": ARGS.estado_capacidad}]})
        if ruta == f"/v1/workspaces/{WS_ID}/items":
            tipo = re.search(r"type=(\w+)", consulta)
            valor = [i for i in ITEMS if not tipo or i["type"] == tipo.group(1)]
            return self._responder(200, {"value": valor})
        coincidencia = re.fullmatch(rf"/v1/workspaces/{WS_ID}/warehouses/([\w-]+)", ruta)
        if coincidencia:
            return self._responder(200, {"id": coincidencia.group(1), "properties": {"connectionString": "mock.datawarehouse.local"}})
        coincidencia = re.fullmatch(rf"/v1/workspaces/{WS_ID}/environments/([\w-]+)/libraries", ruta)
        if coincidencia:
            return self._responder(200, {"libraries": [{"name": n, "libraryType": "Custom"} for n in PUBLICADAS.get(coincidencia.group(1), [])]})
        coincidencia = re.fullmatch(rf"/v1/workspaces/{WS_ID}/environments/([\w-]+)", ruta)
        if coincidencia:
            estado = "Success" if PUBLICADAS.get(coincidencia.group(1)) else "Success"
            return self._responder(200, {"id": coincidencia.group(1), "properties": {"publishDetails": {"state": estado}}})
        coincidencia = re.fullmatch(r"/v1/operations/([\w-]+)", ruta)
        if coincidencia:
            return self._responder(200, {"status": "Succeeded", "id": coincidencia.group(1)})
        self._responder(404, {"errorCode": "NotFound", "ruta": ruta})

    def do_POST(self):
        cuerpo = self._cuerpo()
        self._anotar(cuerpo)
        ruta = self.path.split("?")[0]
        coincidencia = re.fullmatch(rf"/v1/workspaces/{WS_ID}/(\w+)", ruta)
        if coincidencia and coincidencia.group(1) in TIPOS_POR_RUTA:
            nuevo = {"id": str(uuid.uuid4()), "type": TIPOS_POR_RUTA[coincidencia.group(1)], "displayName": cuerpo["displayName"]}
            ITEMS.append(nuevo)
            if nuevo["type"] == "Warehouse":
                operacion = str(uuid.uuid4())
                OPERACIONES[operacion] = nuevo
                return self._responder(202, None, {"Location": f"http://127.0.0.1:{ARGS.puerto}/v1/operations/{operacion}", "Retry-After": "1"})
            return self._responder(201, nuevo)
        coincidencia = re.fullmatch(rf"/v1/workspaces/{WS_ID}/(notebooks|environments|dataPipelines)/([\w-]+)/updateDefinition", ruta)
        if coincidencia:
            if coincidencia.group(1) == "environments":
                for parte in cuerpo["definition"]["parts"]:
                    PUBLICADAS.setdefault(coincidencia.group(2), []).append(parte["path"].split("/")[-1])
            return self._responder(200, None)
        if re.fullmatch(rf"/v1/workspaces/{WS_ID}/environments/([\w-]+)/staging/publish", ruta):
            return self._responder(200, {"publishDetails": {"state": "Running"}})
        if re.fullmatch(rf"/v1/workspaces/{WS_ID}/sqlEndpoints/([\w-]+)/refreshMetadata", ruta):
            return self._responder(200, {})
        self._responder(404, {"errorCode": "NotFound", "ruta": ruta})


def main():
    global ARGS
    parser = argparse.ArgumentParser()
    parser.add_argument("--puerto", type=int, default=8765)
    parser.add_argument("--workspace", default=WS_NOMBRE, help="nombre del workspace que devuelve el servidor simulado")
    parser.add_argument("--registro", default="registro.json")
    parser.add_argument("--estado-capacidad", default="Active")
    ARGS = parser.parse_args()
    ThreadingHTTPServer(("127.0.0.1", ARGS.puerto), Manejador).serve_forever()


if __name__ == "__main__":
    main()
