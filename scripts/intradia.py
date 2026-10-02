"""Baja las velas de 15 minutos de hoy de los bancos (CGR / MarketDataHub) a data/intradia.json.

La página arma el intradía con lo que recibe mientras está abierta; este archivo completa lo que
pasó antes de abrirla. El navegador no puede pedirle estas velas a CGR directo (su servidor no acepta
pedidos desde otra página), por eso lo hace esta tarea de GitHub Actions cada 15 minutos.

El token se lee de la variable de entorno MDH_TOKEN (secreto del repositorio): nunca va en el código.

Uso: MDH_TOKEN=mdh_... python scripts/intradia.py
"""

from __future__ import annotations

import datetime
import json
import os
import pathlib
import urllib.parse
import urllib.request

BASE = "https://dash.cgrconsult.ing/api/historical/"
BANCOS = ("GGAL", "BMA", "BBAR", "SUPV")
BA = datetime.timezone(datetime.timedelta(hours=-3))   # Buenos Aires, sin horario de verano
SALIDA = pathlib.Path(__file__).resolve().parent.parent / "data" / "intradia.json"
# Velas de las ruedas anteriores, para el perfil de volumen de 5 y 20 ruedas. Se reescribe solo cuando
# cambia el día: así el repositorio no acumula una copia nueva cada 15 minutos.
PERFIL = SALIDA.with_name("perfil.json")
RUEDAS_PERFIL = 20


def velas(ticker: str, token: str) -> list[dict]:
    url = BASE + urllib.parse.quote(f"{ticker} - 24hs") + "?interval=15m"
    # El servidor rechaza el agente por defecto de Python: hay que identificarse como un cliente HTTP común.
    pedido = urllib.request.Request(url, headers={"X-Internal-Token": token, "User-Agent": "curl/8.0"})
    with urllib.request.urlopen(pedido, timeout=60) as respuesta:
        return json.load(respuesta)


def main() -> None:
    token = os.environ.get("MDH_TOKEN", "").strip()
    if not token:
        raise SystemExit("Falta MDH_TOKEN.")
    ahora = datetime.datetime.now(BA)
    hoy = ahora.date().isoformat()
    bancos: dict[str, dict] = {}
    historia: dict[str, list] = {}
    for b in BANCOS:
        filas = velas(b, token)
        fechas = sorted({x["timestamp"][:10] for x in filas if x["timestamp"][:10] < hoy})[-RUEDAS_PERFIL:]
        # [fecha, mínimo, máximo, volumen en pesos] de cada vela de 15 minutos
        historia[b] = [[x["timestamp"][:10], x["low"], x["high"], x["volume"]]
                       for x in filas if fechas and fechas[0] <= x["timestamp"][:10] < hoy]
        de_hoy = [x for x in filas if x["timestamp"].startswith(hoy)]
        previas = [x for x in filas if x["timestamp"][:10] < hoy]
        bancos[b] = {
            "cl": previas[-1]["close"] if previas else None,   # cierre de la rueda anterior
            "velas": [
                {"t": int(x["timestamp"][11:13]) * 60 + int(x["timestamp"][14:16]),
                 "o": x["open"], "h": x["high"], "l": x["low"], "c": x["close"], "v": x["volume"]}
                for x in de_hoy
            ],
        }
    hasta = max((v[-1][0] for v in historia.values() if v), default=None)
    previo = json.loads(PERFIL.read_text(encoding="utf-8")).get("hasta") if PERFIL.exists() else None
    if hasta and hasta != previo:
        PERFIL.parent.mkdir(exist_ok=True)
        PERFIL.write_text(json.dumps({"hasta": hasta, "ruedas": RUEDAS_PERFIL, "b": historia}, separators=(",", ":")), encoding="utf-8")
        print("perfil.json hasta", hasta, {b: len(v) for b, v in historia.items()})

    if not any(x["velas"] for x in bancos.values()):
        print(f"Sin velas de hoy ({hoy}): no se toca el archivo.")
        return
    SALIDA.parent.mkdir(exist_ok=True)
    SALIDA.write_text(json.dumps({"fecha": hoy, "paso": 15, "b": bancos}, separators=(",", ":")), encoding="utf-8")
    print(hoy, {b: len(x["velas"]) for b, x in bancos.items()})


if __name__ == "__main__":
    main()
