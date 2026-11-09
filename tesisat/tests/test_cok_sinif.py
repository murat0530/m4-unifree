"""Çoklu tehlike sınıfı, mahal tipi kütüphanesi, kompartıman, yerleşim önerisi, otomatik senaryo."""
from pathlib import Path

import pytest

from tesisat import kapsama, yangin as y
from tesisat.cli import calistir, proje_yukle
from tesisat.ortak import BILGI, HATA, UYARI, GirdiHatasi, kurallari_yukle

K = kurallari_yukle()
KY = K["yangin"]
ORNEK = Path(__file__).resolve().parents[1] / "ornekler" / "dis_hastanesi.yaml"


def oda(mid, tip, x0, y0, x1, y1, **ek):
    return {"id": mid, "tip": tip, "poligon": [[x0, y0], [x1, y0], [x1, y1], [x0, y1]], **ek}


def kur(mahaller, bina=None, komp=None, senaryolar=None):
    hatlar = [{"id": "R", "ust": None, "uzunluk_m": 5, "cap": "100"}]
    for m in mahaller:
        kayit = KY["mahal_tipleri"].get(m.get("tip"), {})
        if kayit.get("muaf") or m.get("muaf"):
            continue
        sinif = m.get("tehlike_sinifi") or kayit.get("sinif")
        sc = KY["tehlike_siniflari"][sinif]
        pol = [tuple(p) for p in m["poligon"]]
        pts = kapsama.yerlesim_oner(pol, sc["max_aralik_m"], sc["max_alan_m2"], min(2.0, sc["max_aralik_m"] / 2),
                                    on_ek=f"{m['id']}-")
        hatlar.append({"id": f"{m['id']}-H", "ust": "R", "uzunluk_m": 4, "cap": "65"})
        for sid, p in pts.items():
            hatlar.append({"id": sid, "ust": f"{m['id']}-H", "uzunluk_m": 3, "cap": "32", "sprinkler": True,
                           "mahal": m["id"], "konum": list(p)})
    g = {"sprinkler_varsayilan": {"K": 80}, "mahaller": mahaller, "hatlar": hatlar,
         "pompa": {"adet_yedek": 1}, "yedek_sprinkler": 6}
    if komp is not None:
        g["kompartimanlar"] = komp
    if senaryolar is not None:
        g["senaryolar"] = senaryolar
    return {"bina": bina or {}, "yangin": g}


def bul(s, seviye, metin=""):
    return [b for b in s.bulgular if b.seviye == seviye and metin in b.mesaj]


def test_hastane_mahalleri_ot1_byky_ek1b():
    for tip in ("muayene_tedavi", "poliklinik", "hasta_odasi", "sterilizasyon", "goruntuleme"):
        assert KY["mahal_tipleri"][tip]["sinif"] == "OT1"
        assert "Hastaneler" in KY["mahal_tipleri"][tip]["kaynak"]
    assert KY["mahal_tipleri"]["tesisat_odasi"]["sinif"] == "OT3"   # Ek-1/B tesisat odaları
    assert KY["mahal_tipleri"]["otopark"]["sinif"] == "OT2"


def test_bina_sinifi_en_yuksek_md19():
    p = kur([oda("A", "muayene_tedavi", 0, 0, 6, 6), oda("B", "laboratuvar", 6, 0, 14, 6)])
    a = y.YanginAgi(p["yangin"], K)
    assert a.sinif_kod == "OT2" and a.tasarim_alani == 144
    assert a.hatlar["A-1"].sinif_kod == "OT1" and a.hatlar["B-1"].sinif_kod == "OT2"


def test_acik_sinif_kutuphaneyi_ezer_ve_kayda_gecer():
    p = kur([oda("A", "arsiv", 0, 0, 6, 4, tehlike_sinifi="OT2")])
    a = y.YanginAgi(p["yangin"], K)
    assert a.mahal_bilgi["A"]["sinif"] == "OT2"
    assert "kütüphane önerisi: OT3" in a.mahal_bilgi["A"]["kaynak"]


def test_benzesim_atamasi_uyari_verir():
    s = y.hesapla(kur([oda("L", "dis_protez_lab", 0, 0, 10, 8)]), K)
    assert bul(s, UYARI, "benzeşimle atandı")


def test_bilinmeyen_tip_girdi_hatasi():
    g = kur([oda("X", "poliklinik", 0, 0, 4, 4)])["yangin"]
    g["mahaller"] = [oda("X", "uzay_ussu", 0, 0, 4, 4)]
    with pytest.raises(GirdiHatasi, match="uzay_ussu"):
        y.YanginAgi(g, K)


def test_muaf_mahal_islak_hacim():
    s = y.hesapla(kur([oda("A", "muayene_tedavi", 0, 0, 6, 6), oda("W", "islak_hacim", 6, 0, 9, 6)]), K)
    assert not [b for b in bul(s, HATA) if b.nesne == "W"]
    assert [b for b in bul(s, BILGI) if b.nesne == "W"]


