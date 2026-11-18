"""Fiyat listesi: kalem kodu → (poz, KDV hariç birim fiyat, tarih, kaynak). Fiyat UYDURULMAZ:
listede eşleşmeyen kalem fiyatsız kalır ve teklif 'tamamlanmadı' görünür."""
from __future__ import annotations

import fnmatch
import re
from pathlib import Path

import yaml

from .ortak import derin_birlestir

VARSAYILAN = Path(__file__).parent / "fiyatlar" / "fiyat_listesi.yaml"


def yukle(ek: dict | None = None, yol: str | Path | None = None) -> dict:
    with open(yol or VARSAYILAN, encoding="utf-8") as f:
        liste = yaml.safe_load(f)
    if ek:
        kalemler = list(ek.get("kalemler") or []) + liste["kalemler"]   # proje kalemleri önce eşleşir
        liste = derin_birlestir(liste, {k: v for k, v in ek.items() if k != "kalemler"})
        liste["kalemler"] = kalemler
    return liste


def _dn(kod: str) -> int | None:
    m = re.search(r"DN(\d+)", kod) or re.search(r"-(\d+)x", kod)
    return int(m.group(1)) if m else None


def birim_fiyat(k: dict, p: dict) -> float:
    tur = k.get("tur", "Net")
    if tur == "ÇŞB":
        return round(float(k["ref"]) * p["guncelleme"] * (1 - p["iskonto"]), 2)
    if tur == "Tahmin":
        return round(float(k["tahmin"]) * (1 + p["genel_gider"]) * (1 + p["kar"]), 2)
    return round(float(k.get("net", 0)), 2)


def esle(kod: str, liste: dict) -> dict | None:
    p = liste["parametreler"]
    dn = _dn(kod)
    for k in liste["kalemler"]:
        if "kod" in k and k["kod"] != kod:
            continue
        if "desen" in k:
            if not fnmatch.fnmatch(kod, k["desen"]):
                continue
            if dn is not None and (("dn_min" in k and dn < k["dn_min"]) or ("dn_max" in k and dn > k["dn_max"])):
                continue
            if dn is None and ("dn_min" in k or "dn_max" in k):
                continue
        aciklama = {"ÇŞB": f"ÇŞB ref {k.get('ref')} × {p['guncelleme']} × (1−{p['iskonto']})",
                    "Tahmin": f"tahmin {k.get('tahmin')} × (1+GG {p['genel_gider']}) × (1+kâr {p['kar']})",
                    "Net": "net"}.get(k.get("tur", "Net"), "")
        return {"poz": k.get("poz", ""), "fiyat": birim_fiyat(k, p), "tarih": str(p.get("tarih", "")),
                "kaynak": f"{p.get('kaynak', '')} — {aciklama}" + (f" — {k['not']}" if k.get("not") else ""),
                "tur": k.get("tur", "Net")}
    return None
