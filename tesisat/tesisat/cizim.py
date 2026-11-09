"""AutoCAD DXF planından mahal sınırları, mahal adları, sprinkler ve dolap konumlarını okur.

DWG doğrudan okunamaz: AutoCAD'de "Farklı Kaydet → DXF" (AutoCAD 2013 veya üstü DXF) ile kaydedin.

Kurallar:
  * Mahal sınırı = mahal katmanındaki KAPALI LWPOLYLINE/POLYLINE (yay parçaları kirişle yaklaşıklanır)
  * Mahal adı = sınırın içinde kalan TEXT/MTEXT (etiket katmanı verilmezse tüm katmanlar)
  * Sprinkler / dolap = adı verilen desenle eşleşen blok (INSERT) ekleme noktaları
  * Birim: $INSUNITS (mm/cm/m); tanımsızsa çizim boyutundan tahmin edilir veya --birim ile verilir
Çıktı koordinatları METRE'dir ve yangin.mahaller / hatlar[].konum biçimine uygundur.
"""
from __future__ import annotations

import fnmatch
import re
from collections import Counter

from . import kapsama
from .ortak import GirdiHatasi

_BIRIM = {1: 0.0254, 2: 0.3048, 4: 0.001, 5: 0.01, 6: 1.0}
_TR = str.maketrans("İIıŞşĞğÜüÖöÇç", "IIISSGGUUOOCC")

# Mahal adı → tip (sıra önemli: özel olan önce). Eşleşmeyenler mühendis kararına bırakılır.
TIP_ANAHTARLARI = [
    ("islak_hacim", ["WC", "TUVALET", "LAVABO", "DUS", "BANYO", "ABDEST", "WC-"]),
    ("merdiven", ["MERDIVEN"]),
    ("asansor_kuyusu", ["ASANSOR"]),
    ("dis_protez_lab", ["PROTEZ"]),
    ("laboratuvar", ["LAB"]),
    ("arsiv", ["ARSIV"]),
    ("depo", ["DEPO", "AMBAR"]),
    ("tesisat_odasi", ["TESISAT", "MEKANIK", "KAZAN", "POMPA", "HIDROFOR", "JENERATOR", "KOMPRESOR",
                       "VAKUM", "SANTRAL"]),
    ("sterilizasyon", ["STERIL"]),
    ("goruntuleme", ["RONTGEN", "PANORAMIK", "TOMOGRAFI", "GORUNTULEME", "RADYOLOJI", "CBCT"]),
    ("ameliyathane", ["AMELIYAT", "CERRAHI"]),
    ("camasirhane", ["CAMASIR"]),
    ("otopark", ["OTOPARK"]),
    ("yemekhane", ["KAFETERYA", "YEMEK", "MUTFAK", "KANTIN"]),
    ("muayene_tedavi", ["MUAYENE", "UNITE", "TEDAVI", "PEDODONTI", "ENDODONTI", "ORTODONTI", "PERIODONTOLOJI",
                        "PROTETIK", "RESTORATIF", "AGIZ"]),
    ("buro", ["OFIS", "IDARI", "MUDUR", "BURO", "TOPLANTI", "SEKRETER", "HEKIM ODASI", "DOKTOR"]),
    ("poliklinik", ["KORIDOR", "BEKLEME", "HOL", "LOBI", "GIRIS", "POLIKLINIK", "DANISMA", "KAYIT", "VEZNE"]),
]


def normal(metin: str) -> str:
    return re.sub(r"\s+", " ", metin.translate(_TR).upper()).strip()


def tip_tahmin(ad: str) -> str | None:
    n = normal(ad)
    for tip, anahtarlar in TIP_ANAHTARLARI:
        for a in anahtarlar:
            if re.search(r"(^|[^A-Z])" + re.escape(a), n):
                return tip
    return None


def _eslesir(ad: str, desenler: list[str]) -> bool:
    return any(fnmatch.fnmatch(ad.upper(), d.upper()) for d in desenler)


def _ac(yol: str):
    try:
        import ezdxf
    except ImportError as e:  # pragma: no cover
        raise GirdiHatasi("DXF okumak için 'ezdxf' paketi gerekli: pip install ezdxf") from e
    if str(yol).lower().endswith(".dwg"):
        raise GirdiHatasi("DWG doğrudan okunamaz — AutoCAD'de 'Farklı Kaydet → DXF' ile kaydedin")
    try:
        return ezdxf.readfile(yol)
    except (IOError, ezdxf.DXFStructureError) as e:
        raise GirdiHatasi(f"DXF açılamadı: {e}") from e


def _olcek(doc, birim: str | None) -> tuple[float, str]:
    if birim:
        return {"mm": 0.001, "cm": 0.01, "m": 1.0}[birim], f"{birim} (kullanıcı)"
    kod = doc.header.get("$INSUNITS", 0)
    if kod in _BIRIM:
        return _BIRIM[kod], {4: "mm", 5: "cm", 6: "m", 1: "inç", 2: "ft"}[kod] + " ($INSUNITS)"
    # tanımsız: çizim genişliğinden tahmin (bina > 1000 birim ise mm)
    xs = []
    for e in doc.modelspace().query("LWPOLYLINE"):
        xs += [p[0] for p in e.get_points("xy")]
    genislik = (max(xs) - min(xs)) if xs else 0
    return (0.001, "mm (tahmin)") if genislik > 1000 else (1.0, "m (tahmin)")


