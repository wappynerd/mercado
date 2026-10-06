"""Bancos comparables de la región (Brasil, Colombia, Perú, Chile, México) a data/pares.json.

Yahoo Finance no acepta pedidos desde otra página, así que esta tarea de GitHub Actions baja los
balances y precios y guarda los ratios ya calculados. Todo se calcula en una sola moneda: el market
cap (en la moneda del precio) se compara con el patrimonio llevado a esa moneda con el tipo de cambio
de hoy, porque Yahoo mezcla dólares del ADR con pesos colombianos del balance en su propio P/B.

Uso: python scripts/pares.py
"""

from __future__ import annotations

import datetime
import json
import math
import pathlib

import yfinance as yf

# ROE: ganancia del último trimestre anualizada sobre el patrimonio promedio del trimestre (el de
# 12 meses no sirve: Yahoo arma el cuarto trimestre restando, y en varios bancos queda negativo).
# Santander Brasil queda afuera: Yahoo no resuelve bien sus units y el market cap sale mal.
# ticker de Yahoo -> (ticker que se muestra, nombre, país)
PARES = {
    "ITUB": ("ITUB", "Itaú Unibanco", "BR"),
    "BBD": ("BBD", "Bradesco", "BR"),
    "BBAS3.SA": ("BBAS3", "Banco do Brasil", "BR"),
    "BPAC11.SA": ("BPAC11", "BTG Pactual", "BR"),
    "NU": ("NU", "Nu Holdings", "BR"),
    "CIB": ("CIB", "Bancolombia", "CO"),
    "AVAL": ("AVAL", "Grupo Aval", "CO"),
    "BAP": ("BAP", "Credicorp", "PE"),
    "IFS": ("IFS", "Intercorp", "PE"),
    "BCH": ("BCH", "Banco de Chile", "CL"),
    "BSAC": ("BSAC", "Santander Chile", "CL"),
    "BCI.SN": ("BCI", "BCI", "CL"),
    "GFNORTEO.MX": ("GFNORTE", "Banorte", "MX"),
    "BBAJIOO.MX": ("BBAJIO", "BanBajío", "MX"),
    "GFINBURO.MX": ("GFINBUR", "Inbursa", "MX"),
}
SALIDA = pathlib.Path(__file__).resolve().parent.parent / "data" / "pares.json"


def fila(df, nombres):
    for n in nombres:
        if n in df.index:
            s = df.loc[n].dropna()
            if len(s):
                return s.sort_index()
    return None


def fx(desde: str, hacia: str) -> float:
    """Unidades de `hacia` por una de `desde`."""
    if desde == hacia:
        return 1.0
    return float(yf.Ticker(f"{desde}{hacia}=X").fast_info["last_price"])


def trimestre(fecha) -> str:
    return f"{fecha.year}Q{(fecha.month - 1) // 3 + 1}"


def par(simbolo: str) -> dict:
    k = yf.Ticker(simbolo)
    info = k.info
    mon_p, mon_b = info.get("currency"), info.get("financialCurrency") or info.get("currency")
    precio = float(k.fast_info["last_price"])
    bs, res = k.quarterly_balance_sheet, k.quarterly_income_stmt
    # Banorte y otros locales vienen sin market cap: precio × acciones del último balance.
    mc = info.get("marketCap") or precio * float(fila(bs, ["Ordinary Shares Number", "Share Issued"]).iloc[-1])
    pat = fila(bs, ["Common Stock Equity", "Stockholders Equity"])
    gan = fila(res, ["Net Income Common Stockholders", "Net Income", "Net Income From Continuing Operation Net Minority Interest"])
    q = pat.index[-1]
    eq, eq0 = float(pat.iloc[-1]), float(pat.iloc[-2]) if len(pat) > 1 else float(pat.iloc[-1])
    ni_q = float(gan[gan.index <= q].iloc[-1]) if (gan.index <= q).any() else None
    a_p = fx(mon_b, mon_p)              # patrimonio y ganancias a la moneda del precio
    a_usd = fx(mon_p, "USD")            # market cap a dólares
    hist = k.history(period="13mo", auto_adjust=True)["Close"].dropna()
    hace = hist[hist.index <= hist.index[-1] - datetime.timedelta(days=365)]
    var1a = None
    if len(hace):
        # Variación en dólares: si el precio está en moneda local, se corrige por el tipo de cambio.
        v = precio / float(hace.iloc[-1])
        if mon_p != "USD":
            fxh = yf.Ticker(f"{mon_p}USD=X").history(start=hace.index[-1].date() - datetime.timedelta(days=5), end=hace.index[-1].date() + datetime.timedelta(days=1))["Close"].dropna()
            v *= a_usd / float(fxh.iloc[-1])
        var1a = v - 1
    return {
        "mc": mc * a_usd / 1e6,
        "pbv": mc / (eq * a_p),
        "roe": ni_q * 4 / ((eq + eq0) / 2) if ni_q is not None else None,
        "var1a": var1a,
        "q": trimestre(q),
    }


def main() -> None:
    salida = []
    for s, (t, nombre, pais) in PARES.items():
        try:
            d = par(s)
        except Exception as e:   # un banco que falla no tira abajo al resto
            print(s, "ERROR", e)
            continue
        print(f"{t:8} {pais} mc {d['mc']:>9,.0f}  pbv {d['pbv']:.2f}  roe {d['roe'] or 0:.1%}  1a {d['var1a'] or 0:+.0%}  {d['q']}")
        salida.append({"t": t, "n": nombre, "p": pais, **{k: (round(v, 4) if isinstance(v, float) and math.isfinite(v) else v) for k, v in d.items()}})
    if len(salida) < len(PARES) // 2:
        raise SystemExit("Fallaron demasiados bancos: no se toca el archivo.")
    SALIDA.parent.mkdir(exist_ok=True)
    SALIDA.write_text(json.dumps({"fecha": datetime.date.today().isoformat(), "bancos": salida}, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


if __name__ == "__main__":
    main()
