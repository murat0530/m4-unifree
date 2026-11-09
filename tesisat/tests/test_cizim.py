"""DXF okuma testleri: üretilen mimari DXF'ten mahal, ad, tip, sprinkler ve dolap okunur."""
import pytest

from dxf_ornek import ODALAR, uret
from tesisat import cizim
from tesisat.cli import main
from tesisat.ortak import GirdiHatasi


@pytest.fixture
def plan(tmp_path):
    yol = tmp_path / "plan.dxf"
    uret(str(yol), sprinkler=[(1.5, 11.5), (4.5, 14.5), (11.0, 1.0), (28.0, 18.0)], dolap=[(1.0, 9.6)])
    return str(yol)


def test_ozet(plan):
    o = cizim.dxf_ozet(plan)
    assert o["birim"].startswith("mm")
    assert o["kapali_cizgi"]["A-MAHAL"] == len(ODALAR)
    assert o["bloklar"]["SPR_PENDENT_K80"] == 4


def test_mahaller_birim_ve_alan(plan):
    o = cizim.dxf_oku(plan, ["A-MAHAL"], ["SPR*"], ["YANGIN*"], ["A-MAHAL-YAZI"])
    assert len(o["mahaller"]) == len(ODALAR)         # A-DUVAR'daki aynı çizgiler alınmadı
    kor = next(m for m in o["mahaller"] if m["ad"] == "POLİKLİNİK KORİDORU")
    assert kor["alan_m2"] == pytest.approx(60.0)      # mm → m dönüşümü
    assert sum(m["alan_m2"] for m in o["mahaller"]) == pytest.approx(600.0)


@pytest.mark.parametrize("ad,tip", [
    ("POLİKLİNİK KORİDORU", "poliklinik"), ("DİŞ TEDAVİ ÜNİTESİ 1", "muayene_tedavi"),
    ("ENDODONTİ", "muayene_tedavi"), ("CERRAHİ MÜDAHALE", "ameliyathane"), ("STERİLİZASYON", "sterilizasyon"),
    ("PANORAMİK RÖNTGEN", "goruntuleme"), ("ARŞİV", "arsiv"), ("DİŞ PROTEZ LAB.", "dis_protez_lab"),
    ("WC", "islak_hacim"), ("MEKANİK TESİSAT ODASI", "tesisat_odasi"), ("SARF DEPO", "depo"),
    ("BAŞHEKİM", None), ("HASTA BEKLEME", "poliklinik"), ("İDARİ OFİS", "buro"),
])
def test_tip_tahmini(ad, tip):
    assert cizim.tip_tahmin(ad) == tip


def test_sprinkler_dolap_mahal_atamasi(plan):
    o = cizim.dxf_oku(plan, ["A-MAHAL"], ["SPR*"], ["YANGIN*"])
    ad = {m["id"]: m["ad"] for m in o["mahaller"]}
    sp = {tuple(s["konum"]): ad[s["mahal"]] for s in o["sprinklerler"]}
    assert sp[(1.5, 11.5)] == "DİŞ TEDAVİ ÜNİTESİ 1"
    assert sp[(11.0, 1.0)] == "WC"
    assert sp[(28.0, 18.0)] == "ARŞİV"
    assert ad[o["dolaplar"][0]["mahal"]] == "POLİKLİNİK KORİDORU"


def test_belirsiz_tip_uyarisi(tmp_path):
    yol = tmp_path / "p.dxf"
    uret(str(yol), ekstra_bilinmeyen=True)
    o = cizim.dxf_oku(str(yol), ["A-MAHAL"])
    assert any("tahmin edilemedi" in u for u in o["uyarilar"])
    assert any(m.get("tip_belirsiz") for m in o["mahaller"])


def test_hatalar(tmp_path, plan):
    with pytest.raises(GirdiHatasi, match="DXF"):
        cizim.dxf_oku(str(tmp_path / "plan.dwg"), ["A-MAHAL"])
    with pytest.raises(GirdiHatasi, match="kapalı mahal sınırı"):
        cizim.dxf_oku(plan, ["YOK-KATMAN"])


def test_cli(plan, tmp_path, capsys):
    cikti = tmp_path / "m.yaml"
    assert main(["dxf-oku", plan, "--mahal-katmani", "A-MAHAL", "--sprinkler-blok", "SPR*",
                 "--kat", "3", "-o", str(cikti)]) == 0
    assert "3-M01" in cikti.read_text(encoding="utf-8")
    assert main(["dxf-ozet", plan]) == 0
    assert "A-MAHAL" in capsys.readouterr().out
