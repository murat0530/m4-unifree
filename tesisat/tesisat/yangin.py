"""Yangın tesisatı: sprinkler + yangın dolabı + hidrant hidrolik hesabı ve
BYKHY / TS EN 12845 uygunluk kontrolü.

Yöntem
------
* Boru kaybı: Hazen-Williams (EN 12845):  p = 6,05·10⁵ · Q^1,85 / (C^1,85 · d^4,87)  [bar/m]
  Q [l/dk], d [mm] iç çap. Bağlantı parçaları eşdeğer boy ile eklenir.
* Çıkış elemanları: Q = K·√P. Sprinkler min basıncı max(pmin, (yoğunluk·alan/K)²).
* Ağaç (dallanmış) ağ, verilen kaynak basıncında TAM çözülür: her açık çıkışın
  debisi kendi gerçek basıncından hesaplanır (sönümlü sabit nokta iterasyonu).
  Ardından tüm açık çıkışların gereksinimini karşılayan EN DÜŞÜK kaynak basıncı
  ikiye bölme ile bulunur. Bu, el hesabındaki "K-eşdeğeri ile dengeleme"
  yaklaşımının yakınsamış kesin karşılığıdır.
"""
from __future__ import annotations

import math

from .ortak import (BILGI, HATA, UYARI, GirdiHatasi, ModulSonucu, Tablo,
                    agac_sirala, yuvarla)

MOD = "yangin"


def hw_bar_m(q_lpm: float, d_mm: float, c: float) -> float:
    """Hazen-Williams birim kayıp [bar/m] (EN 12845 biçimi)."""
    if q_lpm <= 0:
        return 0.0
    return 6.05e5 * q_lpm ** 1.85 / (c ** 1.85 * d_mm ** 4.87)


def hiz_ms(q_lpm: float, d_mm: float) -> float:
    return (q_lpm / 60000.0) / (math.pi * (d_mm / 1000.0) ** 2 / 4)


# ---------------------------------------------------------------- ağ modeli
class _Hat:
    __slots__ = ("id", "ust", "L", "dz", "dn", "d", "C", "leq", "vana", "cikis",
                 "K", "preq", "qmin", "alan", "tip", "ham", "z_son")


