"""Yangın tesisatı metraj motoru — MİKTAR üretir, fiyat ve poz üretmez.

Girdi: ağ modeli (yangin.YanginAgi). Çıktı: detay metraj satırları, belirsizlikler
(her biri numaralı ve ilgili satırlara bağlı) ve iç tutarlılık sayıları.

İki ayrı kavram:
  * ÇIKARIM YÖNTEMİ — miktar nereden geldi:
        ölçülen | hesaplanan | elle girilen | kontrol gerekli
  * ONAY DURUMU — satır teklife girebilir mi (Excel'de formülle):
        belirsizlik açık | onay bekliyor | onaylandı
    Bir satıra bağlı açık belirsizlik varsa, yöntemi ne olursa olsun "belirsizlik açık"tır.

Kurallar: METRAJ_KURALLARI.md (bu modülle birebir aynı tutulmalı).
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field

from .ortak import GirdiHatasi
from .yangin import YanginAgi

OLCULEN, HESAPLANAN, ELLE, KONTROL = "ölçülen", "hesaplanan", "elle girilen", "kontrol gerekli"
YONTEMLER = (OLCULEN, HESAPLANAN, ELLE, KONTROL)
# Belirsizliğin teklife etkisi
ETKI_MIKTAR, ETKI_TANIM, ETKI_KAPSAM = "miktar", "kalem tanımı", "kapsam"

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
    belirsizlik_ids: list[str] = field(default_factory=list)

    def __post_init__(self):
        if self.yontem not in YONTEMLER:
            raise ValueError(f"geçersiz çıkarım yöntemi: {self.yontem}")


@dataclass
class Belirsizlik:
    kategori: str
    nesne: str
    aciklama: str
    oneri: str
    etki: str = ETKI_MIKTAR
    bag_kaynak: tuple[str, ...] = ()      # bu kaynak nesnelerin satırlarına bağlanır
    bag_kod_on_ek: str | None = None      # ve/veya kodu bu önekle başlayan satırlara
    id: str = ""
    kalem_kodlari: list[str] = field(default_factory=list)


@dataclass
class Metraj:
    proje_adi: str
    satirlar: list[Satir] = field(default_factory=list)
    belirsizlikler: list[Belirsizlik] = field(default_factory=list)
    model: dict = field(default_factory=dict)
    referans: dict | None = None


def _yontem(deger: str | None, varsayilan: str = ELLE) -> str:
    if deger is None:
        return varsayilan
    if deger not in YONTEMLER:
        raise GirdiHatasi(f"metraj: geçersiz yöntem '{deger}' (seçenekler: {', '.join(YONTEMLER)})")
    return deger


def _baglanti(ayar: dict, dn: int) -> str | None:
    """Bağlantı yöntemi: tek değer veya {"<=50": "dişli", ">=65": "yivli"} biçiminde DN aralıkları."""
    b = ayar.get("baglanti_yontemi")
    if b is None or isinstance(b, str):
        return b
    for anahtar, deger in b.items():
        a = str(anahtar).replace(" ", "")
        if (a.startswith("<=") and dn <= int(a[2:])) or (a.startswith(">=") and dn >= int(a[2:])) \
                or (a.isdigit() and dn == int(a)):
            return deger
    return None


def metraj_cikar(proje: dict, kurallar: dict) -> Metraj:
    if "yangin" not in proje:
        raise GirdiHatasi("metraj: projede 'yangin' bölümü yok")
    g = proje["yangin"]
    ag = YanginAgi(g, kurallar)
    m = Metraj((proje.get("proje") or {}).get("ad", "Proje"))
    ayar = g.get("metraj") or {}
    seri = ag.seri_ad
    malzeme = SERI_AD.get(seri, seri)
    fit_sinif = ayar.get("fitting_malzeme")

    def fit_ek(dn):
        parca = [x for x in (_baglanti(ayar, dn), fit_sinif) if x]
        return f" — {', '.join(parca)}" if parca else ""

    def belirsiz(*a, **k):
        m.belirsizlikler.append(Belirsizlik(*a, **k))

    # --- sistem sınıflaması: hattın aşağısındaki çıkış tipleri
    asagi: dict[str, set] = {}
    for hid in reversed(ag.sira):
        h = ag.hatlar[hid]
        tipler = {("sprinkler" if h.tip == "sprinkler" else "dolap")} if h.tip else set()
        for c in ag.cocuk.get(hid, []):
            tipler |= asagi[c]
        asagi[hid] = tipler

    def sistem(hid):
        t = asagi[hid]
        if t == {"sprinkler"}:
            return "Yangın — sprinkler"
        if t == {"dolap"}:
            return "Yangın — dolap/hidrant"
        return "Yangın — ortak besleme" if t else "Yangın — çıkışsız hat"

    def kat(h):
        return str(h.ham.get("kat", "")) or "-"

    # --- 1) Borular (B1–B3)
    for hid in ag.sira:
        h = ag.hatlar[hid]
        if h.L <= 0:
            belirsiz("Boru", hid, "Hat uzunluğu 0 — metraja girmedi", "Uzunluğu girin", ETKI_MIKTAR)
            continue
        not_ = f"düşey bileşen {abs(h.dz):.2f} m dahil" if abs(h.dz) > 1e-9 else ""
        m.satirlar.append(Satir(f"BORU-{seri}-DN{h.dn}", f"{malzeme} DN{h.dn}", sistem(hid), kat(h), hid,
                                str(h.dn), "m", round(h.L, 3), _yontem(h.ham.get("uzunluk_yontemi")), not_))
        if h.ham.get("cap_onerildi"):
            belirsiz("Boru", hid, f"Çap etiketi çizimde bulunamadı; DN{h.dn} beslenen sprinkler sayısından ÖNERİLDİ",
                     "Çizimdeki çap etiketini ekleyin veya çapı doğrulayın", ETKI_TANIM, bag_kaynak=(hid,))
        if not asagi[hid]:
            belirsiz("Boru", hid, "Hattın aşağısında çıkış (sprinkler/dolap) yok", "Ölü hat mı, eksik çıkış mı? "
                     "Çizimden kontrol", ETKI_MIKTAR, bag_kaynak=(hid,))

    # --- 2) Topolojiden fittingler (düğüm = hattın bitiş noktası)
    te_beyan = {hid for hid in ag.sira if (ag.hatlar[hid].ham.get("parcalar") or {}).get("te_donus")}
    for hid in ag.sira:
        p = ag.hatlar[hid]
        cocuklar = [ag.hatlar[c] for c in ag.cocuk.get(hid, [])]
        k = len(cocuklar)
        sis = sistem(hid)
        dugum = f"{hid} bitiş düğümü"
        spr_cikis = p.tip == "sprinkler"
        if k == 0:
            if not p.tip:   # K0
                belirsiz("Fitting", dugum, "Kör uç (çıkışsız hat sonu) — tapa/kapak gerekebilir",
                         "Çizimden kontrol; tapa kalemi ekleyin", ETKI_MIKTAR, bag_kaynak=(hid,))
            elif spr_cikis:   # E1: hat ucundaki sprinkler bağlantısı (½")
                m.satirlar.append(Satir(f"FIT-SPRUC-{p.dn}x15", f"Sprinkler uç bağlantısı DN{p.dn}×½\" (redüksiyonlu "
                                        f"dirsek veya redüksiyonlu manşon){fit_ek(p.dn)}", sis, kat(p), dugum,
                                        f"{p.dn}x15", "adet", 1, HESAPLANAN,
                                        "Kural E1: hat ucunda sprinkler — bağlantı parçası var, tipi geometriye bağlı"))
            continue
        if k == 1 and spr_cikis:   # T4: hat ortasında sprinkler çıkışı → giriş × geçiş × ½"
            c = cocuklar[0]
            m.satirlar.append(Satir(f"FIT-TE-{p.dn}x{c.dn}x15", f"Te {p.dn}×{c.dn}×½\" (sprinkler çıkışlı)"
                                    f"{fit_ek(p.dn)}", sis, kat(p), dugum, f"{p.dn}x{c.dn}x15", "adet", 1, HESAPLANAN,
                                    "Kural T4: hat ortasında sprinkler çıkışı = 1 te (çap değişimi te içinde)"))
            continue
        if k >= 2 and spr_cikis:   # sprinkler çıkışı + 2 devam → 4 yollu
            k += 1
        if k == 1:
            c = cocuklar[0]
            if c.dn != p.dn:   # R1
                m.satirlar.append(Satir(f"FIT-RED-{p.dn}x{c.dn}", f"Redüksiyon DN{p.dn}×DN{c.dn}{fit_ek(p.dn)}", sis,
                                        kat(p), dugum, f"{p.dn}x{c.dn}", "adet", 1, HESAPLANAN,
                                        "Kural R1: tek çıkışlı düğümde çap değişimi"))
                if c.dn > p.dn:   # R1a
                    belirsiz("Fitting", dugum, f"Akış yönünde çap büyüyor (DN{p.dn}→DN{c.dn})", "Çap seçimini kontrol "
                             "edin", ETKI_MIKTAR, bag_kaynak=(dugum,))
            if c.id in te_beyan:   # R2: eksik olabilecek bağlantı parçası
                belirsiz("Fitting", dugum, f"Hidrolik girdide '{c.id}' için te beyan edilmiş, topolojide tek çıkış "
                         "var — uç bağlantı dirsek mi, te + tapa mı? Bu bağlantı parçası metrajda YOK.",
                         "Çizimden bağlantı tipini belirleyip kalemi ekleyin", ETKI_MIKTAR,
                         bag_kaynak=(dugum, c.id))
            continue
        if k == 2 and not spr_cikis:   # T1: üç ağızlı te (giriş × geçiş × kol)
            gecis, kol = sorted(cocuklar, key=lambda x: (-x.dn, x.id in te_beyan))
            esit = p.dn == gecis.dn == kol.dn
            ad = (f"Te {p.dn}×{gecis.dn}×{kol.dn} (giriş×geçiş×kol)" +
                  (" eşit" if esit else " redüksiyonlu") + fit_ek(p.dn))
            not_ = "Kural T1: iki çıkışlı düğüm = 1 te."
            if gecis.dn != p.dn:
                not_ += (f" Satın alma alternatifi: eşit te DN{p.dn} + redüksiyon {p.dn}×{gecis.dn} — "
                         "alternatif ayrıca SAYILMAZ.")
            m.satirlar.append(Satir(f"FIT-TE-{p.dn}x{gecis.dn}x{kol.dn}", ad, sis, kat(p), dugum,
                                    f"{p.dn}x{gecis.dn}x{kol.dn}", "adet", 1, HESAPLANAN, not_))
            continue
        # C1: k ≥ 3
        m.satirlar.append(Satir(f"FIT-COKLU-DN{p.dn}-{k + 1}YOL", f"{k + 1} yollu bağlantı DN{p.dn} (kollektör / haç / "
                                f"ardışık te){fit_ek(p.dn)}", sis, kat(p), dugum, str(p.dn), "adet", 1, KONTROL,
                                "Kural C1: üçten fazla çıkış — fiziksel çözüm çizimden belirlenmeli"))
        belirsiz("Fitting", dugum, f"{k} çıkışlı düğüm ({', '.join(c.id for c in cocuklar)}) — kollektör, haç veya "
                 "ardışık te olabilir", "Çizimden belirleyip uygun kaleme çevirin", ETKI_TANIM, bag_kaynak=(dugum,))

    # --- 3) Girdideki parça listesinden dirsek ve vanalar (D1, V1)
    for hid in ag.sira:
        h = ag.hatlar[hid]
        for ad, adet in (h.ham.get("parcalar") or {}).items():
            if ad in DIRSEK_AD:
                m.satirlar.append(Satir(f"FIT-{ad.upper().replace('_', '')}-DN{h.dn}", f"{DIRSEK_AD[ad]} DN{h.dn}"
                                        f"{fit_ek(h.dn)}", sistem(hid), kat(h), hid, str(h.dn), "adet", float(adet),
                                        ELLE, "Kural D1: hidrolik parça listesinden; geometriyle doğrulanmadı"))
            elif ad in VANA_AD:
                m.satirlar.append(Satir(f"VANA-{ad.upper()}-DN{h.dn}", f"{VANA_AD[ad]} DN{h.dn}", sistem(hid), kat(h),
                                        hid, str(h.dn), "adet", float(adet), ELLE, "Kural V1: hidrolik parça listesinden"))
    if any(s.kod.startswith("FIT-DIRSEK") for s in m.satirlar):
        belirsiz("Fitting", "dirsekler", "Dirsek adetleri hidrolik eşdeğer boy için girilmiş parça listesinden; boru "
                 "güzergâh geometrisi olmadığından fiziksel dirsek sayısı doğrulanamadı",
                 "DXF boru katmanından güzergâh okununca açı kuralıyla (D2) yeniden sayılacak", ETKI_MIKTAR,
                 bag_kod_on_ek="FIT-DIRSEK")
    if any(s.kod.startswith("FIT-SPRUC") for s in m.satirlar):
        belirsiz("Fitting", "uç sprinklerler", "Hat ucundaki sprinkler bağlantısının tipi (redüksiyonlu dirsek / "
                 "redüksiyonlu manşon) boru geometrisi olmadan belirlenemez — adet kesin, tanım değil",
                 "Çizimden sprinklerin borunun altında mı ucunda mı olduğunu belirleyin", ETKI_TANIM,
                 bag_kod_on_ek="FIT-SPRUC")
    if _baglanti(ayar, 25) is None or _baglanti(ayar, 100) is None or not fit_sinif:
        belirsiz("Fitting", "tümü", "Fitting bağlantı yöntemi (dişli / kaynaklı / yivli) ve/veya malzeme sınıfı "
                 "(ör. TS EN 10242 temper döküm, TS EN 10253 kaynaklı) tüm çaplar için tanımlı değil — satın alma "
                 "tanımı eksik", "yangin.metraj.baglanti_yontemi ({'<=50': 'dişli', '>=65': 'yivli'}) ve "
                 "fitting_malzeme girin", ETKI_TANIM, bag_kod_on_ek="FIT-")

    # --- 3b) Yivli kaplin (K1, ÖN HESAP): yalnız YİVLİ ağızlar (ağız çapı yivli aralıktaysa) + boru boy ekleri
    yivli: dict[int, float] = {}

    def agizlar(s):
        """Kalem kodundan ağız çapları: TE-a x b x c → [a,b,c]; RED-axb → [a,b]; DIRSEK-DNa → [a,a];
        VANA-…-DNa → [a,a]; COKLU-DNa → [a] (çıkış çapları bilinmiyor)."""
        if s.kod.startswith(("FIT-TE", "FIT-RED")):
            return [int(x) for x in re.findall(r"\d+", s.dn)]
        if s.kod.startswith(("FIT-DIRSEK", "VANA-KELEBEK")):
            return [int(s.dn)] * 2
        if s.kod.startswith("FIT-COKLU"):
            return [int(s.dn)]
        return []

    for s in list(m.satirlar):
        if s.kod.startswith("BORU-"):
            dn = int(s.dn)
            if _baglanti(ayar, dn) == "yivli":
                yivli[dn] = yivli.get(dn, 0) + max(0, math.ceil(s.miktar / float(ayar.get("boru_boyu_m", 6.0))) - 1)
            continue
        for a in agizlar(s):
            if a != 15 and _baglanti(ayar, a) == "yivli":
                yivli[a] = yivli.get(a, 0) + s.miktar
    for dn, n in sorted(yivli.items()):
        if n:
            m.satirlar.append(Satir(f"YIVLI-KAPLIN-DN{dn}", f"Yivli kaplin DN{dn} (ÖN HESAP)", "Yangın — tümü", "-",
                                    "kural K1", str(dn), "adet", float(n), HESAPLANAN,
                                    "Kural K1: yivli parça/vana ağzı başına 1 + ⌈boy/6 m⌉−1 boru eki; ağız çapı "
                                    "yivli aralıkta değilse sayılmaz"))
    if yivli:
        belirsiz("Fitting", "yivli kaplinler", "Yivli kaplin adedi ön hesaptır (parça ağzı + boru boyu ekleri); "
                 "ortak bağlantı uçları ve ekipman (alarm vanası vb.) bağlantıları ayrıca belirlenmeli",
                 "Çizimdeki kaplin bloklarından saydırın veya montaj detayından kesinleştirin", ETKI_MIKTAR,
                 bag_kod_on_ek="YIVLI-KAPLIN")

    # --- 4) Çıkış elemanları (S1, O1)
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
        belirsiz("Sprinkler", "tümü", "Sprinkler tipi (sarkık/dik/yan duvar), sıcaklık sınıfı ve tepki süresi "
                 "(standart/hızlı) tanımlı değil — tek kalem altında toplandı", "Mahal bazında tip ve sıcaklık "
                 "sınıfını belirleyin", ETKI_TANIM, bag_kod_on_ek="SPR-K")
        # S2–S4: yedek sprinkler, dolabı ve anahtarı AYRI kalemler
        yedek = g.get("yedek_sprinkler")
        k80 = sorted({int(round(ag.hatlar[i].K)) for i in ag.sprinklerler})
        if yedek:
            m.satirlar.append(Satir("SPR-YEDEK-BASLIK", f"Yedek sprinkler başlığı (K{'/K'.join(map(str, k80))})",
                                    "Yangın — sprinkler", "-", "yangin.yedek_sprinkler", "", "adet", float(yedek), ELLE,
                                    "Kural S2: BYKHY md. 96/8 en az 6"))
        dolap = ayar.get("yedek_dolap_adet")
        anahtar = ayar.get("sprinkler_anahtari_adet")
        m.satirlar.append(Satir("SPR-YEDEK-DOLAP", "Yedek sprinkler dolabı (kabin)", "Yangın — sprinkler", "-",
                                "yangin.metraj.yedek_dolap_adet" if dolap else "kural S3", "", "adet",
                                float(dolap or 1), ELLE if dolap else HESAPLANAN,
                                "Kural S3: girilmemişse tesis başına 1 (varsayım)"))
        m.satirlar.append(Satir("SPR-ANAHTAR", "Sprinkler değiştirme anahtarı", "Yangın — sprinkler", "-",
                                "yangin.metraj.sprinkler_anahtari_adet" if anahtar else "kural S4", "", "adet",
                                float(anahtar or len(k80)),
                                ELLE if anahtar else HESAPLANAN,
                                "Kural S4: girilmemişse sprinkler tipi (K) başına 1 (varsayım); BYKHY md. 96/8"))
        if not dolap or not anahtar:
            belirsiz("Sprinkler", "yedek dolap/anahtar", "Yedek sprinkler dolabı ve/veya anahtar adedi girilmedi; "
                     "varsayım kuralıyla (S3/S4) hesaplandı", "Adetleri işveren/şartnameye göre girin "
                     "(yangin.metraj.yedek_dolap_adet, sprinkler_anahtari_adet)", ETKI_MIKTAR,
                     bag_kaynak=tuple(x for x, v in [("kural S3", dolap), ("kural S4", anahtar)] if not v))

    # --- 5) Askı — yalnızca kural tanımlıysa, her zaman ÖN HESAP (A1)
    aralik = ((kurallar.get("metraj") or {}).get("aski_araligi_m")) or {}
    if aralik:
        toplam: dict[int, float] = {}
        for hid in ag.sira:
            h = ag.hatlar[hid]
            toplam[h.dn] = toplam.get(h.dn, 0.0) + max(h.L - abs(h.dz), 0.0)
        for dn, L in sorted(toplam.items()):
            a = aralik.get(dn) or aralik.get(str(dn))
            if not a or L <= 0:
                continue
            m.satirlar.append(Satir(f"ASKI-DN{dn}", f"Boru askısı DN{dn} (ÖN HESAP)", "Yangın — tümü", "-",
                                    f"Σ yatay boru DN{dn}", str(dn), "adet", float(math.ceil(L / float(a))), HESAPLANAN,
                                    f"Kural A1: ⌈{L:.1f} m / {a} m⌉ — yaklaşık"))
        belirsiz("Askı", "tümü", "Askı adedi ön hesaptır: DN bazında toplam yatay uzunluk / aralık. Hat uçları, "
                 "branşman başları, vana/ağırlık noktaları ve özel (sismik) destekler temsil edilmiyor",
                 "Nihai metraj için hat bazında askı yerleşimi ve destek kuralları gerekli", ETKI_MIKTAR,
                 bag_kod_on_ek="ASKI-")
    else:
        belirsiz("Askı", "tümü", "Askı aralığı kuralı tanımlı değil — askı hesaplanmadı; teklifte askı kalemi YOK",
                 "Firma/şartname askı kuralını girin (kurallar_ek.metraj.aski_araligi_m)", ETKI_KAPSAM)
    for kalem, neden in [("İşçilik", "işçilik birimi poz/firma kuralına bağlı — teklifte YOK"),
                         ("Boya / korozyon koruması", "şartnameye bağlı — teklifte YOK"),
                         ("Pompa grubu, depo, alarm/izleme", "ekipman kalemleri bu metraj kapsamı dışında — teklifte YOK")]:
        belirsiz(kalem, "tümü", neden, "Kapsama alınacaksa kural/şartname tanımlanmalı", ETKI_KAPSAM)

    # --- numaralandır ve satırlara bağla
    for i, b in enumerate(m.belirsizlikler, 1):
        b.id = f"B{i:02d}"
        for s in m.satirlar:
            if (b.bag_kaynak and s.kaynak in b.bag_kaynak) or (b.bag_kod_on_ek and s.kod.startswith(b.bag_kod_on_ek)):
                s.belirsizlik_ids.append(b.id)
                if s.kod not in b.kalem_kodlari:
                    b.kalem_kodlari.append(s.kod)

    m.model = {
        "Σ boru uzunluğu (m)": round(sum(ag.hatlar[h].L for h in ag.sira), 3),
        "Sprinkler adedi": len(ag.sprinklerler),
        "Dolap/hidrant adedi": len(ag.cikislar) - len(ag.sprinklerler),
        "Ağ hattı adedi": len(ag.sira),
    }
    return m


def ek_kalemler_ekle(m: Metraj, ek: list[dict]) -> None:
    """Ağdan türetilmeyen kalemler (proje ayarı). miktar: sayı | "sprinkler" | "kat" | "boru_m" (× carpan)."""
    spr = sum(s.miktar for s in m.satirlar if s.kod.startswith("SPR-K"))
    katlar = len({s.kat for s in m.satirlar if s.kod.startswith("SPR-K")}) or 1
    boru = sum(s.miktar for s in m.satirlar if s.kod.startswith("BORU-"))
    for e in ek or []:
        mk = e.get("miktar", 1)
        taban = {"sprinkler": spr, "kat": katlar, "boru_m": boru}.get(mk) if isinstance(mk, str) else float(mk)
        if taban is None:
            raise GirdiHatasi(f"ek_kalemler/{e.get('kod')}: miktar '{mk}' anlaşılamadı (sayı, sprinkler, kat, boru_m)")
        miktar = round(taban * float(e.get("carpan", 1)), 3)
        yontem = e.get("yontem") or (HESAPLANAN if isinstance(mk, str) else ELLE)
        not_ = e.get("not", "") + (f" [{mk} × {e.get('carpan', 1)}]" if isinstance(mk, str) else "")
        m.satirlar.append(Satir(e["kod"], e["kalem"], e.get("sistem", "Yangın — genel"), "-", "ek kalem (proje ayarı)",
                                "", e.get("birim", "adet"), miktar, _yontem(yontem), not_.strip()))
