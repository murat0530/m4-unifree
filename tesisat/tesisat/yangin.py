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

from . import kapsama
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
                 "K", "preq", "qmin", "alan", "alan_kaynak", "tip", "ham", "z_son", "sinif_kod", "mahal")


class YanginAgi:
    def __init__(self, girdi: dict, kurallar: dict):
        self.k = kurallar["yangin"]
        self.g = girdi
        self.siniflar = self.k["tehlike_siniflari"]
        self.sinif_sirasi = list(self.siniflar)
        proje_sinif = girdi.get("tehlike_sinifi")
        if proje_sinif is not None and proje_sinif not in self.siniflar:
            raise GirdiHatasi(f"yangin.tehlike_sinifi '{proje_sinif}' geçersiz. Seçenekler: "
                              f"{', '.join(self.siniflar)}")
        self.proje_sinif = proje_sinif
        self.sistem = girdi.get("sistem", "islak")
        if self.sistem not in ("islak", "kuru"):
            raise GirdiHatasi("yangin.sistem 'islak' veya 'kuru' olmalı")
        self.mahal_bilgi = self._mahal_siniflari(girdi.get("mahaller") or [])
        adaylar = [v["sinif"] for v in self.mahal_bilgi.values() if v["sinif"]]
        if proje_sinif:
            adaylar.append(proje_sinif)
        if not adaylar:
            raise GirdiHatasi("yangin: 'tehlike_sinifi' veya mahallerde 'tip'/'tehlike_sinifi' verilmeli")
        for kod in set(adaylar):
            self.tasarim_alani_of(kod)   # ıslak/kuru uygunluğu
        # BYKHY md. 19/1: su ve pompa kapasitesi binanın EN YÜKSEK tehlike sınıfına göre
        self.sinif_kod = max(adaylar, key=self.sinif_sirasi.index)
        self.sinif = self.siniflar[self.sinif_kod]
        self.tasarim_alani = self.tasarim_alani_of(self.sinif_kod)
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
        self.geo: dict = {}
        self.geo_alan: dict = {}
        self.geo_notlar: list = []
        self._geometri(girdi.get("mahaller") or [], ham_hatlar)

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
                x.alan_kaynak = "girdi"
                if x.id in self.geo_alan:
                    plan = self.geo_alan[x.id]
                    girilen = h["sprinkler"].get("alan_m2") if isinstance(h["sprinkler"], dict) else None
                    oran = self.k["yerlesim"]["alan_farki_uyari_orani"]
                    if girilen is not None and abs(girilen - plan) > oran * plan:
                        self.geo_notlar.append((UYARI, x.id, f"Girilen alan {girilen:g} m² ≠ plandan hesaplanan "
                                                f"{plan:.2f} m² — plan alanı kullanıldı", ""))
                    s["alan_m2"] = plan
                    x.alan_kaynak = "plan"
                if "K" not in s or "alan_m2" not in s:
                    raise GirdiHatasi(f"yangin/{x.id}: sprinkler için K ve alan_m2 gerekli "
                                      "(veya sprinkler_varsayilan tanımlayın)")
                x.cikis, x.tip = "sprinkler", "sprinkler"
                x.mahal = str(h["mahal"]) if h.get("mahal") is not None else None
                x.sinif_kod = self.hat_sinifi(x.mahal)
                sc = self.siniflar[x.sinif_kod]
                x.K = float(s["K"])
                x.alan = float(s["alan_m2"])
                x.qmin = float(sc["yogunluk"]) * x.alan
                x.preq = max(float(sc["pmin_bar"]), (x.qmin / x.K) ** 2)
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
    def tasarim_alani_of(self, kod: str) -> float:
        a = self.siniflar[kod]["alan"][0 if self.sistem == "islak" else 1]
        if a is None:
            raise GirdiHatasi(f"{self.siniflar[kod]['ad']} için {self.sistem} sistem izinli değil "
                              "(BYKHY Ek-8/B: bir üst tehlike sınıfı kullanılmalı)")
        return float(a)

    def hat_sinifi(self, mahal: str | None) -> str:
        if mahal is not None and mahal in self.mahal_bilgi and self.mahal_bilgi[mahal]["sinif"]:
            return self.mahal_bilgi[mahal]["sinif"]
        return self.proje_sinif or self.sinif_kod

    def en_yuksek(self, kodlar) -> str:
        return max(kodlar, key=self.sinif_sirasi.index)

    def _mahal_siniflari(self, mahaller: list) -> dict:
        """Mahal 'tip' → kütüphaneden sınıf; 'tehlike_sinifi' açıkça verilirse o geçerli."""
        tipler = self.k.get("mahal_tipleri", {})
        cikti = {}
        for m in mahaller:
            mid = str(m.get("id", ""))
            tip = m.get("tip")
            kayit = {}
            if tip is not None:
                if tip not in tipler:
                    raise GirdiHatasi(f"yangin.mahaller/{mid}: tip '{tip}' tanımlı değil. "
                                      f"Seçenekler: {', '.join(tipler)}")
                kayit = tipler[tip]
            acik_sinif = m.get("tehlike_sinifi")
            if acik_sinif is not None and acik_sinif not in self.siniflar:
                raise GirdiHatasi(f"yangin.mahaller/{mid}: tehlike_sinifi '{acik_sinif}' geçersiz")
            muaf = bool(m.get("muaf", kayit.get("muaf", False)))
            sinif = acik_sinif or kayit.get("sinif")
            if acik_sinif:
                kaynak = "Proje girdisi (mühendis kararı)" + (f" — kütüphane önerisi: {kayit['sinif']}"
                                                              if kayit.get("sinif") and kayit["sinif"] != acik_sinif else "")
            elif sinif:
                kaynak = kayit.get("kaynak", "")
            elif muaf:
                kaynak = kayit.get("kaynak", "Muafiyet beyanı")
            else:
                sinif, kaynak = self.proje_sinif, "Proje varsayılanı"
                if sinif is None:
                    raise GirdiHatasi(f"yangin.mahaller/{mid}: tehlike sınıfı belirlenemedi ('tip' veya "
                                      "'tehlike_sinifi' verin)")
            cikti[mid] = {"sinif": None if (muaf and not acik_sinif) else sinif, "kaynak": kaynak, "muaf": muaf,
                          "tip": tip, "ad": m.get("ad") or kayit.get("ad") or mid, "not": kayit.get("not"),
                          "muaf_nedeni": m.get("muaf_nedeni") or (kayit.get("kaynak", "") if muaf else "")}
        return cikti

    def _geometri(self, mahaller: list, ham: list):
        """Mahal çokgenleri + sprinkler konumlarından kapsama alanları (kapsama.py)."""
        if not mahaller:
            return
        y = self.k["yerlesim"]
        mh = {}
        for m in mahaller:
            mid = str(m.get("id", ""))
            pol = m.get("poligon") or []
            if not mid or len(pol) < 3:
                raise GirdiHatasi(f"yangin.mahaller: id ve en az 3 köşeli poligon gerekli ({m})")
            mh[mid] = {**m, "poligon": [tuple(map(float, p[:2])) for p in pol]}
        gruplar: dict = {}
        for h in ham:
            if h.get("sprinkler") is None:
                continue
            if h.get("mahal") is None:
                self.geo_notlar.append((UYARI, h["id"], "Sprinklerin mahal/konum bilgisi yok — geometrik "
                                        "kapsama kontrolü yapılamadı, girilen alan kullanıldı", ""))
                continue
            mid = str(h["mahal"])
            if mid not in mh:
                raise GirdiHatasi(f"yangin/{h['id']}: mahal '{mid}' tanımlı değil")
            if not h.get("konum"):
                raise GirdiHatasi(f"yangin/{h['id']}: mahal verilmiş ama konum [x, y] yok")
            gruplar.setdefault(mid, {})[h["id"]] = tuple(map(float, h["konum"][:2]))
        ref = "TS EN 12845 md. 12.2–12.4"
        for mid, m in mh.items():
            sc = self.siniflar[self.hat_sinifi(mid)]
            smax = float(sc["max_aralik_m"])
            if m.get("acik_kiris"):
                dmax = y["duvar_max_acik_kiris_m"]
            elif m.get("yerlesim") == "sasirtmali":
                dmax = y["duvar_max_sasirtmali_m"]
            else:
                dmax = min(y["duvar_max_standart_m"], smax / 2)
            spr = gruplar.get(mid)
            if not spr:
                mb = self.mahal_bilgi.get(mid, {})
                if mb.get("muaf"):
                    self.geo_notlar.append((BILGI, mid, f"Mahal sprinklerden muaf: {mb.get('muaf_nedeni', '')} "
                                            "— muafiyet mühendis beyanı ile kesinleşir", "BYKHY md. 96/3"))
                else:
                    self.geo_notlar.append((HATA, mid, "Mahalde sprinkler yok (muaf ise 'muaf: true' ve "
                                            "gerekçe girin)", "BYKHY md. 96/3"))
                continue
            a = kapsama.mahal_analizi(m["poligon"], spr, smax, dmax, y["min_aralik_m"],
                                      float(sc["max_alan_m2"]))
            a.update({"smax": smax, "dmax": dmax, "poligon": m["poligon"], "alan_max": float(sc["max_alan_m2"]),
                      "ad": self.mahal_bilgi.get(mid, {}).get("ad", mid), "sinif": self.hat_sinifi(mid)})
            self.geo[mid] = a
            self.geo_alan.update(a["alanlar"])
            for tur, nesne, mesaj in a["ihlaller"]:
                if tur == "alan":
                    continue  # sprinkler yerleşim kontrolünde raporlanır
                seviye = UYARI if tur == "yakin" else HATA
                ek = {"yakin": " (md. 12.3 istisnaları: birbirini ıslatmayacak şekilde ayrılmışsa)",
                      "aralik": f" (Tablo 19)", "duvar": "", "korunmayan": "", "disarida": ""}[tur]
                self.geo_notlar.append((seviye, nesne, f"[{a['ad']}] {mesaj}{ek}", ref))
            if abs(a["hucre_toplami"] - a["mahal_alani"]) > 0.01 * a["mahal_alani"]:
                self.geo_notlar.append((HATA, mid, f"Hücre toplamı {a['hucre_toplami']:.1f} m² ≠ mahal "
                                        f"{a['mahal_alani']:.1f} m² (sprinkler mahal dışında olabilir)", ref))

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

    def yol_uzunlugu(self, hid: str) -> float:
        return sum(self.hatlar[h].L + self.hatlar[h].leq for h in self.yol(hid))

    def otomatik_senaryolar(self, uzun_eksen: str = "x", oran: float = 1.5) -> list[dict]:
        """En elverişsiz tasarım alanı adayları (TS EN 12845: dikdörtgene yakın, uzun kenar
        branşman yönünde). Her sınıf için en uzun boru yolundaki sprinklerden ve en yüksek
        kottaki sprinklerden başlayarak, elips ölçütüyle en yakın sprinklerler eklenir;
        kapsama, eklenen sprinklerlerin en yüksek sınıfının tasarım alanına ulaşınca durulur."""
        konumlu = [i for i in self.sprinklerler if self.hatlar[i].ham.get("konum")]
        if not konumlu or len(konumlu) != len(self.sprinklerler):
            raise GirdiHatasi("yangin: otomatik senaryo için tüm sprinklerlerde konum [x, y] olmalı")
        kon = {i: tuple(map(float, self.hatlar[i].ham["konum"][:2])) for i in konumlu}
        tohumlar = []
        for kod in sorted({self.hatlar[i].sinif_kod for i in konumlu}, key=self.sinif_sirasi.index, reverse=True):
            grup = [i for i in konumlu if self.hatlar[i].sinif_kod == kod]
            tohumlar.append((f"{kod} en uzak", max(grup, key=self.yol_uzunlugu)))
        tohumlar.append(("en yüksek kot", max(konumlu, key=lambda i: (self.hatlar[i].z_son, self.yol_uzunlugu(i)))))
        sonuc, gorulen = [], set()
        mahal_of = {i: m for m, a in self.geo.items() for i in a["idler"]}

        def sec(t, r):
            rx, ry = (r, 1.0) if uzun_eksen == "x" else (1.0, r)
            z = self.hatlar[t].z_son
            ayni_kat = [i for i in konumlu if abs(self.hatlar[i].z_son - z) < 1.0]
            ayni_kat.sort(key=lambda i: math.hypot((kon[i][0] - kon[t][0]) / rx, (kon[i][1] - kon[t][1]) / ry))
            secim, toplam, hedef = [], 0.0, 0.0
            for i in ayni_kat:
                secim.append(i)
                toplam += self.hatlar[i].alan
                hedef = self.tasarim_alani_of(self.en_yuksek([self.hatlar[j].sinif_kod for j in secim]))
                if toplam + 1e-9 >= hedef:
                    break
            hucre = [self.geo[mahal_of[i]]["hucreler"][i] for i in secim if i in mahal_of]
            uzun = max(kapsama.sinir_kutusu(hucre)) if hucre else 0.0
            return secim, uzun >= 1.2 * math.sqrt(hedef) - 1e-6

        for etiket, t in tohumlar:
            # biçim koşulu (uzun kenar ≥ 1,2·√A) sağlanana kadar alanı branşman yönünde uzat
            for r in (oran, 2.0, 3.0, 4.0, 6.0):
                secim, uygun = sec(t, r)
                if uygun:
                    break
            anahtar = frozenset(secim)
            if anahtar in gorulen:
                continue
            gorulen.add(anahtar)
            sonuc.append({"ad": f"Otomatik — {etiket} ({t})", "acik": secim})
        dolaplar = [i for i in self.cikislar if self.hatlar[i].tip.startswith("dolap")]
        if dolaplar and sonuc:
            en_uzak_dolap = max(dolaplar, key=self.yol_uzunlugu)
            sonuc.append({"ad": f"Otomatik — en uzak dolap ({en_uzak_dolap})", "acik": [en_uzak_dolap]})
            sonuc.append({"ad": f"Otomatik — {sonuc[0]['ad'].split('— ')[1]} + {en_uzak_dolap}",
                          "acik": sonuc[0]["acik"] + [en_uzak_dolap]})
        return sonuc

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
        ["Bina tehlike sınıfı (en yüksek)", ag.sinif["ad"], "BYKHY md. 19/1 — su ve pompa kapasitesi buna göre"],
        ["Sistem tipi", "Islak / ön etkili" if ag.sistem == "islak" else "Kuru / değişken", ""],
        ["Tasarım yoğunluğu", f"{ag.yogunluk} mm/dk", "BYKHY Ek-8/B, TS EN 12845 Tablo 3"],
        ["Operasyon (tasarım) alanı", f"{ag.tasarim_alani:g} m²", "BYKHY Ek-8/B"],
        ["Min. sprinkler basıncı", f"{ag.sinif['pmin_bar']} bar", "TS EN 12845 12.4"],
        ["Sprinkler başına max alan", f"{ag.sinif['max_alan_m2']} m²", "BYKHY md. 96/5, TS EN 12845"],
        ["Su temin süresi", f"{ag.sinif['sure_dk']} dk", "BYKHY md. 92/3"],
        ["Boru serisi / C", f"{ag.seri_ad} / C={ag.C:g}", "TS EN 12845 (Hazen-Williams)"],
    ]))

    _mahal_tablosu(s, ag)
    _zorunluluk_kontrol(s, ag, bina, k)
    _kompartiman_kontrol(s, ag, g, bina, k)
    _eleman_kontrol(s, ag, k)
    for seviye, nesne, mesaj, ref in ag.geo_notlar:
        s.bulgu(seviye, nesne, mesaj, ref)
    if ag.geo:
        tg = Tablo("Kapsama alanı kontrolü (plandan)", ["Mahal", "Mahal alanı m²", "Sprinkler",
                   "Σ hücre m²", "Min hücre m²", "Max hücre m²", "Max aralık m", "Max duvar m",
                   "R_max m", "İhlal"])
        for mid, a in ag.geo.items():
            al = a["alanlar"].values()
            ihlal = sum(1 for t in a["ihlaller"] if t[0] != "yakin")
            tg.satirlar.append([a["ad"], yuvarla(a["mahal_alani"]), len(a["idler"]), yuvarla(a["hucre_toplami"]),
                                yuvarla(min(al)), yuvarla(max(al)), a["smax"], a["dmax"], yuvarla(a["r_max"]),
                                ihlal or "OK"])
        s.tablolar.append(tg)

    senaryolar = list(g.get("senaryolar") or [])
    oto = g.get("otomatik_senaryo")
    if oto or (not senaryolar and ag.geo and ag.sprinklerler):
        ayar = oto if isinstance(oto, dict) else {}
        eklenen = ag.otomatik_senaryolar(ayar.get("uzun_eksen", "x"), float(ayar.get("oran", 1.5)))
        senaryolar += eklenen
        s.bulgu(BILGI, "senaryolar", f"{len(eklenen)} aday tasarım alanı otomatik üretildi (en uzak sprinkler / "
                "en yüksek kot; uzun kenar branşman yönünde). Mühendis ek aday alanlar tanımlayabilir.",
                "TS EN 12845 (en elverişsiz tasarım alanı)")
    if not senaryolar:
        s.bulgu(HATA, "senaryolar", "En az bir hesap senaryosu (açık çıkış listesi) tanımlanmalı")
        return s

    ozet = Tablo("Senaryo özeti", ["Senaryo", "Sınıf", "Açık sprinkler", "Açık dolap/hidrant",
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
        sn_sinif = ag.en_yuksek([ag.hatlar[i].sinif_kod for i in spr]) if spr else None
        sn_alan = ag.tasarim_alani_of(sn_sinif) if sn_sinif else 0.0
        sonuclar[-1]["sinif"] = sn_sinif
        if spr and kapsama + 1e-6 < sn_alan:
            eksik = math.ceil((sn_alan - kapsama) / max(ag.hatlar[spr[0]].alan, 1e-9))
            s.bulgu(HATA, ad, f"Açık sprinklerlerin toplam kapsama alanı {kapsama:.1f} m² < {sn_sinif} tasarım "
                    f"alanı {sn_alan:g} m² — yaklaşık {eksik} sprinkler daha senaryoya eklenmeli",
                    "BYKHY Ek-8/B, TS EN 12845 Tablo 3")
        ozet.satirlar[-1].insert(1, sn_sinif or "-")
        _tasarim_alani_bicimi(s, ag, ad, spr, sn_alan)
        _senaryo_tablolari(s, ag, ad, acik, cz)
        _hiz_kontrol(s, ag, ad, cz, k)
        _dolap_basinc_kontrol(s, ag, ad, diger, cz)
    s.tablolar.insert(1, ozet)

    if not any(r["spr"] for r in sonuclar) and ag.sprinklerler:
        s.bulgu(HATA, "senaryolar", "Sprinkler içeren hiçbir senaryo yok — en elverişsiz tasarım alanı hesaplanmalı")

    belirleyici = max(sonuclar, key=lambda r: r["cz"]["ps"])
    _plan_cizimleri(s, ag, sonuclar)
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


def _tasarim_alani_bicimi(s, ag: YanginAgi, ad, spr, tasarim_alani):
    """EN 12845: tasarım alanı yaklaşık dikdörtgen, uzun kenarı ≥ 1,2·√A."""
    if not spr or not all(i in ag.geo_alan for i in spr):
        return
    mahal_ad = {i: m for m, a in ag.geo.items() for i in a["idler"]}
    hucre = [ag.geo[mahal_ad[i]]["hucreler"][i] for i in spr]
    a, b = kapsama.sinir_kutusu(hucre)
    gerek = 1.2 * math.sqrt(tasarim_alani)
    if max(a, b) + 1e-6 < gerek:
        s.bulgu(UYARI, ad, f"Tasarım alanının uzun kenarı {max(a, b):.2f} m < 1,2·√A = {gerek:.2f} m — "
                "alan branşmanlar boyunca uzatılmalı", "TS EN 12845 (tasarım alanı biçimi)")


def _plan_cizimleri(s, ag: YanginAgi, sonuclar):
    """Kat başına tek plan: mahal sınırları (sınıf rengi), sprinkler hücreleri, belirleyici tasarım alanı."""
    if not ag.geo:
        return
    spr_sen = [r for r in sonuclar if r["spr"] and not r["diger"]] or [r for r in sonuclar if r["spr"]]
    bel = max(spr_sen, key=lambda r: r["cz"]["ps"]) if spr_sen else None
    acik = set(bel["spr"]) if bel else set()
    katlar: dict = {}
    for m in ag.g.get("mahaller") or []:
        mid = str(m["id"])
        katlar.setdefault(str(m.get("kat", "")), []).append({
            "id": mid, "ad": ag.mahal_bilgi[mid]["ad"], "sinif": ag.mahal_bilgi[mid]["sinif"],
            "poligon": [tuple(map(float, p[:2])) for p in m["poligon"]], "analiz": ag.geo.get(mid),
            "alan_max": ag.geo[mid]["alan_max"] if mid in ag.geo else 0})
    for kat, liste in katlar.items():
        ids = {m["id"] for m in liste}
        dolaplar = [(i, tuple(map(float, ag.hatlar[i].ham["konum"][:2]))) for i in ag.cikislar
                    if ag.hatlar[i].tip != "sprinkler" and ag.hatlar[i].ham.get("konum")
                    and str(ag.hatlar[i].ham.get("mahal")) in ids]
        baslik = "Kapsama planı" + (f" — kat {kat}" if kat else "") + (f" (mavi: {bel['ad']})" if bel else "")
        s.sekiller.append({"baslik": baslik, "svg": kapsama.svg_kat_plani(baslik, liste, acik, dolaplar)})


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
    sinif_tum = ag.siniflar
    tb = Tablo("Sprinkler yerleşim kontrolü", ["Sprinkler", "Sınıf", "K", "Kapsama m²", "Alan kaynağı", "Max m²",
                                                "Min Q l/dk", "Min P bar", "Durum"])
    for i in ag.sprinklerler:
        h = ag.hatlar[i]
        sinif = sinif_tum[h.sinif_kod]
        durum = []
        if h.alan > sinif["max_alan_m2"] + 1e-9:
            durum.append("alan aşımı")
            s.bulgu(HATA, i, f"Sprinkler kapsama alanı {h.alan:g} m² > {sinif['max_alan_m2']} m²",
                    "BYKHY md. 96/5, TS EN 12845")
        if int(round(h.K)) not in [int(x) for x in sinif["K"]]:
            durum.append("K uygun değil")
            s.bulgu(UYARI, i, f"K={h.K:g} bu tehlike sınıfı için öngörülen {sinif['K']} değil",
                    "TS EN 12845 Tablo 37")
        tb.satirlar.append([i, h.sinif_kod, h.K, yuvarla(h.alan), h.alan_kaynak, sinif["max_alan_m2"], yuvarla(h.qmin, 1),
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


def _mahal_tablosu(s, ag: YanginAgi):
    if not ag.mahal_bilgi:
        return
    alanlar = {}
    for m in ag.g.get("mahaller") or []:
        if m.get("poligon"):
            alanlar[str(m["id"])] = kapsama.alan([tuple(map(float, p[:2])) for p in m["poligon"]])
    t = Tablo("Mahal tehlike sınıfları (BYKHY md. 19, Ek-1)",
              ["Mahal", "Ad", "Tip", "Alan m²", "Tehlike sınıfı", "Yoğunluk mm/dk", "Dayanak / not"])
    for mid, mb in ag.mahal_bilgi.items():
        sinif = mb["sinif"]
        yog = ag.siniflar[sinif]["yogunluk"] if sinif else "-"
        not_ = mb["kaynak"] + (f" — {mb['not']}" if mb.get("not") else "")
        t.satirlar.append([mid, mb["ad"], mb["tip"] or "-", yuvarla(alanlar.get(mid)) if mid in alanlar else "-",
                           sinif or "MUAF", yog, not_])
        if "⚠" in (mb["kaynak"] or "") and sinif:
            s.bulgu(UYARI, mid, f"{mb['ad']}: tehlike sınıfı {sinif} benzeşimle atandı — mühendis onayı gerekli "
                    f"({mb['kaynak']})", "BYKHY md. 19, Ek-1")
    s.tablolar.append(t)


def _kompartiman_kontrol(s, ag: YanginAgi, g, bina, k):
    komps = g.get("kompartimanlar") or []
    alanlar = {}
    for m in g.get("mahaller") or []:
        if m.get("poligon"):
            alanlar[str(m["id"])] = kapsama.alan([tuple(map(float, p[:2])) for p in m["poligon"]])
    dt_sinir = k["dusuk_tehlike_kompartiman_m2"]
    if not komps:
        for mid, mb in ag.mahal_bilgi.items():
            if mb["sinif"] == "DT":
                s.bulgu(UYARI, mid, f"Düşük Tehlike için mahal ≤ {dt_sinir} m² ve en az 30 dk dayanımlı bir "
                        "kompartıman olmalı — kompartıman tanımlanmadı, doğrulanamadı", "BYKHY Ek-1/A, md. 19/2-a")
        return
    sprinklerli = bool(ag.sprinklerler)
    t = Tablo("Yangın kompartımanları (BYKHY Ek-4)", ["Kompartıman", "Kullanım", "Alan m²", "Sınır m²", "Durum"])
    atanan = set()
    for km in komps:
        kid = str(km.get("id"))
        kul = km.get("kullanim") or bina.get("kullanim")
        tablo = k["kompartiman"].get(kul)
        if tablo is None:
            raise GirdiHatasi(f"yangin.kompartimanlar/{kid}: kullanim '{kul}' Ek-4 tablosunda yok. "
                              f"Seçenekler: {', '.join(k['kompartiman'])}")
        mahaller = [str(x) for x in km.get("mahaller") or []]
        for mid in mahaller:
            if mid not in ag.mahal_bilgi:
                raise GirdiHatasi(f"yangin.kompartimanlar/{kid}: mahal '{mid}' tanımlı değil")
        atanan.update(mahaller)
        alan = float(km["alan_m2"]) if km.get("alan_m2") is not None else sum(alanlar.get(m, 0.0) for m in mahaller)
        if tablo["max_m2"] is None:
            sinir, durum = None, "OK (sınırsız)"
        else:
            kat = tablo.get("katsayi", None) if sprinklerli else 1
            if sprinklerli and kat is None:
                sinir, durum = None, "OK (yangın kontrol sistemiyle sınırsız)"
            else:
                sinir = tablo["max_m2"] * (kat or 1)
                durum = "OK" if alan <= sinir + 1e-6 else "AŞIM"
                if durum == "AŞIM":
                    s.bulgu(HATA, kid, f"Kompartıman alanı {alan:.0f} m² > {sinir:.0f} m² ({kul}"
                            + (f", yangın kontrol sistemi ile ×{kat}" if sprinklerli and kat else "") + ") — "
                            "kompartıman bölünmeli (yangın duvarı/kapısı)", "BYKHY md. 24/6, Ek-4")
        dt_mahal = [m for m in mahaller if ag.mahal_bilgi[m]["sinif"] == "DT"]
        if dt_mahal and alan > dt_sinir + 1e-6:
            s.bulgu(HATA, kid, f"Düşük Tehlike mahalleri ({', '.join(dt_mahal)}) {alan:.0f} m² kompartımanda — "
                    f"DT için kompartıman ≤ {dt_sinir} m² olmalı; aksi halde OT1 alınmalı", "BYKHY Ek-1/A, md. 19/2-a")
        t.satirlar.append([km.get("ad", kid), kul, yuvarla(alan, 1), yuvarla(sinir, 0) if sinir else "sınırsız", durum])
    for mid in ag.mahal_bilgi:
        if mid not in atanan:
            s.bulgu(UYARI, mid, "Mahal hiçbir kompartımana atanmamış", "BYKHY Ek-4")
    s.tablolar.append(t)


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
    yatakli = kullanim in ("otel", "yurt", "konaklama", "hastane", "yatakli_tesis") or bool(bina.get("yatakli"))
    if yatakli and yy and yy > z["konaklama_yapi_yuksekligi_m"]:
        neden.append(f"yataklı tesis, yapı yüksekliği > {z['konaklama_yapi_yuksekligi_m']} m (md. 96/2-ç)")
    if bina.get("magaza_m2", 0) > z["magaza_m2"]:
        neden.append(f"katlı mağaza/AVM > {z['magaza_m2']} m² (md. 96/2-d)")
    if bina.get("parlayici_m2", 0) > z["parlayici_m2"]:
        neden.append(f"parlayıcı/kolay alevlenici madde alanı > {z['parlayici_m2']} m² (md. 96/2-e)")
    if not neden and ag.sprinklerler:
        s.bulgu(BILGI, "zorunluluk", "Girilen bina verileriyle BYKHY md. 96/2 kapsamında sprinkler ZORUNLULUĞU "
                "tespit edilmedi (yapı yüksekliği, otopark, yatak/oda sayısı, mağaza ve parlayıcı alan eşikleri). "
                "Sistem idare/işveren şartı veya gönüllü olarak tasarlanıyor; yapılırsa TS EN 12845'e uygun olmalıdır.",
                "BYKHY md. 96/2, 96/5")
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