class YanginAgi:
    def __init__(self, girdi: dict, kurallar: dict):
        self.k = kurallar["yangin"]
        self.g = girdi
        sinif = girdi.get("tehlike_sinifi")
        if sinif not in self.k["tehlike_siniflari"]:
            raise GirdiHatasi(f"yangin.tehlike_sinifi '{sinif}' geçersiz. Seçenekler: "
                              f"{', '.join(self.k['tehlike_siniflari'])}")
        self.sinif_kod = sinif
        self.sinif = self.k["tehlike_siniflari"][sinif]
        self.sistem = girdi.get("sistem", "islak")
        if self.sistem not in ("islak", "kuru"):
            raise GirdiHatasi("yangin.sistem 'islak' veya 'kuru' olmalı")
        alan = self.sinif["alan"][0 if self.sistem == "islak" else 1]
        if alan is None:
            raise GirdiHatasi(
                f"{self.sinif['ad']} için {self.sistem} sistem izinli değil "
                "(BYKHY Ek-8/B: bir üst tehlike sınıfı kullanılmalı)")
        self.tasarim_alani = float(alan)
        self.yogunluk = float(self.sinif["yogunluk"])

        seri_ad = girdi.get("boru_serisi", "CELIK_EN10255_ORTA")
        if seri_ad not in self.k["boru_serileri"]:
            raise GirdiHatasi(f"yangin.boru_serisi '{seri_ad}' tanımlı değil")
        self.seri_ad = seri_ad
        seri = self.k["boru_serileri"][seri_ad]
        self.caplar = {str(a): float(d) for a, d in seri["caplar"].items()}
        malzeme = girdi.get("malzeme", seri.get("malzeme", "celik"))
        self.C = float(girdi.get("C", self.k["C_degerleri"].get(malzeme, 120)))
        self.leq_katsayi = (self.C / 120.0) ** 1.85

        kaynak = girdi.get("kaynak", {}) or {}
        self.kaynak_ad = kaynak.get("ad", "Kaynak")
        self.kaynak_kot = float(kaynak.get("kot_m", 0.0))
        spr_vars = girdi.get("sprinkler_varsayilan", {}) or {}

        ham_hatlar = girdi.get("hatlar") or []
        if not ham_hatlar:
            raise GirdiHatasi("yangin.hatlar boş")
        for h in ham_hatlar:
            if "id" not in h:
                raise GirdiHatasi(f"yangin: id'si olmayan hat: {h}")
            h["id"] = str(h["id"])
            if h.get("ust") is not None:
                h["ust"] = str(h["ust"])
        sira = agac_sirala(ham_hatlar, "ust", "yangin")

        self.hatlar: dict[str, _Hat] = {}
        self.sira: list[str] = []
        self.cocuk: dict[str | None, list[str]] = {}
        for h in sira:
            x = _Hat()
            x.ham = h
            x.id = h["id"]
            x.ust = h.get("ust")
            x.L = float(h.get("uzunluk_m", 0.0))
            x.dz = float(h.get("kot_farki_m", 0.0))
            dn = str(h.get("cap", "")).replace("DN", "").strip()
            if dn not in self.caplar:
                raise GirdiHatasi(f"yangin/{x.id}: çap '{h.get('cap')}' {seri_ad} serisinde yok. "
                                  f"Seçenekler: {', '.join(self.caplar)}")
            x.dn = int(dn)
            x.d = self.caplar[dn]
            x.C = float(h.get("C", self.C))
            x.vana = bool(h.get("vana_noktasi", False))
            x.leq = self._esdeger_boy(x, h.get("parcalar") or {}) + float(h.get("es_uzunluk_m", 0.0))
            x.cikis = None
            x.tip = None
            if h.get("sprinkler") is not None:
                s = h["sprinkler"] if isinstance(h["sprinkler"], dict) else {}
                s = {**spr_vars, **s}
                if "K" not in s or "alan_m2" not in s:
                    raise GirdiHatasi(f"yangin/{x.id}: sprinkler için K ve alan_m2 gerekli "
                                      "(veya sprinkler_varsayilan tanımlayın)")
                x.cikis, x.tip = "sprinkler", "sprinkler"
                x.K = float(s["K"])
                x.alan = float(s["alan_m2"])
                x.qmin = self.yogunluk * x.alan
                x.preq = max(float(self.sinif["pmin_bar"]), (x.qmin / x.K) ** 2)
            elif h.get("cikis"):
                tip = h["cikis"]
                if tip not in self.k["cikis_tipleri"]:
                    raise GirdiHatasi(f"yangin/{x.id}: cikis '{tip}' tanımlı değil. "
                                      f"Seçenekler: {', '.join(self.k['cikis_tipleri'])}")
                t = self.k["cikis_tipleri"][tip]
                x.cikis, x.tip = tip, tip
                x.qmin = float(h.get("debi_lpm", t["debi_lpm"]))
                x.preq = float(h.get("basinc_bar", t["basinc_bar"]))
                x.K = x.qmin / math.sqrt(x.preq)
                x.alan = 0.0
            self.hatlar[x.id] = x
            self.sira.append(x.id)
            self.cocuk.setdefault(x.ust, []).append(x.id)
        # mutlak kotlar
        for hid in self.sira:
            x = self.hatlar[hid]
            z0 = self.kaynak_kot if x.ust is None else self.hatlar[x.ust].z_son
            x.z_son = z0 + x.dz
        self.cikislar = [h for h in self.sira if self.hatlar[h].cikis]
        self.sprinklerler = [h for h in self.cikislar if self.hatlar[h].tip == "sprinkler"]
        if len(self.cocuk.get(None, [])) != 1:
            raise GirdiHatasi("yangin: ağın tek bir başlangıç hattı olmalı (ust: null olan tek hat)")

    # -------------------------------------------------------------
    def _esdeger_boy(self, x: _Hat, parcalar: dict) -> float:
        tablo = self.k["esdeger_boy_m"]
        toplam = 0.0
        for ad, adet in parcalar.items():
            if ad not in tablo:
                raise GirdiHatasi(f"yangin/{x.id}: bilinmeyen parça '{ad}'. Tanımlılar: {', '.join(tablo)}")
            satir = {int(k): float(v) for k, v in tablo[ad].items()}
            if x.dn in satir:
                deger = satir[x.dn]
            else:
                buyukler = [d for d in satir if d >= x.dn]
                deger = satir[min(buyukler)] if buyukler else satir[max(satir)]
            toplam += deger * float(adet)
        # Tablo C=120 içindir; diğer C için (C/120)^1,85 (EN 12845 / NFPA 13)
        return toplam * (x.C / 120.0) ** 1.85

    def yol(self, hid: str) -> list[str]:
        y = []
        while hid is not None:
            y.append(hid)
            hid = self.hatlar[hid].ust
        return y[::-1]

    # -------------------------------------------------------------
    def coz(self, acik: list[str], ps: float) -> dict:
        """Kaynak basıncı ps [bar] için ağın kesin çözümü."""
        acik_k = {i: self.hatlar[i] for i in acik}
        q = {i: h.K * math.sqrt(h.preq) for i, h in acik_k.items()}
        w = 0.5
        onceki = float("inf")
        for _ in range(20000):
            akis = self._akislar(q)
            p_bas, p_son = self._basinclar(akis, ps)
            artik = 0.0
            yeni = {}
            for i, h in acik_k.items():
                hedef = h.K * math.sqrt(max(p_son[i], 0.0))
                artik = max(artik, abs(hedef - q[i]))
                yeni[i] = q[i] + w * (hedef - q[i])
            q = yeni
            if artik < 1e-7:
                break
            if artik > onceki * 1.001:
                w = max(w * 0.7, 0.02)
            onceki = artik
        akis = self._akislar(q)
        p_bas, p_son = self._basinclar(akis, ps)
        return {"ps": ps, "q_cikis": q, "akis": akis, "p_bas": p_bas, "p_son": p_son}

    def _akislar(self, q: dict) -> dict:
        akis = {}
        for hid in reversed(self.sira):
            toplam = q.get(hid, 0.0)
            for c in self.cocuk.get(hid, []):
                toplam += akis[c]
            akis[hid] = toplam
        return akis

    def _basinclar(self, akis: dict, ps: float):
        st = self.k["statik_bar_m"]
        p_bas, p_son = {}, {}
        for hid in self.sira:
            h = self.hatlar[hid]
            p0 = ps if h.ust is None else p_son[h.ust]
            kayip = hw_bar_m(akis[hid], h.d, h.C) * (h.L + h.leq)
            p_bas[hid] = p0
            p_son[hid] = p0 - kayip - st * h.dz
        return p_bas, p_son

    def gerekli_kaynak_basinci(self, acik: list[str]) -> dict:
        def uygun(ps):
            c = self.coz(acik, ps)
            oran = min(c["p_son"][i] / self.hatlar[i].preq for i in acik)
            return oran >= 1.0, c

        lo, hi = 0.0, 2.0
        ok, cz = uygun(hi)
        while not ok:
            hi *= 2
            if hi > 200:
                raise GirdiHatasi("yangin: 200 bar kaynak basıncında bile çözüm yok — çaplar çok küçük")
            ok, cz = uygun(hi)
        for _ in range(60):
            orta = (lo + hi) / 2
            ok, c = uygun(orta)
            if ok:
                hi, cz = orta, c
            else:
                lo = orta
            if hi - lo < 1e-5:
                break
        return cz


