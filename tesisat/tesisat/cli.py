"""Komut satırı arayüzü.

    python -m tesisat hesapla proje.yaml -o rapor.html --json sonuc.json
    python -m tesisat kurallar            # varsayılan kural dosyasının yolu
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

from . import cizim, rapor, yangin
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
    oz = alt.add_parser("dxf-ozet", help="DXF katman/blok/yazı özetini göster (çizim standardını tanımak için)")
    oz.add_argument("dxf")
    ok = alt.add_parser("dxf-oku", help="DXF'ten mahal sınırları, adlar, sprinkler ve dolap konumlarını oku")
    ok.add_argument("dxf")
    ok.add_argument("--mahal-katmani", required=True, help="Virgülle ayrılmış katman desenleri, ör. 'A-MAHAL,ROOM*'")
    ok.add_argument("--sprinkler-blok", default="", help="Sprinkler blok adı desenleri, ör. 'SPR*'")
    ok.add_argument("--dolap-blok", default="", help="Yangın dolabı blok adı desenleri")
    ok.add_argument("--etiket-katmani", default="", help="Mahal adı yazılarının katmanları (boş: tümü)")
    ok.add_argument("--birim", choices=["mm", "cm", "m"], help="Çizim birimi ($INSUNITS yoksa)")
    ok.add_argument("--kat", help="Kat etiketi (kimlik ön eki), ör. '3'")
    ok.add_argument("-o", "--cikti", help="YAML çıktı (varsayılan: <dxf>_mahaller.yaml)")
    a = ap.parse_args(argv)

    def liste(x):
        return [t.strip() for t in x.split(",") if t.strip()]

    if a.komut == "dxf-ozet":
        try:
            o = cizim.dxf_ozet(a.dxf)
        except GirdiHatasi as e:
            print(f"GİRDİ HATASI: {e}", file=sys.stderr)
            return 2
        print(f"Birim: {o['birim']}")
        print("Katmanlar (varlık / kapalı çizgi / yazı):")
        for k, n in sorted(o["katmanlar"].items(), key=lambda t: -t[1]):
            print(f"  {k:30} {n:6} {o['kapali_cizgi'].get(k, 0):6} {o['yazi'].get(k, 0):6}")
        print("Bloklar (adet):")
        for k, n in sorted(o["bloklar"].items(), key=lambda t: -t[1]):
            print(f"  {k:30} {n:6}")
        print("Örnek yazılar:")
        for k, t in o["ornek_yazilar"]:
            print(f"  [{k}] {t}")
        return 0

    if a.komut == "dxf-oku":
        try:
            o = cizim.dxf_oku(a.dxf, liste(a.mahal_katmani), liste(a.sprinkler_blok), liste(a.dolap_blok),
                              liste(a.etiket_katmani) or None, a.birim, a.kat)
        except GirdiHatasi as e:
            print(f"GİRDİ HATASI: {e}", file=sys.stderr)
            return 2
        cikti = Path(a.cikti or Path(a.dxf).with_suffix("").as_posix() + "_mahaller.yaml")
        with open(cikti, "w", encoding="utf-8") as f:
            f.write(f"# {Path(a.dxf).name} dosyasından okundu — birim: {o['birim']}, koordinatlar metre\n")
            for u in o["uyarilar"]:
                f.write(f"# UYARI: {u}\n")
            yaml.safe_dump({k: o[k] for k in ("mahaller", "sprinklerler", "dolaplar")}, f,
                           allow_unicode=True, sort_keys=False, width=140)
        print(f"{len(o['mahaller'])} mahal, {len(o['sprinklerler'])} sprinkler, {len(o['dolaplar'])} dolap "
              f"okundu (birim {o['birim']}) → {cikti}")
        for m in o["mahaller"]:
            print(f"  {m['id']:8} {m['alan_m2']:8.2f} m²  {m.get('tip', '??? TİP BELİRSİZ'):18} {m['ad']}")
        for u in o["uyarilar"]:
            print(f"  UYARI: {u}")
        return 0

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
