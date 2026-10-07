"""Datos de la pestaña Sectores a data/sectores.json: acciones totales de cada empresa y cierres diarios.

Acciones: para ponderar cada sector por market cap.

Se toma el market cap de Yahoo dividido por su precio: así entran todas las clases de acciones de la
empresa (TGS, Telecom, TGN, Metrogas o Transener tienen clases que no cotizan y Yahoo las suma).
Si Yahoo no tiene market cap, se usan las acciones en circulación. La página multiplica estas acciones
por el precio del momento. Cambian muy poco, así que alcanza con bajarlas una vez por día.

Cierres: los de Data912 desde diciembre del año pasado (alcanza para 1S, 1M y YTD), con el CCL del
AL30. El navegador podría pedirlos directo, pero son ~7 MB por visita; así baja unos 100 KB.
Data912 tiene algún cierre fuera del rango del día: se reemplaza por el punto medio entre mínimo y máximo.

Uso: python scripts/sectores.py
"""

from __future__ import annotations

import datetime
import json
import pathlib
import urllib.request

import yfinance as yf

# Las mismas especies que arma la pestaña Sectores (la clasificación vive en index.html).
TICKERS = """GGAL BMA BBAR SUPV BPAT VALO BHIP BYMA A3 YPFD CAPX TGSU2 TGNO4 ECOG METR GBAN DGCU2 CGPA2
PAMP CEPU CECO2 TRAN EDN TXAR ALUA LOMA HARG CELU FERR FIPL CARC TECO2 CVH GCLA CRES MOLA MOLI LEDE
SAMI AGRO MORI SEMI IRSA CTIO GCDI MIRG PATA COME BOLT RICH GRIM HAVA LONG AUSO OEST
INTR CADO RIGO POLL GAMI GARO DOME ROSE""".split()
SALIDA = pathlib.Path(__file__).resolve().parent.parent / "data" / "sectores.json"
D912 = "https://data912.com/historical/"


def cierres(ruta: str, desde: str) -> list:
    pedido = urllib.request.Request(D912 + ruta, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(pedido, timeout=60) as r:
        filas = json.load(r)
    out = []
    for x in filas:
        c, lo, hi = x.get("c"), x.get("l"), x.get("h")
        if x["date"] < desde or not c or c <= 0:
            continue
        if lo and hi and lo > 0 and (c < lo * 0.995 or c > hi * 1.005):
            c = (lo + hi) / 2
        out.append([x["date"], c])
    return out


def ajustar(t: str, filas: list) -> list:
    """Splits y dividendos en acciones (Yahoo los registra; Data912 no los ajusta): los precios anteriores
    se dividen por la proporción. Después, un cierre aislado que se va y vuelve al día siguiente
    (más de 25% y menos de 10% contra el anterior) se reemplaza por el promedio de sus vecinos."""
    try:
        for f, r in yf.Ticker(t + ".BA").splits.items():
            dia = str(f.date())
            if r and r > 0 and dia > filas[0][0]:
                filas = [[d, c / r if d < dia else c] for d, c in filas]
                print(t, "ajustado por", r, "el", dia)
    except Exception as e:
        print(t, "sin splits", e)
    for i in range(1, len(filas) - 1):
        a, b, c = filas[i - 1][1], filas[i][1], filas[i + 1][1]
        if abs(b / a - 1) > 0.25 and abs(c / a - 1) < 0.10:
            filas[i][1] = (a + c) / 2
            print(t, "cierre aislado corregido el", filas[i][0])
    return [[d, round(c, 4)] for d, c in filas]


def acciones(t: str) -> float | None:
    k = yf.Ticker(t + ".BA")
    info = k.info
    mc, p = info.get("marketCap"), info.get("currentPrice") or info.get("regularMarketPrice")
    if mc and p:
        return mc / p
    sh = info.get("sharesOutstanding") or info.get("impliedSharesOutstanding")
    if sh:
        return float(sh)
    bs = k.quarterly_balance_sheet
    for r in ("Ordinary Shares Number", "Share Issued"):
        if r in bs.index and len(bs.loc[r].dropna()):
            return float(bs.loc[r].dropna().iloc[0])
    return None


def main() -> None:
    previo = json.loads(SALIDA.read_text(encoding="utf-8"))["acciones"] if SALIDA.exists() else {}
    desde = f"{datetime.date.today().year - 1}-12-01"
    a30, a30c = dict(cierres("bonds/AL30", desde)), dict(cierres("bonds/AL30C", desde))
    ccl = [[f, round(a30[f] / a30c[f], 2)] for f in sorted(a30) if f in a30c]
    salida = {}
    for t in TICKERS:
        try:
            a = acciones(t)
        except Exception as e:   # una que falla no tira abajo al resto: queda la del día anterior
            print(t, "ERROR", e)
            a = None
        if a:
            salida[t] = round(a)
        elif t in previo:
            salida[t] = previo[t]
        print(f"{t:6} {salida.get(t, 0):>16,}")
    if len(salida) < len(TICKERS) // 2:
        raise SystemExit("Fallaron demasiadas: no se toca el archivo.")
    hist = {}
    for t in TICKERS:
        try:
            hist[t] = ajustar(t, cierres(f"stocks/{t}", desde))
        except Exception:
            # Data912 no tiene algunas (A3, ECOG): se usan los cierres de Yahoo.
            try:
                h = yf.Ticker(t + ".BA").history(start=desde, auto_adjust=False)["Close"].dropna()
                hist[t] = [[str(f.date()), round(float(c), 4)] for f, c in h.items() if c > 0]
            except Exception as e:
                print(t, "sin historia", e)
    SALIDA.parent.mkdir(exist_ok=True)
    SALIDA.write_text(json.dumps({"fecha": datetime.date.today().isoformat(), "acciones": salida, "cierres": hist, "ccl": ccl},
                                 separators=(",", ":")), encoding="utf-8")
    print("cierres", len(hist), "especies; CCL hasta", ccl[-1] if ccl else None)


if __name__ == "__main__":
    main()
