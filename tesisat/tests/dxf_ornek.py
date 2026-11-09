"""Testler için gerçekçi mimari DXF üretir (mm, Türkçe mahal adları, sprinkler/dolap blokları)."""
import ezdxf

ODALAR = [  # (ad, x0, y0, x1, y1) metre
    ("POLİKLİNİK KORİDORU", 0, 8, 30, 10), ("DİŞ TEDAVİ ÜNİTESİ 1", 0, 10, 6, 16),
    ("DİŞ TEDAVİ ÜNİTESİ 2", 6, 10, 12, 16), ("ENDODONTİ", 12, 10, 18, 16),
    ("CERRAHİ MÜDAHALE", 18, 10, 24, 16), ("STERİLİZASYON", 24, 10, 30, 16),
    ("HASTA BEKLEME", 0, 16, 18, 20), ("PANORAMİK RÖNTGEN", 18, 16, 24, 20),
    ("ARŞİV", 24, 16, 30, 20), ("DİŞ PROTEZ LAB.", 0, 0, 10, 8), ("WC", 10, 0, 14, 8),
    ("MEKANİK TESİSAT ODASI", 14, 0, 18, 8), ("SARF DEPO", 18, 0, 22, 8), ("BAŞHEKİM", 22, 0, 30, 8),
]


def uret(yol, sprinkler=None, dolap=None, ekstra_bilinmeyen=False):
    doc = ezdxf.new("R2013", units=4)  # mm
    for k in ("A-DUVAR", "A-MAHAL", "A-MAHAL-YAZI", "Y-SPRINKLER", "Y-DOLAP"):
        doc.layers.add(k)
    for ad in ("SPR_PENDENT_K80", "YANGIN_DOLABI"):
        b = doc.blocks.new(name=ad)
        b.add_circle((0, 0), 60)
    msp = doc.modelspace()
    odalar = list(ODALAR) + ([("PERSONEL ODASI X", 30, 0, 34, 8)] if ekstra_bilinmeyen else [])
    for ad, x0, y0, x1, y1 in odalar:
        pts = [(x0 * 1000, y0 * 1000), (x1 * 1000, y0 * 1000), (x1 * 1000, y1 * 1000), (x0 * 1000, y1 * 1000)]
        msp.add_lwpolyline(pts, close=True, dxfattribs={"layer": "A-MAHAL"})
        msp.add_lwpolyline(pts, close=True, dxfattribs={"layer": "A-DUVAR"})   # duvar çizgisi (yok sayılmalı)
        msp.add_text(ad, dxfattribs={"layer": "A-MAHAL-YAZI", "height": 200}).set_placement(
            ((x0 + x1) / 2 * 1000, (y0 + y1) / 2 * 1000))
    msp.add_text("KAT PLANI 1/50", dxfattribs={"layer": "A-MAHAL-YAZI"}).set_placement((50000, 50000))
    for x, y in sprinkler or []:
        msp.add_blockref("SPR_PENDENT_K80", (x * 1000, y * 1000), dxfattribs={"layer": "Y-SPRINKLER"})
    for x, y in dolap or []:
        msp.add_blockref("YANGIN_DOLABI", (x * 1000, y * 1000), dxfattribs={"layer": "Y-DOLAP"})
    doc.saveas(yol)