def test_kompartiman_saglik_1500_x2_ek4():
    # sprinklerli → 3000 m² sınır; 3200 m² beyan → HATA
    m = [oda("A", "poliklinik", 0, 0, 10, 10)]
    s = y.hesapla(kur(m, komp=[{"id": "K", "kullanim": "saglik", "mahaller": ["A"], "alan_m2": 3200}]), K)
    assert bul(s, HATA, "3200 m² > 3000 m²")
    s = y.hesapla(kur(m, komp=[{"id": "K", "kullanim": "saglik", "mahaller": ["A"], "alan_m2": 2900}]), K)
    assert not bul(s, HATA, "Kompartıman alanı")


def test_dusuk_tehlike_126m2():
    m = [oda("A", "poliklinik", 0, 0, 10, 15, tehlike_sinifi="DT")]
    s = y.hesapla(kur(m, komp=[{"id": "K", "kullanim": "saglik", "mahaller": ["A"]}]), K)
    assert bul(s, HATA, "DT için kompartıman ≤ 126 m²")


def test_senaryo_sinifi_tasarim_alani():
    # OT3 tesisat odası içeren senaryo 216 m² ister
    m = [oda("T", "tesisat_odasi", 0, 0, 4, 8), oda("U", "muayene_tedavi", 4, 0, 10, 8)]
    p = kur(m, senaryolar=[{"ad": "x", "acik": ["T-1", "T-2", "T-3"]}])
    s = y.hesapla(p, K)
    assert bul(s, HATA, "OT3 tasarım alanı 216 m²")


@pytest.mark.parametrize("pol,sinif", [
    ([(0, 0), (6, 0), (6, 6), (0, 6)], "OT1"),
    ([(0, 0), (10, 0), (10, 8), (0, 8)], "OT2"),
    ([(0, 0), (30, 0), (30, 2), (0, 2)], "OT1"),
    ([(0, 0), (12, 0), (12, 6), (6, 6), (6, 12), (0, 12)], "OT3"),
])
def test_yerlesim_onerisi_kurallari_saglar(pol, sinif):
    sc = KY["tehlike_siniflari"][sinif]
    dmax = min(2.0, sc["max_aralik_m"] / 2)
    pts = kapsama.yerlesim_oner(pol, sc["max_aralik_m"], sc["max_alan_m2"], dmax)
    a = kapsama.mahal_analizi(pol, pts, sc["max_aralik_m"], dmax, 2.0, sc["max_alan_m2"])
    assert not [t for t in a["ihlaller"] if t[0] != "yakin"]
    assert a["hucre_toplami"] == pytest.approx(kapsama.alan(pol))


def test_yerlesim_minimum_adet_6x6_ot1():
    sc = KY["tehlike_siniflari"]["OT1"]
    pts = kapsama.yerlesim_oner([(0, 0), (6, 0), (6, 6), (0, 6)], sc["max_aralik_m"], sc["max_alan_m2"], 2.0)
    assert len(pts) == 4   # 1–3 sprinkler aralık/alan kuralını sağlayamaz


def test_otomatik_senaryolar_alan_ve_bicim():
    sonuclar, _ = calistir(proje_yukle(ORNEK))
    s = sonuclar[0]
    ag = y.YanginAgi(proje_yukle(ORNEK)["yangin"], K)
    for sn in ag.otomatik_senaryolar("x"):
        spr = [i for i in sn["acik"] if ag.hatlar[i].tip == "sprinkler"]
        if not spr:
            continue
        sinif = ag.en_yuksek([ag.hatlar[i].sinif_kod for i in spr])
        assert sum(ag.hatlar[i].alan for i in spr) >= ag.tasarim_alani_of(sinif) - 1e-6
    assert not bul(s, UYARI, "1,2·√A")


def test_dis_hastanesi_ornegi():
    sonuclar, _ = calistir(proje_yukle(ORNEK))
    s = sonuclar[0]
    assert not bul(s, HATA)
    assert s.ozet["Tehlike sınıfı"].startswith("Orta Tehlike-3")    # tesisat odası (md. 19/1)
    assert bul(s, BILGI, "ZORUNLULUĞU")                              # 22 m, yataksız → zorunlu değil
    assert bul(s, BILGI, "Yangın dolabı zorunlu")                    # sağlık > 1000 m²


def test_saglik_30_50m_ustu_zorunlu():
    p = kur([oda("A", "poliklinik", 0, 0, 6, 6)], bina={"kullanim": "saglik", "yapi_yuksekligi_m": 31})
    assert bul(y.hesapla(p, K), BILGI, "Sprinkler zorunlu")
    p["bina"] = {"kullanim": "saglik", "yapi_yuksekligi_m": 22, "yatakli": True}
    assert bul(y.hesapla(p, K), BILGI, "yataklı tesis")