# ---------------------------------------------------------------- ana hesap
def hesapla(proje: dict, kurallar: dict) -> ModulSonucu:
    g = proje["yangin"]
    s = ModulSonucu(MOD, "Yangın Tesisatı — Sprinkler / Yangın Dolabı / Hidrant")
    ag = YanginAgi(g, kurallar)
    k = ag.k
    bina = proje.get("bina", {}) or {}

    s.tablolar.append(Tablo("Tasarım kriterleri", ["Parametre", "Değer", "Kaynak"], [
        ["Tehlike sınıfı", ag.sinif["ad"], "BYKHY md. 19, Ek-1"],
        ["Sistem tipi", "Islak / ön etkili" if ag.sistem == "islak" else "Kuru / değişken", ""],
        ["Tasarım yoğunluğu", f"{ag.yogunluk} mm/dk", "BYKHY Ek-8/B, TS EN 12845 Tablo 3"],
        ["Operasyon (tasarım) alanı", f"{ag.tasarim_alani:g} m²", "BYKHY Ek-8/B"],
        ["Min. sprinkler basıncı", f"{ag.sinif['pmin_bar']} bar", "TS EN 12845 12.4"],
        ["Sprinkler başına max alan", f"{ag.sinif['max_alan_m2']} m²", "BYKHY md. 96/5, TS EN 12845"],
        ["Su temin süresi", f"{ag.sinif['sure_dk']} dk", "BYKHY md. 92/3"],
        ["Boru serisi / C", f"{ag.seri_ad} / C={ag.C:g}", "TS EN 12845 (Hazen-Williams)"],
    ]))

    _zorunluluk_kontrol(s, ag, bina, k)
    _eleman_kontrol(s, ag, k)

    senaryolar = g.get("senaryolar") or []
    if not senaryolar:
        s.bulgu(HATA, "senaryolar", "En az bir hesap senaryosu (açık çıkış listesi) tanımlanmalı")
        return s

    ozet = Tablo("Senaryo özeti", ["Senaryo", "Açık sprinkler", "Açık dolap/hidrant",
                                   "Σ kapsama m²", "Q toplam l/dk", "Gerekli kaynak basıncı bar",
                                   "Kritik çıkış"])
    sonuclar = []
    for sn in senaryolar:
        ad = sn.get("ad", "Senaryo")
        acik = [str(x) for x in (sn.get("acik") or [])]
        if not acik:
            raise GirdiHatasi(f"yangin/senaryo '{ad}': açık çıkış yok")
        for i in acik:
            if i not in ag.hatlar or not ag.hatlar[i].cikis:
                raise GirdiHatasi(f"yangin/senaryo '{ad}': '{i}' bir sprinkler/dolap/hidrant hattı değil")
        spr = [i for i in acik if ag.hatlar[i].tip == "sprinkler"]
        diger = [i for i in acik if ag.hatlar[i].tip != "sprinkler"]
        cz = ag.gerekli_kaynak_basinci(acik)
        kritik = min(acik, key=lambda i: cz["p_son"][i] / ag.hatlar[i].preq)
        kapsama = sum(ag.hatlar[i].alan for i in spr)
        qtop = cz["akis"][ag.sira[0]]
        q_spr = sum(cz["q_cikis"][i] for i in spr)
        ozet.satirlar.append([ad, len(spr), len(diger), yuvarla(kapsama, 1), yuvarla(qtop, 1),
                              yuvarla(cz["ps"], 3), kritik])
        sonuclar.append({"ad": ad, "acik": acik, "spr": spr, "diger": diger, "cz": cz,
                         "qtop": qtop, "q_spr": q_spr, "kapsama": kapsama})
        if spr and kapsama + 1e-6 < ag.tasarim_alani:
            eksik = math.ceil((ag.tasarim_alani - kapsama) / max(ag.hatlar[spr[0]].alan, 1e-9))
            s.bulgu(HATA, ad, f"Açık sprinklerlerin toplam kapsama alanı {kapsama:.1f} m² < tasarım alanı "
                    f"{ag.tasarim_alani:g} m² — yaklaşık {eksik} sprinkler daha senaryoya eklenmeli",
                    "BYKHY Ek-8/B, TS EN 12845 Tablo 3")
        _senaryo_tablolari(s, ag, ad, acik, cz)
        _hiz_kontrol(s, ag, ad, cz, k)
        _dolap_basinc_kontrol(s, ag, ad, diger, cz)
    s.tablolar.insert(1, ozet)

    if not any(r["spr"] for r in sonuclar) and ag.sprinklerler:
        s.bulgu(HATA, "senaryolar", "Sprinkler içeren hiçbir senaryo yok — en elverişsiz tasarım alanı hesaplanmalı")

    belirleyici = max(sonuclar, key=lambda r: r["cz"]["ps"])
    _pompa_depo(s, ag, g, sonuclar, belirleyici, k)

    s.ozet = {
        "Tehlike sınıfı": ag.sinif["ad"],
        "Belirleyici senaryo": belirleyici["ad"],
        "Pompa çıkışında gerekli basınç [bar]": round(belirleyici["cz"]["ps"], 3),
        "Belirleyici senaryo debisi [l/dk]": round(belirleyici["qtop"], 1),
        "En büyük senaryo debisi [l/dk]": round(max(r["qtop"] for r in sonuclar), 1),
    }
    return s


