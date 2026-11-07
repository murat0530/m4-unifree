"""Ortak yapılar: bulgular, kural yükleme, ζ çözümleme, tablo yardımcıları."""
from __future__ import annotations

import copy
from dataclasses import dataclass, asdict, field
from pathlib import Path

import yaml

HATA, UYARI, BILGI = "HATA", "UYARI", "BİLGİ"
VARSAYILAN_KURALLAR = Path(__file__).with_name("kurallar_varsayilan.yaml")


class GirdiHatasi(ValueError):
    """Proje dosyasındaki eksik/hatalı girdi."""


@dataclass
class Bulgu:
    seviye: str
    modul: str
    nesne: str
    mesaj: str
    referans: str = ""

    def sozluk(self) -> dict:
        return asdict(self)


@dataclass
class Tablo:
    baslik: str
    kolonlar: list[str]
    satirlar: list[list] = field(default_factory=list)

    def sozluk(self) -> dict:
        return asdict(self)


@dataclass
class ModulSonucu:
    modul: str
    baslik: str
    ozet: dict = field(default_factory=dict)
    tablolar: list[Tablo] = field(default_factory=list)
    bulgular: list[Bulgu] = field(default_factory=list)

    def bulgu(self, seviye, nesne, mesaj, referans=""):
        self.bulgular.append(Bulgu(seviye, self.modul, nesne, mesaj, referans))

    def sozluk(self) -> dict:
        return {
            "modul": self.modul,
            "baslik": self.baslik,
            "ozet": self.ozet,
            "tablolar": [t.sozluk() for t in self.tablolar],
            "bulgular": [b.sozluk() for b in self.bulgular],
        }


def derin_birlestir(taban: dict, ek: dict) -> dict:
    sonuc = copy.deepcopy(taban)
    for k, v in (ek or {}).items():
        if isinstance(v, dict) and isinstance(sonuc.get(k), dict):
            sonuc[k] = derin_birlestir(sonuc[k], v)
        else:
            sonuc[k] = copy.deepcopy(v)
    return sonuc


def kurallari_yukle(*ekler: dict | str | Path | None) -> dict:
    with open(VARSAYILAN_KURALLAR, encoding="utf-8") as f:
        kurallar = yaml.safe_load(f)
    for ek in ekler:
        if ek is None:
            continue
        if isinstance(ek, (str, Path)):
            with open(ek, encoding="utf-8") as f:
                ek = yaml.safe_load(f) or {}
        kurallar = derin_birlestir(kurallar, ek)
    return kurallar


def zeta_topla(tanim, kutuphane: dict, nesne: str) -> float:
    """ζ tanımı: sayı | [ad, ad, sayı] | {ad: adet}. Toplam ζ döner."""
    if tanim is None:
        return 0.0
    if isinstance(tanim, (int, float)):
        return float(tanim)
    toplam = 0.0
    if isinstance(tanim, dict):
        ogeler = list(tanim.items())
    elif isinstance(tanim, list):
        ogeler = [(x, 1) for x in tanim]
    else:
        raise GirdiHatasi(f"{nesne}: zeta tanımı anlaşılamadı: {tanim!r}")
    for ad, adet in ogeler:
        if isinstance(ad, (int, float)):
            toplam += float(ad) * adet
        elif ad in kutuphane:
            toplam += float(kutuphane[ad]) * float(adet)
        else:
            raise GirdiHatasi(
                f"{nesne}: bilinmeyen yerel kayıp '{ad}'. Tanımlılar: {', '.join(sorted(kutuphane))}")
    return toplam


def armatur_say(tanim, kutuphane: dict, nesne: str) -> dict[str, float]:
    """{armatür: adet} doğrular."""
    if not tanim:
        return {}
    if isinstance(tanim, list):
        sayim: dict[str, float] = {}
        for a in tanim:
            sayim[a] = sayim.get(a, 0) + 1
        tanim = sayim
    for ad in tanim:
        if ad not in kutuphane:
            raise GirdiHatasi(
                f"{nesne}: bilinmeyen armatür '{ad}'. Tanımlılar: {', '.join(sorted(kutuphane))}")
    return {k: float(v) for k, v in tanim.items()}


def yuvarla(x, n=2):
    if x is None:
        return "-"
    if isinstance(x, float):
        return round(x, n)
    return x


def agac_sirala(hatlar: list[dict], ust_anahtar: str, nesne: str) -> list[dict]:
    """Hatları üstten alta (topolojik) sıralar, döngü/eksik üst kontrolü yapar."""
    idler = [h["id"] for h in hatlar]
    if len(set(idler)) != len(idler):
        tekrar = sorted({i for i in idler if idler.count(i) > 1})
        raise GirdiHatasi(f"{nesne}: tekrarlanan hat kimliği: {tekrar}")
    sozluk = {h["id"]: h for h in hatlar}
    for h in hatlar:
        u = h.get(ust_anahtar)
        if u is not None and u not in sozluk:
            raise GirdiHatasi(f"{nesne}: {h['id']} hattının '{ust_anahtar}' değeri '{u}' tanımlı değil")
    sira, ziyaret, yigin = [], set(), set()

    def gez(hid):
        if hid in ziyaret:
            return
        if hid in yigin:
            raise GirdiHatasi(f"{nesne}: hat ağacında döngü var ({hid})")
        yigin.add(hid)
        u = sozluk[hid].get(ust_anahtar)
        if u is not None:
            gez(u)
        yigin.discard(hid)
        ziyaret.add(hid)
        sira.append(sozluk[hid])

    for h in hatlar:
        gez(h["id"])
    return sira
