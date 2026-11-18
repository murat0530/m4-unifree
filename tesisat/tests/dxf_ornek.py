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


# --- T12 tipi tek kat sprinkler planı (mm, boru katmanı + inç çap etiketleri + sprinkler blokları)
T12_X = [0.0, 2.209, 4.399, 6.599, 8.799, 11.03, 13.221, 15.584]           # 1…8. branş kollektör konumları (m)
T12_KOL_ETIKET = ['1 1/4"', '1 1/2"', '2"', '2"', '2"', '1 1/2"', '1 1/4"']  # kollektör açıklıkları
T12_SPR2_Y, T12_SPR1_Y = 1.348, 1.348 + 3.167


def uret_t12_plan(yol, kesisen_cizgi=True, etiketsiz_brans=None):
    doc = ezdxf.new("R2013", units=4)
    for k in ("Y-BORU", "Y-BORU-YAZI", "Y-SPRINKLER", "A-DUVAR"):
        doc.layers.add(k)
    for ad in ("SPR_K80_SARKIK", "KOLON_BESLEME"):
        doc.blocks.new(name=ad).add_circle((0, 0), 80)
    msp = doc.modelspace()
    mm = lambda p: (p[0] * 1000, p[1] * 1000)  # noqa: E731
    # kollektör tek polyline (branşlar gövdesine T ile bağlanır)
    msp.add_lwpolyline([mm((T12_X[0], 0)), mm((T12_X[-1], 0))], dxfattribs={"layer": "Y-BORU"})
    for (x0, x1), et in zip(zip(T12_X, T12_X[1:]), T12_KOL_ETIKET):
        msp.add_text(et, dxfattribs={"layer": "Y-BORU-YAZI", "height": 100}).set_placement(mm(((x0 + x1) / 2, -0.25)))
    for i, x in enumerate(T12_X, 1):
        msp.add_line(mm((x, 0)), mm((x, T12_SPR1_Y)), dxfattribs={"layer": "Y-BORU"})
        if i != etiketsiz_brans:
            msp.add_text('1 1/4"', dxfattribs={"layer": "Y-BORU-YAZI", "height": 100}).set_placement(mm((x + 0.15, 0.7)))
            msp.add_text('1"', dxfattribs={"layer": "Y-BORU-YAZI", "height": 100}).set_placement(mm((x + 0.15, 3.0)))
        for y in (T12_SPR2_Y, T12_SPR1_Y):
            msp.add_blockref("SPR_K80_SARKIK", mm((x, y)), dxfattribs={"layer": "Y-SPRINKLER"})
    # besleme: 4. branş altından DN65, kaynak bloğu
    msp.add_line(mm((T12_X[3], -1.0)), mm((T12_X[3], 0)), dxfattribs={"layer": "Y-BORU"})
    msp.add_text("DN65", dxfattribs={"layer": "Y-BORU-YAZI", "height": 100}).set_placement(mm((T12_X[3] + 0.15, -0.6)))
    msp.add_blockref("KOLON_BESLEME", mm((T12_X[3], -1.0)), dxfattribs={"layer": "Y-BORU"})
    if kesisen_cizgi:   # başka bir hat 2. branşın üzerinden geçiyor — bağlantı DEĞİL
        msp.add_line(mm((1.5, 2.0)), mm((3.0, 2.0)), dxfattribs={"layer": "Y-BORU"})
    doc.saveas(yol)