# ---------------------------------------------------------------- yardımcılar
def _senaryo_tablolari(s, ag: YanginAgi, ad, acik, cz):
    t = Tablo(f"Hidrolik hesap — {ad}",
              ["Hat", "Üst", "DN", "di mm", "L m", "Leq m", "Q l/dk", "v m/s", "J bar/m",
               "Sürtünme bar", "Statik bar", "P baş bar", "P son bar"])
    st = ag.k["statik_bar_m"]
    for hid in ag.sira:
        h = ag.hatlar[hid]
        q = cz["akis"][hid]
        if q <= 1e-9:
            continue
        j = hw_bar_m(q, h.d, h.C)
        t.satirlar.append([hid, h.ust or ag.kaynak_ad, h.dn, h.d, yuvarla(h.L), yuvarla(h.leq),
                           yuvarla(q, 1), yuvarla(hiz_ms(q, h.d)), yuvarla(j, 5),
                           yuvarla(j * (h.L + h.leq), 4), yuvarla(st * h.dz, 4),
                           yuvarla(cz["p_bas"][hid], 3), yuvarla(cz["p_son"][hid], 3)])
    s.tablolar.append(t)
    c = Tablo(f"Çıkışlar — {ad}", ["Çıkış", "Tip", "K", "Kapsama m²", "Gerekli Q l/dk",
                                   "Gerekli P bar", "P bar", "Q l/dk", "Yoğunluk mm/dk", "Durum"])
    for i in acik:
        h = ag.hatlar[i]
        p = cz["p_son"][i]
        q = cz["q_cikis"][i]
        yog = q / h.alan if h.alan else None
        durum = "OK" if p >= h.preq - 1e-4 else "YETERSİZ"
        c.satirlar.append([i, h.tip, yuvarla(h.K, 1), yuvarla(h.alan, 1) if h.alan else "-",
                           yuvarla(h.qmin, 1), yuvarla(h.preq, 3), yuvarla(p, 3), yuvarla(q, 1),
                           yuvarla(yog, 2) if yog else "-", durum])
    s.tablolar.append(c)


