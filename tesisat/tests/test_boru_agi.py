"""DXF'ten boru ağı çıkarımı (G1–G5, D2, T5) ve otomatik iş akışı testleri."""
import shutil
from collections import Counter
from pathlib import Path

import ezdxf
import pytest
import yaml

from dxf_ornek import T12_X, uret_t12_plan
from tesisat import boru_agi, metraj
from tesisat.boru_agi import ag_cikar, cap_oku
from tesisat.cli import main
from tesisat.ortak import GirdiHatasi, kurallari_yukle

SABLON = Path(__file__).resolve().parents[1] / "sablonlar" / "yangin_ayar_sablonu.yaml"


@pytest.fixture
def plan(tmp_path):
    yol = tmp_path / "plan.dxf"
    uret_t12_plan(str(yol))
    return str(yol)


def cikar(yol, **k):
    return ag_cikar(yol, ["Y-BORU"], ["SPR*"], {"blok": "KOLON*"}, on_ek="A-", kat="Asma kat", **k)


@pytest.mark.parametrize("metin,dn", [("DN25", 25), ("dn 100", 100), ("Ø50", 50), ('1 1/4"', 32), ('1¼"', 32),
                                      ('2"', 50), ('2 1/2"', 65), ("Ø33.7", 25), ('3/4"', 20), ("KOLON", None),
                                      ("DN33", None)])
def test_cap_oku(metin, dn):
    assert cap_oku(metin) == dn


def test_t12_plani_agi(plan):
    r = cikar(plan)
    oz = r.ozet
    assert oz["sprinkler_agda"] == oz["sprinkler_cizimde"] == 16
    assert oz["birim"].startswith("mm")
    toplam = Counter()
    for h in r.hatlar:
        toplam[h["cap"]] += h["uzunluk_m"]
    # T12 metrajı kat başına: DN25 8×3,167; DN32 8×1,348 + 2,209 + 2,363; DN40 2,19+2,191; DN50 2,2+2,2+2,231; DN65 1,0
    assert toplam["25"] == pytest.approx(8 * 3.167, abs=1e-3)
    assert toplam["32"] == pytest.approx(8 * 1.348 + 2.209 + 2.363, abs=1e-3)
    assert toplam["40"] == pytest.approx(4.381, abs=1e-3)
    assert toplam["50"] == pytest.approx(6.631, abs=1e-3)
    assert toplam["65"] == pytest.approx(1.0, abs=1e-3)
    # D2: kollektör uçlarında dirsek (açıdan); T5: diklemesine çıkan branşlara te dönüş
    dirsek = sum((h.get("parcalar") or {}).get("dirsek_90", 0) for h in r.hatlar)
    assert dirsek == 2
    assert all(h["uzunluk_yontemi"] == "ölçülen" for h in r.hatlar)


def test_kesisme_baglanti_degil(plan):
    r = cikar(plan)
    assert any("BAĞLANTI SAYILMADI" in n for n in r.belirsizlikler)
    assert any("Kaynağa bağlı olmayan 2 düğüm" in n for n in r.belirsizlikler)


def test_metraj_topolojisi_t12_el_sayimiyla_ayni(plan):
    """Elle sayılmış T12 dişli fiting listesi (kat başına yarısı) ile topolojiden türetilen fittingler."""
    r = cikar(plan)
    hatlar = [{"id": "R", "ust": None, "uzunluk_m": 1, "cap": "80"}] + \
             [dict(h, ust=h["ust"] or "R") for h in r.hatlar]
    p = {"yangin": {"tehlike_sinifi": "YT1", "sprinkler_varsayilan": {"K": 80, "alan_m2": 6.97}, "hatlar": hatlar}}
    c = Counter()
    for s in metraj.metraj_cikar(p, kurallari_yukle()).satirlar:
        c[s.kod] += s.miktar
    assert c["FIT-TE-32x25x15"] == 8 and c["FIT-SPRUC-25x15"] == 8
    assert c["FIT-TE-40x32x32"] == 2 and c["FIT-TE-50x40x32"] == 2 and c["FIT-TE-50x50x32"] == 1
    assert c["FIT-COKLU-DN65-4YOL"] == 1 and c["FIT-DIRSEK90-DN32"] == 2 and c["FIT-RED-80x65"] == 1
    assert c["SPR-K80"] == 16