def dxf_ozet(yol: str) -> dict:
    """Katmanlar, blok adları ve örnek yazılar — çizim standardını tanımak için."""
    doc = _ac(yol)
    msp = doc.modelspace()
    katman = Counter()
    kapali = Counter()
    yazi = Counter()
    for e in msp:
        k = e.dxf.layer
        katman[k] += 1
        if e.dxftype() in ("LWPOLYLINE", "POLYLINE") and e.closed:
            kapali[k] += 1
        if e.dxftype() in ("TEXT", "MTEXT"):
            yazi[k] += 1
    bloklar = Counter(e.dxf.name for e in msp.query("INSERT"))
    olcek, aciklama = _olcek(doc, None)
    ornek = [(e.dxf.layer, (e.plain_text() if e.dxftype() == "MTEXT" else e.dxf.text)[:40])
             for e in msp.query("TEXT MTEXT")][:25]
    return {"birim": aciklama, "katmanlar": dict(katman), "kapali_cizgi": dict(kapali), "yazi": dict(yazi),
            "bloklar": dict(bloklar), "ornek_yazilar": ornek}


def _cokgen(e, s) -> list[tuple[float, float]]:
    if e.dxftype() == "LWPOLYLINE":
        pts = [(x * s, y * s) for x, y in e.get_points("xy")]
    else:
        pts = [(v.dxf.location.x * s, v.dxf.location.y * s) for v in e.vertices]
    # kapanış tekrarı varsa at
    if len(pts) > 2 and abs(pts[0][0] - pts[-1][0]) < 1e-9 and abs(pts[0][1] - pts[-1][1]) < 1e-9:
        pts = pts[:-1]
    return [(round(float(x), 4), round(float(y), 4)) for x, y in pts]


def dxf_oku(yol: str, mahal_katmani: list[str], sprinkler_blok: list[str] | None = None,
            dolap_blok: list[str] | None = None, etiket_katmani: list[str] | None = None,
            birim: str | None = None, kat: str | None = None) -> dict:
    doc = _ac(yol)
    msp = doc.modelspace()
    s, birim_acik = _olcek(doc, birim)
    uyarilar = []

    cokgenler = []
    for e in msp.query("LWPOLYLINE POLYLINE"):
        if not _eslesir(e.dxf.layer, mahal_katmani) or not e.closed:
            continue
        if e.dxftype() == "LWPOLYLINE" and any(abs(b) > 1e-9 for *_, b in e.get_points("xyb")):
            uyarilar.append(f"{e.dxf.layer}: yaylı (bulge) mahal sınırı kirişlerle yaklaşıklandı")
        p = _cokgen(e, s)
        if len(p) >= 3 and kapsama.alan(p) > 0.5:
            cokgenler.append(p)
    if not cokgenler:
        raise GirdiHatasi(f"'{', '.join(mahal_katmani)}' katman(lar)ında kapalı mahal sınırı bulunamadı — "
                          "önce 'dxf-ozet' ile katman adlarını kontrol edin")

    yazilar = []
    for e in msp.query("TEXT MTEXT"):
        if etiket_katmani and not _eslesir(e.dxf.layer, etiket_katmani):
            continue
        metin = e.plain_text() if e.dxftype() == "MTEXT" else e.dxf.text
        nokta = e.dxf.insert
        yazilar.append(((nokta.x * s, nokta.y * s), " ".join(metin.split())))

    def en_kucuk_iceren(p):
        adaylar = [i for i, c in enumerate(cokgenler) if kapsama.icinde(p, c)]
        return min(adaylar, key=lambda i: kapsama.alan(cokgenler[i])) if adaylar else None

    adlar: dict[int, list[str]] = {}
    for p, metin in yazilar:
        i = en_kucuk_iceren(p)
        if i is not None and metin:
            adlar.setdefault(i, []).append(metin)

    on_ek = f"{kat}-" if kat else ""
    mahaller = []
    for i, c in enumerate(cokgenler):
        ad = " / ".join(adlar.get(i, [])) or f"Adsız mahal {i + 1}"
        tip = tip_tahmin(ad)
        m = {"id": f"{on_ek}M{i + 1:02d}", "ad": ad, "poligon": [list(p) for p in c],
             "alan_m2": round(float(kapsama.alan(c)), 2)}
        if kat:
            m["kat"] = kat
        if tip:
            m["tip"] = tip
        else:
            m["tip_belirsiz"] = True
            uyarilar.append(f"{m['id']} '{ad}': mahal tipi tahmin edilemedi — 'tip' veya 'tehlike_sinifi' girin")
        mahaller.append(m)

    def bloklar(desen, ad):
        cikti = []
        if not desen:
            return cikti
        for e in msp.query("INSERT"):
            if not _eslesir(e.dxf.name, desen):
                continue
            p = (round(float(e.dxf.insert.x) * s, 4), round(float(e.dxf.insert.y) * s, 4))
            i = en_kucuk_iceren(p)
            if i is None:
                uyarilar.append(f"{ad} bloğu {e.dxf.name} ({p[0]:.2f}, {p[1]:.2f}) hiçbir mahal içinde değil")
            cikti.append({"blok": e.dxf.name, "konum": list(p),
                          "mahal": mahaller[i]["id"] if i is not None else None})
        return cikti

    sprinklerler = bloklar(sprinkler_blok, "Sprinkler")
    for n, sp in enumerate(sprinklerler, 1):
        sp["id"] = f"{on_ek}S{n:03d}"
    dolaplar = bloklar(dolap_blok, "Dolap")
    for n, d in enumerate(dolaplar, 1):
        d["id"] = f"{on_ek}YD{n}"
    return {"birim": birim_acik, "mahaller": mahaller, "sprinklerler": sprinklerler, "dolaplar": dolaplar,
            "uyarilar": uyarilar}