def _hiz_kontrol(s, ag: YanginAgi, ad, cz, k):
    for hid in ag.sira:
        h = ag.hatlar[hid]
        v = hiz_ms(cz["akis"][hid], h.d)
        sinir = k["hiz_max_vana_ms"] if h.vana else k["hiz_max_ms"]
        if v > sinir + 1e-9:
            s.bulgu(HATA, hid, f"[{ad}] Hız {v:.2f} m/s > {sinir:g} m/s "
                    f"({'vana/akış anahtarı noktası' if h.vana else 'genel'}) — çap büyütülmeli",
                    "TS EN 12845 (hız sınırları)")


def _dolap_basinc_kontrol(s, ag: YanginAgi, ad, diger, cz):
    for i in diger:
        h = ag.hatlar[i]
        t = ag.k["cikis_tipleri"][h.tip]
        pmax = t.get("max_basinc_bar")
        if pmax and cz["p_son"][i] > pmax:
            s.bulgu(HATA, i, f"[{ad}] Lüle girişi basıncı {cz['p_son'][i]:.2f} bar > {pmax:g} bar — "
                    "basınç düşürücü gerekli", "BYKHY md. 94/1-b-5")


def _eleman_kontrol(s, ag: YanginAgi, k):
    sinif = ag.sinif
    tb = Tablo("Sprinkler yerleşim kontrolü", ["Sprinkler", "K", "Kapsama m²", "Max m²",
                                                "Min Q l/dk", "Min P bar", "Durum"])
    for i in ag.sprinklerler:
        h = ag.hatlar[i]
        durum = []
        if h.alan > sinif["max_alan_m2"] + 1e-9:
            durum.append("alan aşımı")
            s.bulgu(HATA, i, f"Sprinkler kapsama alanı {h.alan:g} m² > {sinif['max_alan_m2']} m²",
                    "BYKHY md. 96/5, TS EN 12845")
        if int(round(h.K)) not in [int(x) for x in sinif["K"]]:
            durum.append("K uygun değil")
            s.bulgu(UYARI, i, f"K={h.K:g} bu tehlike sınıfı için öngörülen {sinif['K']} değil",
                    "TS EN 12845 Tablo 37")
        tb.satirlar.append([i, h.K, h.alan, sinif["max_alan_m2"], yuvarla(h.qmin, 1),
                            yuvarla(h.preq, 3), ", ".join(durum) or "OK"])
    if ag.sprinklerler:
        s.tablolar.append(tb)

    # Minimum çap (EN 12845 Tablo 36)
    for hid in ag.sira:
        h = ag.hatlar[hid]
        tek_spr = h.tip == "sprinkler" and not ag.cocuk.get(hid) and h.K <= 80
        sinir = k["min_cap_K80_alti_mm"] if tek_spr else k["min_cap_diger_mm"]
        if h.dn < sinir:
            s.bulgu(HATA, hid, f"DN{h.dn} < minimum DN{sinir}", "TS EN 12845 Tablo 36")

    # Hidrant besleme hattı ≥ DN100
    for i in ag.cikislar:
        if ag.hatlar[i].tip == "hidrant":
            for hid in ag.yol(i):
                if ag.hatlar[hid].dn < k["hidrant_min_DN"]:
                    s.bulgu(HATA, hid, f"Hidrant besleme hattı DN{ag.hatlar[hid].dn} < DN{k['hidrant_min_DN']} "
                            "(ring yoksa)", "BYKHY md. 95/5")

    # Dolap aralıkları
    dolaplar = [ag.hatlar[i] for i in ag.cikislar if ag.hatlar[i].tip.startswith("dolap")]
    katlar: dict = {}
    for d in dolaplar:
        kon = d.ham.get("konum")
        if kon:
            katlar.setdefault(str(d.ham.get("kat", "")), []).append((d, kon))
    for kat, liste in katlar.items():
        if len(liste) < 2:
            continue
        for d, (x, y) in liste:
            en_yakin = min(math.dist((x, y), (x2, y2)) for d2, (x2, y2) in liste if d2 is not d)
            sinir = k["dolap_araligi_sprinklerli_m"] if d.ham.get("sprinkler_hattindan") else k["dolap_araligi_max_m"]
            if en_yakin > sinir:
                s.bulgu(HATA, d.id, f"Kat {kat}: en yakın dolaba uzaklık {en_yakin:.1f} m > {sinir} m",
                        "BYKHY md. 94/1-b-2")

    if ag.sprinklerler:
        yedek = ag.g.get("yedek_sprinkler")
        if yedek is None or yedek < k["yedek_sprinkler_min"]:
            s.bulgu(UYARI, "yedek sprinkler", f"En az {k['yedek_sprinkler_min']} adet yedek sprinkler ve "
                    "değiştirme anahtarı bulundurulmalı (girdi: "
                    f"{yedek if yedek is not None else 'belirtilmedi'})", "BYKHY md. 96/8")


