"""Foto diaria de la sonrisa de las opciones de GGAL a data/sonrisas.json.

Para cada vencimiento: precio de GGAL y, por strike, la VI de call y put (Black-Scholes con la punta media,
o el último si no hay puntas). Una foto por día (la última corrida del día pisa a la anterior). Sirve para
medir con datos reales cómo cambia la sonrisa a lo largo del ejercicio (quant/ejercicio.py).

Uso: python scripts/sonrisa.py [--tasa 20]   (TNA % para la VI)
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import pathlib
import re
import urllib.request

SALIDA = pathlib.Path(__file__).resolve().parent.parent / "data" / "sonrisas.json"
BA = dt.timezone(dt.timedelta(hours=-3))
MESES = {"EN": 1, "FE": 2, "MR": 3, "AB": 4, "MY": 5, "JN": 6, "JU": 6, "JL": 7, "AG": 8, "SE": 9, "OC": 10, "NO": 11, "NV": 11, "DI": 12}


def leer(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=60) as r:
        return json.load(r)


def tercer_viernes(anio, mes):
    d = dt.date(anio, mes, 1)
    return dt.datetime(anio, mes, 1 + (4 - d.weekday()) % 7 + 14, 17, tzinfo=BA)


N = lambda x: 0.5 * (1 + math.erf(x / math.sqrt(2)))


def bs(S, K, T, r, s, call):
    d1 = (math.log(S / K) + (r + s * s / 2) * T) / (s * math.sqrt(T))
    d2 = d1 - s * math.sqrt(T)
    return S * N(d1) - K * math.exp(-r * T) * N(d2) if call else K * math.exp(-r * T) * N(-d2) - S * N(-d1)


def vi(p, S, K, T, r, call):
    piso = max(0.0, S - K * math.exp(-r * T)) if call else max(0.0, K * math.exp(-r * T) - S)
    if not p or p <= piso * 1.0005 or p >= bs(S, K, T, r, 5, call):
        return None
    lo, hi = 0.005, 5.0
    for _ in range(80):
        m = (lo + hi) / 2
        lo, hi = (lo, m) if bs(S, K, T, r, m, call) > p else (m, hi)
    return round((lo + hi) / 2, 4)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tasa", type=float, default=20.0)
    a = ap.parse_args()
    r = math.log(1 + a.tasa / 100 / 365) * 365
    ahora = dt.datetime.now(BA)
    S = next(x for x in leer("https://data912.com/live/arg_stocks") if x["symbol"] == "GGAL")["c"]
    filas = []
    for x in leer("https://data912.com/live/arg_options"):
        m = re.match(r"^GFG([CV])(\d+(?:\.\d+)?)([A-Z]{1,2})$", x["symbol"])
        if m:
            b, k = x.get("px_bid") or 0, x.get("px_ask") or 0
            filas.append((m.group(1) == "C", float(m.group(2)), m.group(3), (b + k) / 2 if b > 0 and k > 0 else (x.get("c") or 0), x.get("v") or 0))
    dos = sorted({f[2] for f in filas if len(f[2]) == 2})
    foto = {"GGAL": S, "hora": f"{ahora:%H:%M}", "vtos": {}}
    for call, K, cod, p, v in filas:
        cod = next((c for c in dos if c[0] == cod), cod) if len(cod) == 1 else cod
        mes = MESES.get(cod)
        if not mes:
            continue
        vto = tercer_viernes(ahora.year if mes >= ahora.month else ahora.year + 1, mes)
        if vto < ahora:
            vto = tercer_viernes(ahora.year + 1, mes)
        T = (vto - ahora).total_seconds() / (365 * 86400)
        s = vi(p, S, K, T, r, call) if T > 0 else None
        if s:
            dia = foto["vtos"].setdefault(f"{vto:%Y-%m-%d}", {})
            dia.setdefault(f"{K:g}", {})["C" if call else "V"] = [s, round(p, 3), int(v)]
    datos = json.loads(SALIDA.read_text(encoding="utf-8")) if SALIDA.exists() else {}
    datos[f"{ahora:%Y-%m-%d}"] = foto
    SALIDA.write_text(json.dumps(dict(sorted(datos.items())), separators=(",", ":")), encoding="utf-8")
    print(f"sonrisa {ahora:%Y-%m-%d %H:%M}: GGAL {S}, " + ", ".join(f"{k}: {len(v)} strikes" for k, v in foto["vtos"].items()))


if __name__ == "__main__":
    main()
