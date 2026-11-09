"""Komut satırı arayüzü.

    python -m tesisat hesapla proje.yaml -o rapor.html --json sonuc.json
    python -m tesisat kurallar            # varsayılan kural dosyasının yolu
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

from . import rapor, yangin
from .ortak import HATA, UYARI, GirdiHatasi, VARSAYILAN_KURALLAR, kurallari_yukle

MODULLER = {
    "yangin": yangin.hesapla,
}
PLANLANAN = {"temiz_su", "atik_su", "havalandirma"}


def proje_yukle(yol: str | Path) -> dict:
    with open(yol, encoding="utf-8") as f:
        proje = yaml.safe_load(f) or {}
    if not isinstance(proje, dict):
        raise GirdiHatasi("Proje dosyası bir YAML sözlüğü olmalı")
    return proje


def calistir(proje: dict, kural_dosyasi: str | None = None):
    kurallar = kurallari_yukle(kural_dosyasi, proje.get("kurallar_ek"))
    sonuclar = []
    for ad, fn in MODULLER.items():
        if ad in proje:
            sonuclar.append(fn(proje, kurallar))
    eksik = sorted(PLANLANAN & set(proje))
    if not sonuclar:
        mesaj = "Projede hesaplanabilir bölüm yok (desteklenen: " + ", ".join(MODULLER) + ")"
        if eksik:
            mesaj += f". Henüz geliştirilmemiş bölümler: {', '.join(eksik)}"
        raise GirdiHatasi(mesaj)
    return sonuclar, eksik


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="tesisat", description="Mekanik tesisat hesap ve kontrol aracı")
    alt = ap.add_subparsers(dest="komut", required=True)
    h = alt.add_parser("hesapla", help="Proje dosyasını hesapla ve kontrol et")
    h.add_argument("proje")
    h.add_argument("-o", "--cikti", help="HTML rapor yolu (varsayılan: <proje>_rapor.html)")
    h.add_argument("--json", help="JSON sonuç yolu")
    h.add_argument("--kurallar", help="Ek kural dosyası (YAML) — varsayılanları ezer")
    alt.add_parser("kurallar", help="Varsayılan kural dosyasının yolunu yaz")
    a = ap.parse_args(argv)

    if a.komut == "kurallar":
        print(VARSAYILAN_KURALLAR)
        return 0

    try:
        proje = proje_yukle(a.proje)
        sonuclar, eksik = calistir(proje, a.kurallar)
    except GirdiHatasi as e:
        print(f"GİRDİ HATASI: {e}", file=sys.stderr)
        return 2

    cikti = Path(a.cikti or Path(a.proje).with_suffix("").as_posix() + "_rapor.html")
    cikti.write_text(rapor.html_rapor(proje, sonuclar), encoding="utf-8")
    if a.json:
        Path(a.json).write_text(rapor.json_rapor(proje, sonuclar), encoding="utf-8")

    c = rapor.sayac(sonuclar)
    for s in sonuclar:
        print(f"[{s.modul}] {s.baslik}")
        for k, v in s.ozet.items():
            print(f"    {k}: {v}")
    for s in sonuclar:
        for b in s.bulgular:
            if b.seviye in (HATA, UYARI):
                print(f"  {b.seviye:5} {b.modul}/{b.nesne}: {b.mesaj}" + (f"  [{b.referans}]" if b.referans else ""))
    if eksik:
        print(f"  NOT: henüz geliştirilmemiş bölümler atlandı: {', '.join(eksik)}")
    print(f"Sonuç: {c[HATA]} hata, {c[UYARI]} uyarı, {c['BİLGİ']} bilgi → {cikti}")
    return 1 if c[HATA] else 0