def _zorunluluk_kontrol(s, ag: YanginAgi, bina: dict, k):
    z = k["zorunluluk"]
    neden = []
    kullanim = str(bina.get("kullanim", "")).lower()
    yy = bina.get("yapi_yuksekligi_m")
    if yy is not None:
        if kullanim == "konut" and yy > z["yapi_yuksekligi_konut_m"]:
            neden.append(f"konut, yapı yüksekliği {yy} m > {z['yapi_yuksekligi_konut_m']} m (md. 96/2-b)")
        if kullanim and kullanim != "konut" and yy > z["yapi_yuksekligi_konut_disi_m"]:
            neden.append(f"konut dışı, yapı yüksekliği {yy} m > {z['yapi_yuksekligi_konut_disi_m']} m (md. 96/2-a)")
    if bina.get("kapali_otopark_m2", 0) > z["kapali_otopark_m2"]:
        neden.append(f"kapalı otopark {bina['kapali_otopark_m2']} m² > {z['kapali_otopark_m2']} m² (md. 96/2-c)")
    if bina.get("asansorlu_otopark_arac", 0) > z["asansorlu_otopark_arac"]:
        neden.append("asansörle 10'dan fazla araç alınan otopark (md. 96/2-c)")
    if bina.get("konaklama_oda", 0) > z["konaklama_oda"] or bina.get("konaklama_yatak", 0) > z["konaklama_yatak"]:
        neden.append("konaklama: oda > 100 veya yatak > 200 (md. 96/2-ç)")
    if kullanim in ("otel", "yurt", "konaklama", "hastane", "yatakli_tesis") and yy and yy > z["konaklama_yapi_yuksekligi_m"]:
        neden.append(f"yataklı tesis, yapı yüksekliği > {z['konaklama_yapi_yuksekligi_m']} m (md. 96/2-ç)")
    if bina.get("magaza_m2", 0) > z["magaza_m2"]:
        neden.append(f"katlı mağaza/AVM > {z['magaza_m2']} m² (md. 96/2-d)")
    if bina.get("parlayici_m2", 0) > z["parlayici_m2"]:
        neden.append(f"parlayıcı/kolay alevlenici madde alanı > {z['parlayici_m2']} m² (md. 96/2-e)")
    if neden:
        if ag.sprinklerler:
            s.bulgu(BILGI, "zorunluluk", "Sprinkler zorunlu: " + "; ".join(neden), "BYKHY md. 96/2")
        else:
            s.bulgu(HATA, "zorunluluk", "Sprinkler zorunlu ancak projede sprinkler yok: " + "; ".join(neden),
                    "BYKHY md. 96/2")
    dz = k["dolap_zorunluluk"]
    dneden = []
    if bina.get("yuksek_bina"):
        dneden.append("yüksek bina")
    if kullanim in ("imalathane", "atolye", "depo", "konaklama", "otel", "saglik", "hastane",
                    "toplanma", "egitim", "okul") and bina.get("kapali_alan_m2", 0) > dz["kullanim_m2"]:
        dneden.append(f"{kullanim}, kapalı alan > {dz['kullanim_m2']} m²")
    if bina.get("kapali_otopark_m2", 0) > dz["otopark_m2"]:
        dneden.append(f"kapalı otopark > {dz['otopark_m2']} m²")
    if bina.get("kazan_kW", 0) > dz["kazan_kW"]:
        dneden.append(f"kazan dairesi > {dz['kazan_kW']} kW")
    var_dolap = any(ag.hatlar[i].tip.startswith("dolap") for i in ag.cikislar)
    if dneden and not var_dolap:
        s.bulgu(HATA, "zorunluluk", "Yangın dolabı zorunlu ancak projede dolap yok: " + "; ".join(dneden),
                "BYKHY md. 94/1-b-1")
    elif dneden:
        s.bulgu(BILGI, "zorunluluk", "Yangın dolabı zorunlu: " + "; ".join(dneden), "BYKHY md. 94/1-b-1")


