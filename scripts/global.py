"""Datos de la pestaña Global Macro a data/global.json: cierres diarios de ETFs por región y activos macro.

Acciones: un ETF por país o región, en dólares, para comparar EEUU, Europa, Asia, Latam y emergentes con
la misma vara. Macro: dólar, tasa a 10 años de EEUU, VIX, commodities, monedas y bitcoin.
Se bajan unos 14 meses de cierres (alcanza para 1D, 1S, 1M, 3M, YTD y 1A); la página calcula los
rendimientos. El catálogo (grupos, nombres y qué ETF es el principal de cada región) vive acá.

Uso: python scripts/global.py
"""

from __future__ import annotations

import datetime
import json
import pathlib

import yfinance as yf

SALIDA = pathlib.Path(__file__).resolve().parent.parent / "data" / "global.json"

# (grupo, [(ticker, nombre, principal)]). El principal de cada región entra en el gráfico base 100.
# tipo "tasa": se mide en puntos básicos, no en %.
ACCIONES = [
    ("EEUU", [("SPY", "S&P 500", True), ("QQQ", "Nasdaq 100", False), ("IWM", "Russell 2000", False), ("DIA", "Dow Jones", False)]),
    ("Europa", [("VGK", "Europa", True), ("EZU", "Eurozona", False), ("EWG", "Alemania", False), ("EWU", "Reino Unido", False), ("EWQ", "Francia", False)]),
    ("Asia", [("AAXJ", "Asia ex-Japón", True), ("EWJ", "Japón", False), ("MCHI", "China", False), ("INDA", "India", False), ("EWY", "Corea", False), ("EWT", "Taiwán", False)]),
    ("Latam", [("ILF", "Latam 40", True), ("EWZ", "Brasil", False), ("EWW", "México", False), ("ECH", "Chile", False), ("ARGT", "Argentina", False)]),
    ("Global", [("ACWI", "Mundo", True), ("EFA", "Desarrollados ex-EEUU", False), ("EEM", "Emergentes", True)]),
]
MACRO = [
    ("Dólar y tasas", [("DX-Y.NYB", "Dólar (DXY)", "nivel"), ("^TNX", "Tasa 10 años EEUU", "tasa"), ("^VIX", "VIX", "nivel")]),
    ("Commodities", [("GC=F", "Oro", "nivel"), ("SI=F", "Plata", "nivel"), ("CL=F", "Petróleo WTI", "nivel"), ("HG=F", "Cobre", "nivel")]),
    ("Monedas", [("EURUSD=X", "EUR/USD", "nivel"), ("USDJPY=X", "USD/JPY", "nivel"), ("USDBRL=X", "USD/BRL", "nivel"), ("USDMXN=X", "USD/MXN", "nivel")]),
    ("Cripto", [("BTC-USD", "Bitcoin", "nivel")]),
]


def main() -> None:
    tickers = [t for _, xs in ACCIONES for t, *_ in xs] + [t for _, xs in MACRO for t, *_ in xs]
    desde = (datetime.date.today() - datetime.timedelta(days=430)).isoformat()
    df = yf.download(tickers, start=desde, auto_adjust=True, progress=False, group_by="ticker", threads=True)
    series: dict[str, list] = {}
    for t in tickers:
        try:
            c = df[t]["Close"].dropna()
        except KeyError:
            continue
        if len(c) < 5:
            continue
        series[t] = [[d.strftime("%Y-%m-%d"), round(float(v), 4)] for d, v in c.items()]
    if not series:
        raise SystemExit("Yahoo no devolvió datos")
    salida = {
        "fecha": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%MZ"),
        "acciones": [{"grupo": g, "items": [{"t": t, "n": n, "p": p} for t, n, p in xs if t in series]} for g, xs in ACCIONES],
        "macro": [{"grupo": g, "items": [{"t": t, "n": n, "tipo": k} for t, n, k in xs if t in series]} for g, xs in MACRO],
        "series": series,
    }
    SALIDA.write_text(json.dumps(salida, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    faltan = [t for t in tickers if t not in series]
    print(f"{len(series)} series, {SALIDA.stat().st_size // 1024} KB" + (f"; sin datos: {faltan}" if faltan else ""))


if __name__ == "__main__":
    main()
