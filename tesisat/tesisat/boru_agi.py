"""DXF plan çiziminden boru ağı çıkarımı (ezdxf + Shapely + NetworkX).

Kurallar (METRAJ_KURALLARI.md → "DXF'ten ağ"):
  G1  Boru = boru katmanındaki LINE / LWPOLYLINE / POLYLINE parçaları (yaylar kirişle).
  G2  Bağlantı yalnız şu durumlarda kurulur: (a) uç noktalar birleştirme toleransı içinde,
      (b) bir parçanın UCU başka bir parçanın gövdesi üzerinde (T bağlantısı → gövde bölünür).
      İki parçanın gövdelerinin kesişmesi BAĞLANTI DEĞİLDİR (üst/alt geçiş) → belirsizlik.
  G3  Sprinkler = sprinkler bloğu; ekleme noktası en yakın boruya (sprinkler toleransı) bağlanır.
  G4  Çap = boru yakınındaki yazı (DN50, Ø50, 2", 1 1/4", 1¼"…), en yakın boru parçasına atanır;
      etiketsiz parçalar, düz devam eden (2 bağlantılı, sprinklersiz) düğümler üzerinden yayılır.
      Hâlâ etiketsiz kalanlara beslenen sprinkler sayısından çap ÖNERİLİR ve belirsizlik yazılır.
  G5  Kaynak düğümünden ağaç kurulur; döngü varsa ağ ağaç değildir → hata (döngülü ağ çözülmez).
  D2  2 bağlantılı ara düğümde yön değişimi: ≥ 67,5° → 90° dirsek, 22,5–67,5° → 45° dirsek.
  T5  Dallanmada ana yönden ≥ 45° sapan çıkışa hidrolik "te dönüş" kaybı eklenir.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field

import networkx as nx
from shapely.geometry import LineString, Point
from shapely.strtree import STRtree

from .cizim import _ac, _eslesir, _olcek
from .ortak import GirdiHatasi

INC_DN = {"1/2": 15, "3/4": 20, "1": 25, "1 1/4": 32, "1 1/2": 40, "2": 50, "2 1/2": 65, "3": 80, "4": 100,
          "5": 125, "6": 150, "8": 200, "½": 15, "¾": 20, "1¼": 32, "1½": 40, "2½": 65}
DN_LISTE = [15, 20, 25, 32, 40, 50, 65, 80, 100, 125, 150, 200, 250, 300]
_RE_DN = re.compile(r"\bDN\s*(\d{2,3})\b", re.I)
_RE_O = re.compile(r"[Ø∅ø]\s*(\d{2,3})(?:[.,]\d+)?")
_RE_INC = re.compile(r'(\d\s+\d/\d|\d[½¼¾]|\d/\d|\d)\s*(?:"|”|″|\'\'|inç|inch)', re.I)
# Dış çap (mm) → DN (TS EN 10255 / ISO 65)
OD_DN = {21.3: 15, 26.9: 20, 33.7: 25, 42.4: 32, 48.3: 40, 60.3: 50, 76.1: 65, 88.9: 80, 114.3: 100, 139.7: 125,
         165.1: 150, 219.1: 200}


def cap_oku(metin: str) -> int | None:
    t = metin.replace(",", ".")
    if m := _RE_DN.search(t):
        dn = int(m.group(1))
        return dn if dn in DN_LISTE else None
    if m := _RE_INC.search(t):
        k = re.sub(r"\s+", " ", m.group(1)).strip()
        return INC_DN.get(k)
    if m := _RE_O.search(t):
        v = float(re.search(r"[\d.]+", m.group(0)[1:].strip()).group(0))
        if int(v) in DN_LISTE and v == int(v):
            return int(v)
        yakin = min(OD_DN, key=lambda od: abs(od - v))
        return OD_DN[yakin] if abs(yakin - v) < 1.0 else None
    return None


def oneri_cap(n_spr: int) -> int:
    for sinir, dn in [(2, 25), (3, 32), (5, 40), (10, 50), (20, 65), (40, 80)]:
        if n_spr <= sinir:
            return dn
    return 100


@dataclass
class AgSonucu:
    hatlar: list[dict]
    belirsizlikler: list[str] = field(default_factory=list)
    ozet: dict = field(default_factory=dict)


def _yon(a, b):
    return math.atan2(b[1] - a[1], b[0] - a[0])


def _sapma(g1, g2):
    d = abs(math.degrees(g2 - g1)) % 360
    return 360 - d if d > 180 else d


def ag_cikar(yol: str, boru_katmani: list[str], sprinkler_blok: list[str], kaynak: dict,
             dolap_blok: list[str] | None = None, etiket_katmani: list[str] | None = None,
             birim: str | None = None, on_ek: str = "", kat: str = "", ust: str | None = None,
             tol: dict | None = None) -> AgSonucu:
    tol = {"birlestirme_m": 0.02, "sprinkler_m": 0.40, "etiket_m": 0.80, **(tol or {})}
    doc = _ac(yol)
    msp = doc.modelspace()
    s, birim_acik = _olcek(doc, birim)
    notlar: list[str] = []

    # --- G1: parçalar
    parcalar: list[LineString] = []
    for e in msp:
        if e.dxftype() not in ("LINE", "LWPOLYLINE", "POLYLINE") or not _eslesir(e.dxf.layer, boru_katmani):
            continue
        if e.dxftype() == "LINE":
            pts = [(e.dxf.start.x * s, e.dxf.start.y * s), (e.dxf.end.x * s, e.dxf.end.y * s)]
        elif e.dxftype() == "LWPOLYLINE":
            pts = [(x * s, y * s) for x, y in e.get_points("xy")]
            if e.closed:
                pts.append(pts[0])
        else:
            pts = [(v.dxf.location.x * s, v.dxf.location.y * s) for v in e.vertices]
        for a, b in zip(pts, pts[1:]):
            if math.dist(a, b) > 1e-6:
                parcalar.append(LineString([(float(a[0]), float(a[1])), (float(b[0]), float(b[1]))]))
    if not parcalar:
        raise GirdiHatasi(f"'{', '.join(boru_katmani)}' katmanında boru çizgisi bulunamadı — 'dxf-ozet' ile kontrol edin")

    # --- uç noktaları birleştir (G2a)
    temsil: list[tuple[float, float]] = []

    def dugum(p):
        for q in temsil:
            if math.dist(p, q) <= tol["birlestirme_m"]:
                return q
        q = (round(p[0], 4), round(p[1], 4))
        temsil.append(q)
        return q

    kenar = [(dugum(tuple(ls.coords[0])), dugum(tuple(ls.coords[-1]))) for ls in parcalar]

    # --- bölme noktaları: T bağlantısı (G2b), sprinkler (G3), kaynak
    def bol(kenarlar, noktalar, esik):
        """Noktaları, gövdesine esik içinde yaklaştıkları kenarlara ekleyip kenarları böler."""
        geo = [LineString([a, b]) for a, b in kenarlar]
        agac = STRtree(geo)
        ekle: dict[int, list] = {}
        eslesen = {}
        for p in noktalar:
            pt = Point(p)
            aday = [i for i in agac.query(pt.buffer(esik)) if geo[i].distance(pt) <= esik]
            if not aday:
                continue
            i = min(aday, key=lambda j: geo[j].distance(pt))
            a, b = kenarlar[i]
            proj = geo[i].interpolate(geo[i].project(pt))
            q = (round(proj.x, 4), round(proj.y, 4))
            if math.dist(q, a) <= tol["birlestirme_m"]:
                eslesen[p] = a
            elif math.dist(q, b) <= tol["birlestirme_m"]:
                eslesen[p] = b
            else:
                ekle.setdefault(i, []).append(q)
                eslesen[p] = q
        yeni = []
        for i, (a, b) in enumerate(kenarlar):
            if i not in ekle:
                yeni.append((a, b))
                continue
            sira = sorted(set(ekle[i]), key=lambda q: math.dist(a, q))
            zincir = [a] + sira + [b]
            yeni += [(x, y) for x, y in zip(zincir, zincir[1:]) if math.dist(x, y) > 1e-6]
        return yeni, eslesen

    # G2b: bir parçanın UCU başka bir parçanın GÖVDESİ üzerindeyse o gövde bölünür (kendi parçası hariç)
    def t_bol(kenarlar):
        geo = [LineString([a, b]) for a, b in kenarlar]
        agac = STRtree(geo)
        ekle: dict[int, set] = {}
        for p in {n for k in kenarlar for n in k}:
            pt = Point(p)
            for i in agac.query(pt.buffer(tol["birlestirme_m"])):
                a, b = kenarlar[i]
                if p in (a, b) or geo[i].distance(pt) > tol["birlestirme_m"]:
                    continue
                if min(math.dist(p, a), math.dist(p, b)) <= tol["birlestirme_m"]:
                    continue
                ekle.setdefault(i, set()).add(p)
        yeni = []
        for i, (a, b) in enumerate(kenarlar):
            if i not in ekle:
                yeni.append((a, b))
                continue
            zincir = [a] + sorted(ekle[i], key=lambda q: math.dist(a, q)) + [b]
            yeni += [(x, y) for x, y in zip(zincir, zincir[1:]) if math.dist(x, y) > 1e-6]
        return yeni

    kenar = t_bol(kenar)

    # G2 uyarısı: gövde gövde kesişmeleri (bağlantı sayılmaz)
    geo = [LineString([a, b]) for a, b in kenar]
    agac = STRtree(geo)
    kesisme = 0
    for i, g in enumerate(geo):
        for j in agac.query(g):
            if j <= i:
                continue
            x = g.intersection(geo[j])
            if x.is_empty or x.geom_type != "Point":
                continue
            p = (x.x, x.y)
            if min(math.dist(p, q) for q in (*kenar[i], *kenar[j])) > tol["birlestirme_m"]:
                kesisme += 1
    if kesisme:
        notlar.append(f"{kesisme} noktada boru çizgileri kesişiyor ama uç noktası yok — BAĞLANTI SAYILMADI "
                      "(üst/alt geçiş varsayıldı); gerçek bağlantıysa çizimde uç noktası oluşturun")

    def bloklar(desen):
        cikti = []
        for e in msp.query("INSERT"):
            if desen and _eslesir(e.dxf.name, desen):
                cikti.append(((float(e.dxf.insert.x) * s, float(e.dxf.insert.y) * s), e.dxf.name))
        return cikti

    spr_bloklar = bloklar(sprinkler_blok)
    dolap_bloklar = bloklar(dolap_blok or [])
    if "nokta" in kaynak:
        kaynak_p = (float(kaynak["nokta"][0]) * s, float(kaynak["nokta"][1]) * s)
    elif "blok" in kaynak:
        kb = bloklar([kaynak["blok"]] if isinstance(kaynak["blok"], str) else kaynak["blok"])
        if not kb:
            raise GirdiHatasi(f"Kaynak bloğu '{kaynak['blok']}' çizimde yok")
        kaynak_p = kb[0][0]
    else:
        raise GirdiHatasi("kaynak: 'nokta' [x, y] (çizim biriminde) veya 'blok' deseni verin")

    kenar, spr_es = bol(kenar, [p for p, _ in spr_bloklar], tol["sprinkler_m"])
    kenar, dol_es = bol(kenar, [p for p, _ in dolap_bloklar], tol["sprinkler_m"])
    kenar, kay_es = bol(kenar, [kaynak_p], 1.0)
    if kaynak_p not in kay_es:
        raise GirdiHatasi("Kaynak noktası hiçbir boruya 1 m'den yakın değil")
    kok = kay_es[kaynak_p]
    for p, ad in spr_bloklar:
        if p not in spr_es:
            notlar.append(f"Sprinkler bloğu {ad} ({p[0]:.2f}, {p[1]:.2f}) hiçbir boruya {tol['sprinkler_m']} m'den "
                          "yakın değil — ağa bağlanmadı")
    spr_dugum = {q: p for p, q in spr_es.items()}
    dol_dugum = {q: p for p, q in dol_es.items()}

    # --- grafik
    G = nx.Graph()
    for a, b in kenar:
        if a != b:
            G.add_edge(a, b, L=math.dist(a, b), dn=None, etiket=False)
    if kok not in G:
        raise GirdiHatasi("Kaynak düğümü ağda değil")
    bilesen = nx.node_connected_component(G, kok)
    disari = G.number_of_nodes() - len(bilesen)
    if disari:
        kopuk_spr = sum(1 for q in spr_dugum if q not in bilesen)
        notlar.append(f"Kaynağa bağlı olmayan {disari} düğüm (ve {kopuk_spr} sprinkler) ağ dışında bırakıldı — "
                      "çizimde kopukluk olabilir")
    G = G.subgraph(bilesen).copy()
    if not nx.is_forest(G):
        dongu = nx.cycle_basis(G)
        raise GirdiHatasi(f"Ağda {len(dongu)} döngü var (ör. {dongu[0][:3]}…) — döngülü/ızgara ağ henüz çözülmüyor; "
                          "çizimde kapalı çevrim olup olmadığını kontrol edin")

    # --- G4: çap etiketleri
    etiketler = []
    for e in msp.query("TEXT MTEXT"):
        if etiket_katmani and not _eslesir(e.dxf.layer, etiket_katmani):
            continue
        metin = e.plain_text() if e.dxftype() == "MTEXT" else e.dxf.text
        dn = cap_oku(metin)
        if dn:
            etiketler.append(((float(e.dxf.insert.x) * s, float(e.dxf.insert.y) * s), dn, metin))
    kenarlar = list(G.edges())
    if kenarlar and etiketler:
        geo = [LineString([a, b]) for a, b in kenarlar]
        agac = STRtree(geo)
        for p, dn, metin in etiketler:
            pt = Point(p)
            aday = [i for i in agac.query(pt.buffer(tol["etiket_m"])) if geo[i].distance(pt) <= tol["etiket_m"]]
            if not aday:
                continue
            i = min(aday, key=lambda j: geo[j].distance(pt))
            a, b = kenarlar[i]
            onceki = G.edges[a, b]["dn"]
            if onceki and onceki != dn:
                notlar.append(f"Aynı boru parçasına iki farklı çap etiketi yakın: DN{onceki} ve DN{dn} ('{metin}')")
            G.edges[a, b]["dn"], G.edges[a, b]["etiket"] = dn, True

    def gecis(n):   # çap yayılabilen düz devam düğümü
        return G.degree(n) == 2 and n not in spr_dugum and n not in dol_dugum and n != kok

    degisti = True
    while degisti:
        degisti = False
        for n in list(G.nodes):
            if not gecis(n):
                continue
            (a, b) = list(G.edges(n))
            da, db = G.edges[a]["dn"], G.edges[b]["dn"]
            if da and not db:
                G.edges[b]["dn"] = da
                degisti = True
            elif db and not da:
                G.edges[a]["dn"] = db
                degisti = True

    # --- G5: kaynaktan ağaç
    T = nx.bfs_tree(G, kok)
    alt_spr = {}
    for n in reversed(list(nx.topological_sort(T))):
        alt_spr[n] = (1 if n in spr_dugum else 0) + sum(alt_spr[c] for c in T.successors(n))
    oneri = 0
    for u, v in T.edges():
        if not G.edges[u, v]["dn"]:
            G.edges[u, v]["dn"] = oneri_cap(alt_spr[v])
            G.edges[u, v]["oneri"] = True
            oneri += 1
    if oneri:
        notlar.append(f"{oneri} boru parçasında çap etiketi bulunamadı; çap, beslenen sprinkler sayısından ÖNERİLDİ "
                      "(kontrol gerekli)")

    # --- hatlara dönüştür: kırılma düğümleri
    def kirilma(n):
        if n == kok or n in spr_dugum or n in dol_dugum:
            return True
        cocuk = list(T.successors(n))
        if len(cocuk) != 1:
            return True
        p = next(iter(T.predecessors(n)))
        return G.edges[p, n]["dn"] != G.edges[n, cocuk[0]]["dn"]

    hatlar, sayac = [], {"h": 0, "s": 0, "d": 0}
    dugum_hat: dict = {kok: ust}

    def yeni_id(tur):
        sayac[tur] += 1
        return f"{on_ek}{'H' if tur == 'h' else ('S' if tur == 's' else 'YD')}{sayac[tur]:03d}"

    yigin = [(kok, c) for c in T.successors(kok)]
    while yigin:
        bas, ilk = yigin.pop(0)
        zincir = [bas, ilk]
        while not kirilma(zincir[-1]):
            zincir.append(next(iter(T.successors(zincir[-1]))))
        son = zincir[-1]
        L = sum(G.edges[a, b]["L"] for a, b in zip(zincir, zincir[1:]))
        dn = G.edges[zincir[0], zincir[1]]["dn"]
        parca = {}
        for a, b, c in zip(zincir, zincir[1:], zincir[2:]):
            sap = _sapma(_yon(a, b), _yon(b, c))
            if sap >= 67.5:
                parca["dirsek_90"] = parca.get("dirsek_90", 0) + 1
            elif sap >= 22.5:
                parca["dirsek_45"] = parca.get("dirsek_45", 0) + 1
        # T5: dallanmadan çıkış yönü
        onc = list(T.predecessors(bas))
        if onc and len(list(T.successors(bas))) >= 2:
            if _sapma(_yon(onc[0], bas), _yon(bas, ilk)) >= 45:
                parca["te_donus"] = 1
        tur = "s" if son in spr_dugum else ("d" if son in dol_dugum else "h")
        hid = yeni_id(tur)
        h = {"id": hid, "ust": dugum_hat[bas], "uzunluk_m": round(L, 3), "kot_farki_m": 0.0, "cap": str(dn),
             "kat": kat, "uzunluk_yontemi": "ölçülen"}
        if any(G.edges[a, b].get("oneri") for a, b in zip(zincir, zincir[1:])):
            h["cap_onerildi"] = True
        if parca:
            h["parcalar"] = parca
        if tur == "s":
            h["sprinkler"] = True
            h["konum"] = [round(son[0], 3), round(son[1], 3)]
            h["konum_yontemi"] = "ölçülen"
        elif tur == "d":
            h["cikis"] = "dolap_yari_sert"
            h["konum"] = [round(son[0], 3), round(son[1], 3)]
            h["konum_yontemi"] = "ölçülen"
        hatlar.append(h)
        dugum_hat[son] = hid
        yigin += [(son, c) for c in T.successors(son)]

    return AgSonucu(hatlar, notlar, {
        "birim": birim_acik, "boru_parcasi": len(parcalar), "dugum": G.number_of_nodes(),
        "sprinkler_cizimde": len(spr_bloklar), "sprinkler_agda": sum(1 for q in spr_dugum if q in G),
        "dolap": sum(1 for q in dol_dugum if q in G), "cap_etiketi": len(etiketler), "cap_onerilen_parca": oneri,
        "toplam_boru_m": round(sum(d["L"] for *_, d in G.edges(data=True)), 3), "hat": len(hatlar)})