def _pompa_depo(s, ag: YanginAgi, g, sonuclar, bel, k):
    pg = g.get("pompa", {}) or {}
    emme = float(pg.get("emme_basinci_bar", 0.0))
    satirlar = []
    q_tasarim = max(r["qtop"] for r in sonuclar)
    h_tasarim = max(r["cz"]["ps"] for r in sonuclar) - emme
    # Önerilen anma noktası: zarf (en büyük Q ve en büyük basınç), yukarı yuvarlanmış
    q_anma_oneri = math.ceil(q_tasarim / 50.0) * 50
    h_anma_oneri = math.ceil(h_tasarim * 10) / 10
    satirlar += [
        ["Belirleyici senaryo (en yüksek basınç)", bel["ad"]],
        ["Tasarım debisi (tüm senaryoların en büyüğü)", f"{q_tasarim:.1f} l/dk = {q_tasarim * 0.06:.2f} m³/h"],
        ["Pompa çıkışında gerekli basınç (belirleyici)", f"{bel['cz']['ps']:.2f} bar"],
        ["Emme tarafı basıncı (girdi)", f"{emme:.2f} bar"],
        ["Gerekli pompa basınç artışı", f"{h_tasarim:.2f} bar ≈ {h_tasarim * 10.197:.1f} mSS"],
        ["Önerilen anma noktası", f"{q_anma_oneri} l/dk @ {h_anma_oneri:.1f} bar"],
    ]
    for r in sonuclar:
        satirlar.append([f"  Senaryo talebi: {r['ad']}", f"{r['qtop']:.1f} l/dk @ {r['cz']['ps'] - emme:.2f} bar"])

    anma_q = pg.get("anma_debi_lpm")
    anma_p = pg.get("anma_basinc_bar")
    if anma_q and anma_p:
        oran = k["pompa"]
        for r in sonuclar:
            gerek = r["cz"]["ps"] - emme
            if r["qtop"] <= anma_q * 1.0 + 1e-9:
                if anma_p + 1e-9 < gerek:
                    s.bulgu(HATA, "pompa", f"[{r['ad']}] Anma basıncı {anma_p} bar < gerekli {gerek:.2f} bar")
            elif r["qtop"] <= anma_q * 1.30 + 1e-9:
                p150 = pg.get("debi_150_basinc_bar")
                if p150 is None:
                    s.bulgu(UYARI, "pompa", f"[{r['ad']}] Talep anma debisinin üzerinde "
                            f"({r['qtop']:.0f} > {anma_q} l/dk); pompa eğrisinde bu debideki basınç doğrulanmalı",
                            "BYKHY md. 93/1 (%130'a kadar kullanım)")
            else:
                s.bulgu(HATA, "pompa", f"[{r['ad']}] Talep {r['qtop']:.0f} l/dk > anma debisinin %130'u "
                        f"({anma_q * 1.3:.0f} l/dk)", "BYKHY md. 93/1")
        pk = pg.get("kapali_vana_basinc_bar")
        if pk is not None and pk > oran["kapali_vana_max_oran"] * anma_p + 1e-9:
            s.bulgu(HATA, "pompa", f"Kapalı vana basıncı {pk} bar > %140 anma ({1.4 * anma_p:.2f} bar)",
                    "BYKHY md. 93/1")
        p150 = pg.get("debi_150_basinc_bar")
        if p150 is not None and p150 + 1e-9 < oran["debi_150_min_basinc_oran"] * anma_p:
            s.bulgu(HATA, "pompa", f"%150 debideki basınç {p150} bar < %65 anma ({0.65 * anma_p:.2f} bar)",
                    "BYKHY md. 93/1")
        satirlar.append(["Seçilen pompa (girdi)", f"{anma_q} l/dk @ {anma_p} bar"])
        # dolap statik basıncı (kapalı vana) kontrolü
        if pk is not None:
            for i in ag.cikislar:
                h = ag.hatlar[i]
                if h.tip.startswith("dolap"):
                    p_stat = emme + pk - ag.k["statik_bar_m"] * (h.z_son - ag.kaynak_kot)
                    pmax = ag.k["cikis_tipleri"][h.tip]["max_basinc_bar"]
                    if p_stat > pmax:
                        s.bulgu(UYARI, i, f"Kapalı vana durumunda dolap statik basıncı {p_stat:.2f} bar > "
                                f"{pmax:g} bar — basınç düşürücü gerekli", "BYKHY md. 94/1-b-5")
    else:
        s.bulgu(BILGI, "pompa", "Pompa anma değerleri girilmedi — önerilen anma noktası raporda verildi")
    if k["pompa"]["yedek_zorunlu"] and int(pg.get("adet_yedek", 0)) < 1:
        s.bulgu(HATA, "pompa", "Yedek pompa tanımlı değil (aynı kapasitede yedek zorunlu)", "BYKHY md. 93/2")

    # Depo
    grup = ag.sinif["grup"]
    if grup == "orta":
        grup = "orta12" if ag.sinif_kod in ("OT1", "OT2") else "orta34"
    ek = k["ek_su_ihtiyaci"][grup]
    sure = float(ag.sinif["sure_dk"])
    # md. 92/5: sprinkler debisi + Ek-8/C dolap/hidrant debisi. Sprinkler debisi,
    # yalnız sprinkler açık senaryolardan alınır (dolap eşzamanlı senaryolarda
    # sprinklerler fazla basınçla çalışır; o senaryolar pompa seçimine girer).
    spr_senaryo = [r for r in sonuclar if r["spr"] and not r["diger"]] or [r for r in sonuclar if r["spr"]]
    q_spr = max((r["q_spr"] for r in spr_senaryo), default=0.0)
    var_dolap = any(ag.hatlar[i].tip.startswith("dolap") for i in ag.cikislar)
    var_hidrant = bool(g.get("hidrant_var")) or any(ag.hatlar[i].tip == "hidrant" for i in ag.cikislar)
    if ag.sprinklerler:
        q_dolap = ek["dolap"] if var_dolap else 0
        q_hid = ek["hidrant"] if var_hidrant else 0
        q_depo = q_spr + q_dolap + q_hid
        aciklama = f"({q_spr:.0f} sprinkler + {q_dolap} dolap + {q_hid} hidrant) l/dk × {sure:g} dk"
        kaynak = "BYKHY md. 92/4-5, Ek-8/C"
    else:
        q_depo = max(r["qtop"] for r in sonuclar)
        aciklama = f"{q_depo:.0f} l/dk (dolap/hidrant senaryosu) × {sure:g} dk"
        kaynak = "BYKHY md. 92/6"
    v_hid = q_depo * sure / 1000.0
    satirlar += [["Depo hesap debisi", aciklama], ["Hidrolik hesaba göre depo hacmi", f"{v_hid:.1f} m³ ({kaynak})"]]
    # Ek-8/A ön hesap karşılaştırması
    if ag.sprinklerler:
        kotlar = [ag.hatlar[i].z_son for i in ag.sprinklerler]
        h_fark = max(kotlar) - min(kotlar)
        anahtar = f"{ag.sinif_kod}_{ag.sistem}"
        tablo = k["min_depo_m3"].get(anahtar)
        if tablo and h_fark <= 45:
            idx = 0 if h_fark <= 15 else (1 if h_fark <= 30 else 2)
            satirlar.append(["Ek-8/A ön hesap en az hacmi (karşılaştırma)",
                             f"{tablo[idx]} m³ (h = {h_fark:.1f} m)"])
            if v_hid < tablo[idx]:
                s.bulgu(BILGI, "depo", f"Hidrolik hesap hacmi {v_hid:.1f} m³, Ek-8/A ön hesap tablosu "
                        f"{tablo[idx]} m³. Hidrolik hesap yapıldığından hidrolik değer esas alınır; "
                        "idare onayı için iki değer de raporda verilmiştir.", "BYKHY md. 92/4")
    depo = g.get("depo", {}) or {}
    if depo.get("hacim_m3") is not None:
        satirlar.append(["Projedeki depo hacmi (girdi)", f"{depo['hacim_m3']} m³"])
        if depo["hacim_m3"] + 1e-9 < v_hid:
            s.bulgu(HATA, "depo", f"Depo hacmi {depo['hacim_m3']} m³ < gerekli {v_hid:.1f} m³", kaynak)
    s.tablolar.append(Tablo("Pompa ve depo", ["Kalem", "Değer"], satirlar))