def test_etiketsiz_brans_cap_onerisi(tmp_path):
    yol = tmp_path / "p.dxf"
    uret_t12_plan(str(yol), etiketsiz_brans=6)
    r = cikar(str(yol))
    assert r.ozet["cap_onerilen_parca"] > 0
    assert any(h.get("cap_onerildi") for h in r.hatlar)
    assert any("ÖNERİLDİ" in n for n in r.belirsizlikler)


def test_dongu_hata(tmp_path):
    doc = ezdxf.new(units=6)
    msp = doc.modelspace()
    doc.blocks.new(name="KOLON").add_circle((0, 0), 0.1)
    for a, b in [((0, 0), (5, 0)), ((5, 0), (5, 5)), ((5, 5), (0, 5)), ((0, 5), (0, 0))]:
        msp.add_line(a, b, dxfattribs={"layer": "Y-BORU"})
    msp.add_blockref("KOLON", (0, 0))
    yol = tmp_path / "d.dxf"
    doc.saveas(yol)
    with pytest.raises(GirdiHatasi, match="döngü"):
        ag_cikar(str(yol), ["Y-BORU"], ["SPR*"], {"blok": "KOLON"})


def test_dwg_aciklayici_hata(tmp_path):
    from tesisat.otomatik import dwg_donustur
    with pytest.raises(GirdiHatasi, match="DXF"):
        dwg_donustur(tmp_path / "x.dwg", tmp_path)


def test_otomatik_uctan_uca(tmp_path, plan):
    assert Path(plan) == tmp_path / "plan.dxf"              # ayar şablonu 'plan.dxf' bekler
    shutil.copy(SABLON, tmp_path / "ayar.yaml")
    rc = main(["otomatik", str(tmp_path / "ayar.yaml"), "-o", str(tmp_path / "c")])
    assert rc == 1                                         # YT1: 260 m² tasarım alanı katlara sığmıyor → HATA
    for f in ("proje.yaml", "hidrolik_rapor.html", "metraj_teklif.xlsx", "ozet.md"):
        assert (tmp_path / "c" / f).exists()
    p = yaml.safe_load((tmp_path / "c" / "proje.yaml").read_text(encoding="utf-8"))
    assert sum(1 for h in p["yangin"]["hatlar"] if h.get("sprinkler")) == 32
    oz = (tmp_path / "c" / "ozet.md").read_text(encoding="utf-8")
    assert "TEKLİF TAMAMLANMADI" in oz and "FIT-COKLU-DN65-4YOL" in oz      # fiyatsız kalem uydurulmadı
    from tesisat.otomatik import calistir_otomatik
    r = calistir_otomatik(tmp_path / "ayar.yaml", tmp_path / "c2")
    assert 280_000 < r["teklif_kdv_haric"] < 360_000       # elle T12 hesabı: 307.202 TL (aynı fiyat esası)


def test_ayar_oner(plan, tmp_path):
    from tesisat.otomatik import ayar_oner
    r = ayar_oner(plan, tmp_path / "a.yaml")
    assert r["boru_katmani"][0] == "Y-BORU" and r["sprinkler_blok"][0] == "SPR_K80_SARKIK"
    assert r["kaynak_blok"] == ["KOLON_BESLEME"] and r["sprinkler_adedi"] == 16
    a = yaml.safe_load((tmp_path / "a.yaml").read_text(encoding="utf-8"))
    assert a["yangin"]["tehlike_sinifi"] == "★ SOR"               # tehlike sınıfı asla tahmin edilmez
