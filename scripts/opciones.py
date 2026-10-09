"""Historia de las opciones de BYMA (velas de 15 minutos de CGR) a data/opciones.json.

La pestaña Opciones arma con esto el costo histórico de una estrategia. CGR guarda poca historia de opciones
y el navegador no le puede pedir velas (su servidor no acepta pedidos desde otra página), así que esta
tarea las baja y las acumula: lo que ya estaba en el archivo se conserva aunque CGR lo borre. Las opciones
que ya vencieron (no figuran en el panel de Data912) se descartan.

El token se lee de la variable de entorno MDH_TOKEN (secreto del repositorio): nunca va en el código.

Uso: MDH_TOKEN=mdh_... python scripts/opciones.py
"""

from __future__ import annotations

import datetime
import json
import os
import pathlib
import re
import urllib.parse
import urllib.request

CGR = "https://dash.cgrconsult.ing/api/historical/"
D912 = "https://data912.com/live/arg_options"
SALIDA = pathlib.Path(__file__).resolve().parent.parent / "data" / "opciones.json"
# Activo de la opción (3 letras) -> acción. Mismo mapa que la pestaña Opciones.
SUBY = {"GFG": "GGAL", "YPF": "YPFD", "COM": "COME", "PAM": "PAMP", "MET": "METR", "EDN": "EDN", "BYM": "BYMA", "ALU": "ALUA",
        "TXA": "TXAR", "CEP": "CEPU", "TRA": "TRAN", "BHI": "BHIP", "TEC": "TECO2", "TGS": "TGSU2", "CRE": "CRES", "TGN": "TGNO4",
        "BBA": "BBAR", "CEC": "CECO2", "LOM": "LOMA", "SUP": "SUPV", "BMA": "BMA"}


def leer(url: str, headers: dict) -> list:
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=60) as r:
        return json.load(r)


def velas(sym: str, token: str) -> list:
    """[["2026-10-05 10:45", cierre], ...] de las velas de 15 minutos de CGR."""
    url = CGR + urllib.parse.quote(f"{sym} - 24hs") + "?interval=15m"
    filas = leer(url, {"X-Internal-Token": token, "User-Agent": "curl/8.0"})
    return [[x["timestamp"][:16].replace("T", " "), x["close"]] for x in filas if x.get("close")]


def main() -> None:
    token = os.environ.get("MDH_TOKEN", "").strip()
    if not token:
        raise SystemExit("Falta MDH_TOKEN.")
    vivas = [x["symbol"] for x in leer(D912, {"User-Agent": "Mozilla/5.0"})]
    vivas = [s for s in vivas if re.match(r"^[A-Z]{3}[CV]", s) and s[:3] in SUBY]
    previo = json.loads(SALIDA.read_text(encoding="utf-8")) if SALIDA.exists() else {"s": {}, "u": {}}

    def juntar(viejo: list, nuevo: list) -> list:
        m = dict(map(tuple, viejo))
        m.update(dict(map(tuple, nuevo)))
        return [[t, m[t]] for t in sorted(m)]

    opciones, fallas = {}, 0
    for s in vivas:
        try:
            nuevo = velas(s, token)
        except Exception as e:   # una que falla no tira abajo al resto: queda lo que había
            fallas += 1
            print(s, "ERROR", e)
            nuevo = []
        serie = juntar(previo["s"].get(s, []), nuevo)
        if serie:
            opciones[s] = serie
    acciones = {}
    for u in sorted({SUBY[s[:3]] for s in opciones}):
        try:
            acciones[u] = juntar(previo["u"].get(u, []), velas(u, token))
        except Exception as e:
            print(u, "ERROR", e)
            if u in previo["u"]:
                acciones[u] = previo["u"][u]
    if vivas and fallas > len(vivas) // 2:
        raise SystemExit("Fallaron demasiadas: no se toca el archivo.")
    SALIDA.parent.mkdir(exist_ok=True)
    SALIDA.write_text(json.dumps({"fecha": datetime.date.today().isoformat(), "s": opciones, "u": acciones}, separators=(",", ":")),
                      encoding="utf-8")
    print(len(opciones), "opciones con historia;", sum(len(v) for v in opciones.values()), "velas;", list(acciones))


if __name__ == "__main__":
    main()
