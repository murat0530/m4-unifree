"""Yangın tesisatı metraj motoru — MİKTAR üretir, fiyat üretmez.

Girdi: hesaplanmış ağ modeli (yangin.YanginAgi). Çıktı: detay metraj satırları,
belirsizlikler ve iç tutarlılık kontrolleri. Fiyat ve poz ayrı tabloda tutulur
(metraj_excel.py → "Fiyatlar" sayfası); burada hiçbir poz numarası üretilmez.

Her satırın "çıkarım yöntemi" şunlardan biridir:
  ölçülen         çizimden (DXF) doğrudan ölçülen uzunluk/konum
  hesaplanan      ağ topolojisi veya yazılı bir kuraldan türetilen miktar
  elle girilen    proje dosyasına kullanıcının girdiği değer
  kontrol gerekli kural kesin karar veremedi; mühendis çizimden doğrulamalı

Fitting tanıma kuralları: METRAJ_KURALLARI.md (bu modülle birebir aynı tutulmalı).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from .ortak import GirdiHatasi
from .yangin import YanginAgi

OLCULEN, HESAPLANAN, ELLE, KONTROL = "ölçülen", "hesaplanan", "elle girilen", "kontrol gerekli"
YONTEMLER = (OLCULEN, HESAPLANAN, ELLE, KONTROL)

SERI_AD = {
    "CELIK_EN10255_ORTA": "Çelik boru TS EN 10255 orta seri",
    "CELIK_SCH40": "Çelik boru ASTM A53/A795 Sch 40",
}
VANA_AD = {
    "kelebek_vana": "Kelebek vana (izleme anahtarlı)",
    "surgulu_vana": "Sürgülü vana",
    "cekvalf": "Çekvalf",
    "alarm_vanasi": "Islak alarm vana istasyonu",
}
DIRSEK_AD = {"dirsek_90": "Dirsek 90°", "dirsek_45": "Dirsek 45°"}
CIKIS_AD = {
    "dolap_yari_sert": "Yangın dolabı, yarı-sert hortumlu (TS EN 671-1)",
    "dolap_yassi": "Yangın dolabı, yassı hortumlu (TS EN 671-2)",
    "hidrant": "Yer üstü yangın hidrantı",
}


@dataclass
class Satir:
    kod: str
    kalem: str
    sistem: str
    kat: str
    kaynak: str
    dn: str
    birim: str
    miktar: float
    yontem: str
    not_: str = ""

    def __post_init__(self):
        if self.yontem not in YONTEMLER:
            raise ValueError(f"geçersiz çıkarım yöntemi: {self.yontem}")


@dataclass
class Belirsizlik:
    kategori: str
    nesne: str
    aciklama: str
    kalem_kodu: str
    oneri: str


@dataclass
class Metraj:
    proje_adi: str
    satirlar: list[Satir] = field(default_factory=list)
    belirsizlikler: list[Belirsizlik] = field(default_factory=list)
    model: dict = field(default_factory=dict)        # iç tutarlılık kontrolü için modelden sayılar
    referans: dict | None = None                     # kontrol edilmiş metraj {kalem_kodu: miktar}


def _yontem(deger: str | None, varsayilan: str = ELLE) -> str:
    if deger is None:
        return varsayilan
    if deger not in YONTEMLER:
        raise GirdiHatasi(f"metraj: geçersiz yöntem '{deger}' (seçenekler: {', '.join(YONTEMLER)})")
    return deger


def metraj_cikar(proje: dict, kurallar: dict) -> Metraj:
    if "yangin" not in proje:
        raise GirdiHatasi("metraj: projede 'yangin' bölümü yok")
    g = proje["yangin"]
    ag = YanginAgi(g, kurallar)
    m = Metraj((proje.get("proje") or {}).get("ad", "Proje"))
    seri = ag.seri_ad
    malzeme = SERI_AD.get(seri, seri)

    # --- sistem sınıflaması: hattın aşağısındaki çıkış tipleri
    asagi: dict[str, set] = {}
    for hid in reversed(ag.sira):
        h = ag.hatlar[hid]
        tipler = set()
        if h.tip:
            tipler.add("sprinkler" if h.tip == "sprinkler" else "dolap")
        for c in ag.cocuk.get(hid, []):
            tipler |= asagi[c]
        asagi[hid] = tipler

    def sistem(hid):
        t = asagi[hid]
        if t == {"sprinkler"}:
            return "Yangın — sprinkler"
        if t == {"dolap"}:
            return "Yangın — dolap/hidrant"
        if t:
            return "Yangın — ortak besleme"
        return "Yangın — çıkışsız hat"

    def kat(h):
        return str(h.ham.get("kat", "")) or "-"

    # --- 1) Borular
    for hid in ag.sira:
        h = ag.hatlar[hid]
        if h.L <= 0:
            m.belirsizlikler.append(Belirsizlik("Boru", hid, "Hat uzunluğu 0 — metraja girmedi", "", "Uzunluğu girin"))
            continue
        not_ = f"düşey bileşen {abs(h.dz):.2f} m dahil" if abs(h.dz) > 1e-9 else ""
        m.satirlar.append(Satir(f"BORU-{seri}-DN{h.dn}", f"{malzeme} DN{h.dn}", sistem(hid), kat(h), hid,
                                str(h.dn), "m", round(h.L, 3), _yontem(h.ham.get("uzunluk_yontemi")), not_))
        if not asagi[hid]:
            m.belirsizlikler.append(Belirsizlik("Boru", hid, "Hattın aşağısında çıkış (sprinkler/dolap) yok",
                                                f"BORU-{seri}-DN{h.dn}", "Ölü hat mı, eksik çıkış mı? Çizimden kontrol"))

    # --- 2) Topolojiden fittingler (düğüm = hattın bitiş noktası)
    te_beyan = {hid for hid in ag.sira if (ag.hatlar[hid].ham.get("parcalar") or {}).get("te_donus")}
    for hid in ag.sira:
        p = ag.hatlar[hid]
        cocuklar = [ag.hatlar[c] for c in ag.cocuk.get(hid, [])]
        k = len(cocuklar)
        sis = sistem(hid)
        kaynak = f"{hid} bitiş düğümü"
        if k == 0:
            if not p.tip:
                m.belirsizlikler.append(Belirsizlik("Fitting", kaynak, "Kör uç (çıkışsız hat sonu) — tapa/kapak "
                                                    "gerekebilir", "", "Çizimden kontrol; tapa kalemi ekleyin"))
            continue
        if k == 1:
            c = cocuklar[0]
            if c.dn != p.dn:
                m.satirlar.append(Satir(f"FIT-RED-{p.dn}x{c.dn}", f"Redüksiyon DN{p.dn}×DN{c.dn}", sis, kat(p), kaynak,
                                        f"{p.dn}x{c.dn}", "adet", 1, HESAPLANAN,
                                        "Kural R1: tek çıkışlı düğümde çap değişimi"))
                if c.dn > p.dn:
                    m.belirsizlikler.append(Belirsizlik("Fitting", kaynak, f"Akış yönünde çap büyüyor (DN{p.dn}→DN{c.dn})",
                                                        f"FIT-RED-{p.dn}x{c.dn}", "Çap seçimini kontrol edin"))
            if c.id in te_beyan:
                m.belirsizlikler.append(Belirsizlik(
                    "Fitting", kaynak, f"Hidrolik girdide '{c.id}' için te beyan edilmiş, topolojide tek çıkış var "
                    "(uç bağlantı: dirsek mi, te + tapa mı?)", "", "Çizimden bağlantı tipini belirleyin; otomatik "
                    "kesinleştirilmedi"))
            continue
        if k == 2:
            # Kural T1: küçük çaplı çıkış = kol; eşitse te beyan edilen çıkış kol sayılır
            gecis, kol = sorted(cocuklar, key=lambda x: (-x.dn, x.id in te_beyan))
            a, b = gecis, kol
            m.satirlar.append(Satir(f"FIT-TE-{p.dn}x{kol.dn}", f"Te DN{p.dn}×DN{kol.dn}" +
                                    (" (eşit)" if kol.dn == p.dn else " (redüksiyonlu çıkış)"), sis, kat(p), kaynak,
                                    f"{p.dn}x{kol.dn}", "adet", 1, HESAPLANAN, "Kural T1: iki çıkışlı düğüm = 1 te"))
            if gecis.dn != p.dn:
                m.satirlar.append(Satir(f"FIT-RED-{p.dn}x{gecis.dn}", f"Redüksiyon DN{p.dn}×DN{gecis.dn}", sis, kat(p),
                                        kaynak, f"{p.dn}x{gecis.dn}", "adet", 1, HESAPLANAN,
                                        "Kural T2: te geçiş tarafında çap değişimi (redüksiyonlu te olarak da "
                                        "temin edilebilir)"))
            if a.dn == b.dn and a.dn != p.dn:
                m.belirsizlikler.append(Belirsizlik("Fitting", kaynak, f"İki çıkış da DN{a.dn}, giriş DN{p.dn}: hangi "
                                                    "kolun geçiş olduğu topolojiden belirlenemez",
                                                    f"FIT-TE-{p.dn}x{kol.dn}", "Çizimden geçiş yönünü belirleyin"))
            continue
        # k >= 3
        m.satirlar.append(Satir(f"FIT-COKLU-DN{p.dn}-{k + 1}YOL", f"{k + 1} yollu bağlantı DN{p.dn} "
                                "(kollektör / haç / ardışık te)", sis, kat(p), kaynak, str(p.dn), "adet", 1, KONTROL,
                                "Kural C1: üçten fazla çıkış — fiziksel çözüm çizimden belirlenmeli"))
        m.belirsizlikler.append(Belirsizlik("Fitting", kaynak, f"{k} çıkışlı düğüm ({', '.join(c.id for c in cocuklar)})"
                                            " — kollektör, haç veya ardışık te olabilir",
                                            f"FIT-COKLU-DN{p.dn}-{k + 1}YOL", "Çizimden belirleyip uygun kaleme çevirin"))

    # --- 3) Girdideki parça listesinden dirsek ve vanalar (hidrolik girdisi; geometriyle doğrulanmadı)
    for hid in ag.sira:
        h = ag.hatlar[hid]
        for ad, adet in (h.ham.get("parcalar") or {}).items():
            if ad in DIRSEK_AD:
                m.satirlar.append(Satir(f"FIT-{ad.upper().replace('_', '')}-DN{h.dn}", f"{DIRSEK_AD[ad]} DN{h.dn}",
                                        sistem(hid), kat(h), hid, str(h.dn), "adet", float(adet), ELLE,
                                        "Kural D1: hidrolik parça listesinden; geometriyle doğrulanmadı"))
            elif ad in VANA_AD:
                m.satirlar.append(Satir(f"VANA-{ad.upper()}-DN{h.dn}", f"{VANA_AD[ad]} DN{h.dn}", sistem(hid), kat(h),
                                        hid, str(h.dn), "adet", float(adet), ELLE, "Kural V1: hidrolik parça listesinden"))

    # --- 4) Çıkış elemanları
    for hid in ag.cikislar:
        h = ag.hatlar[hid]
        yontem = _yontem(h.ham.get("konum_yontemi"))
        if h.tip == "sprinkler":
            m.satirlar.append(Satir(f"SPR-K{int(round(h.K))}", f"Sprinkler başlığı K{int(round(h.K))} "
                                    "(tip/sıcaklık/tepki belirtilmedi)", sistem(hid), kat(h), hid, "", "adet", 1,
                                    yontem, f"mahal {h.mahal or '-'}, sınıf {h.sinif_kod}"))
        else:
            m.satirlar.append(Satir(f"CIKIS-{h.tip.upper()}", CIKIS_AD.get(h.tip, h.tip), sistem(hid), kat(h), hid, "",
                                    "adet", 1, yontem, ""))
    if ag.sprinklerler:
        m.belirsizlikler.append(Belirsizlik(
            "Sprinkler", "tümü", "Sprinkler tipi (sarkık/dik/yan duvar), sıcaklık sınıfı ve tepki süresi (standart/"
            "hızlı) projede tanımlı değil — tek kalem altında toplandı", "SPR-K80",
            "Mahal bazında tip ve sıcaklık sınıfını belirleyin (ör. hastane hasta alanlarında hızlı tepkili)"))
        yedek = g.get("yedek_sprinkler")
        if yedek:
            m.satirlar.append(Satir("SPR-YEDEK", "Yedek sprinkler (dolabı ve anahtarıyla)", "Yangın — sprinkler", "-",
                                    "yangin.yedek_sprinkler", "", "adet", float(yedek), ELLE, "BYKHY md. 96/8: en az 6"))

    # --- 5) Askı (yalnızca kural tanımlıysa)
    aralik = ((kurallar.get("metraj") or {}).get("aski_araligi_m")) or {}
    if aralik:
        toplam: dict[int, float] = {}
        for hid in ag.sira:
            h = ag.hatlar[hid]
            yatay = max(h.L - abs(h.dz), 0.0)
            toplam[h.dn] = toplam.get(h.dn, 0.0) + yatay
        for dn, L in sorted(toplam.items()):
            a = aralik.get(dn) or aralik.get(str(dn))
            if not a or L <= 0:
                continue
            m.satirlar.append(Satir(f"ASKI-DN{dn}", f"Boru askısı DN{dn}", "Yangın — tümü", "-", f"Σ yatay boru DN{dn}",
                                    str(dn), "adet", float(math.ceil(L / float(a))), HESAPLANAN,
                                    f"Kural A1: ⌈{L:.1f} m / {a} m⌉ (aralık kural dosyasından)"))
    else:
        m.belirsizlikler.append(Belirsizlik("Askı", "tümü", "Askı aralığı kuralı tanımlı değil — askı hesaplanmadı",
                                            "", "Firma/şartname askı aralığını kurallar_ek.metraj.aski_araligi_m "
                                            "olarak girin (DN → m)"))
    for kalem, neden in [("İşçilik", "işçilik birimi poz/firma kuralına bağlı — hesaplanmadı"),
                         ("Boya / korozyon koruması", "şartnameye bağlı — hesaplanmadı"),
                         ("Pompa grubu, depo, alarm/izleme", "ekipman kalemleri bu metraj kapsamı dışında")]:
        m.belirsizlikler.append(Belirsizlik(kalem, "tümü", neden, "", "Kural/şartname tanımlandığında eklenecek"))

    m.model = {
        "Σ boru uzunluğu (m)": round(sum(ag.hatlar[h].L for h in ag.sira), 3),
        "Sprinkler adedi": len(ag.sprinklerler),
        "Dolap/hidrant adedi": len(ag.cikislar) - len(ag.sprinklerler),
        "Ağ hattı adedi": len(ag.sira),
    }
    return m
