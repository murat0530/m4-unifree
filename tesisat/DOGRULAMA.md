# Doğrulama Kaydı — Kural ve Formül Kaynakları

Bu belge, `tesisat/kurallar_varsayilan.yaml` ve `tesisat/hidrolik.py` içindeki
değerlerin **hangi bağımsız kaynakla karşılaştırıldığını** kaydeder.
Yeni bir değer eklendiğinde veya değiştirildiğinde bu tablo güncellenmelidir.

Durum işaretleri: ✅ birebir doğrulandı · 🔧 kontrolde hata bulundu, düzeltildi · ⚠️ ikincil kaynak, standart nüshasıyla teyit edilmeli

## 1. Hidrolik formüller

| Konu | Karşılaştırılan kaynak | Sonuç |
|---|---|---|
| Colebrook-White λ | [CalebBell/fluids](https://github.com/CalebBell/fluids) `fluids.friction.Colebrook` (v1.3.1) | ✅ 5 farklı Re/ε noktasında fark < %0,05. Kalan küçük fark, EN 12056/DIN'deki 3,71 sabiti yerine `fluids` paketinin 3,7 kullanmasından gelir. |
| Huebscher eşdeğer çap `1,30·(ab)^0,625/(a+b)^0,25` | [GitMecHub/HVAC-Duct_Sizing](https://github.com/GitMecHub/HVAC-Duct_Sizing) | ✅ Aynı formül |
| Galvaniz kanal pürüzlülüğü 0,09 mm | GitMecHub/HVAC-Duct_Sizing (ASHRAE) | ✅ |
| Su yoğunluğu/viskozitesi tablosu | [Ulroz/mekanik_tesisat_hidrolik_hesap_ve_tasarim](https://github.com/Ulroz/mekanik_tesisat_hidrolik_hesap_ve_tasarim) (CoolProp IAPWS-95 verisi) | ✅ 10 °C: 999,7 / 1,307 mm²/s; 60 °C: 983,2 / 0,474 mm²/s; tüm noktalar ≤ %0,05 |
| Kısmi dolu boru (Prandtl-Colebrook, kb = 1,0 mm) | Elle hesap: DN100 (di = 100 mm), %1 eğim, h/d = 0,5 | ✅ Q = 2,79 l/s, v = 0,71 m/s (yarı dolu boruda hidrolik yarıçap tam doluyla aynı olduğundan tam dolu debinin yarısı) |

## 2. Temiz su — DIN 1988-300

| Değer | Kaynak | Sonuç |
|---|---|---|
| Pik debi sabitleri a, b, c (konut 1,48/0,19/0,94; otel 0,70/0,48/0,13; hastane 0,75/0,44/0,18; okul/idari 0,91/0,31/0,38) | Ulroz reposu (bağımsız Türk uygulaması) | ✅ Birebir |
| Huzurevi sabitleri 1,40/0,14/0,92 | Ulroz reposu | 🔧 Eksikti, eklendi |
| ΣVR < 0,2 l/s → Vs = ΣVR kuralı | Ulroz reposu `docs/DENETIM_RAPORU.md` M-8 | 🔧 Kural dosyasına not edildi. Hesap modülü bu kuralla yazılacak (ilk tasarımda bu aralıkta debi düşük çıkıyordu). |
| Armatür VR değerleri (lavabo 0,07; duş 0,15; WC rezervuar 0,13; çamaşır mak. 0,15; pisuvar basınçlı 0,30; bahçe musluğu 0,30) | Ulroz reposu | ✅ Birebir |
| Katsayıların baskısı | DIN 1988-300:2012. 2023 revizyonu "sıhhi mahal" kavramını getirdi | ⚠️ Proje hangi baskıya tabiyse onunla teyit edilmeli |

## 3. Atık su — TS EN 12056-2, Sistem I

Kaynak: Avustralya Yapı Kodları Kurulu (ABCB) resmî raporu *Sanitary Plumbing & Drainage Pipe Sizing, Final Report v1.1 (2022)*.
Bu rapor BS EN 12056-2:2000 tablolarını görüntü olarak alıntılar. Değerler bu görüntülerden tek tek okunarak karşılaştırıldı.

| Tablo | İçerik | Sonuç |
|---|---|---|
| Tablo 1 | DN ↔ minimum iç çap | 🔧 Eksikti, `min_ic_cap` olarak eklendi |
| Tablo 2 | DU değerleri (Sistem I) — 17 armatür | ✅ Hepsi birebir |
| Tablo 3 | K = 0,5 / 0,7 / 1,0 / 1,2 | ✅ |
| Tablo 4 | Havalandırmasız bağlantı Qmax (DN40 0,50 … DN100 2,50) | ✅ Değerler doğru · 🔧 Tablo numarası yanlıştı (6 yazılmıştı); DN80 "WC yok" ve DN90 "≤2 WC" dipnotları eklendi |
| Tablo 5 | Havalandırmasız sınırlar: L ≤ 4 m, ≤ 3 dirsek, düşüş ≤ 1 m, eğim ≥ %1 | ✅ |
| Tablo 7 | Havalandırmalı bağlantı Qmax (DN50 0,75 … DN100 3,75) | ✅ Değerler doğru · 🔧 Tablo numarası yanlıştı (5 yazılmıştı) |
| Tablo 8 | Havalandırmalı sınırlar: L ≤ 10 m, dirsek sınırsız, düşüş ≤ 3 m, **eğim ≥ %0,5** | 🔧 Eksikti, eklendi (önceden tüm bağlantılara %1 uygulanıyordu) |
| Tablo 11 | Birincil havalandırmalı kolon (DN60 … DN200, köşeli/yuvarlatılmış giriş) | ✅ Hepsi birebir · WC varsa min DN100 dipnotu ✅ |
| Tablo 12 | İkincil havalandırmalı kolon | ✅ DN100–200 doğru · 🔧 DN60–90 satırları eksikti, eklendi |

## 4. Havalandırma — EN 16798-1 / -3

| Değer | Durum |
|---|---|
| Kat. II: 7 l/s·kişi + 0,7 l/s·m² (az kirletici bina) | ⚠️ Yaygın kaynaklarla uyumlu; bağımsız repo kaynağı bulunamadı |
| Konut egzozu: banyo 15, WC 10, mutfak 20 l/s (Tablo B.8, Kat. II) | ⚠️ Standart nüshasıyla teyit edilmeli |
| Genel WC 10 h⁻¹ + 50 m³/h·armatür; otopark 6 h⁻¹ | ⚠️ Uygulama pratiği. İdare şartnamesi ve yangın yönetmeliği esas alınmalı |
| SFP sınıfları (EN 16798-3) | ⚠️ Teyit edilmeli |

## 5. Yangın — BYKHY + TS EN 12845

Birincil kaynak: **BYKHY resmî konsolide metni** ([mevzuat.gov.tr](https://www.mevzuat.gov.tr/MevzuatMetin/21.5.200712937.pdf)). Maddeler metinden doğrudan okundu.
İkincil kaynak: İtalyan Mühendisler Odası (Nuoro) ders notu *Impianti estinzione* — EN 12845 tabloları alıntılı.

| Değer | Kaynak | Sonuç |
|---|---|---|
| Tasarım yoğunluğu ve alanı (DT 2,25/84; OT1 5/72-90; OT2 5/144-180; OT3 5/216-270; OT4 5/360; YT 260-325) | BYKHY Ek-8/B ve EN 12845 Tablo 3 (İtalyan notu) | ✅ İki kaynak birebir aynı |
| YT-1 yoğunluğu | BYKHY Ek-8/B **7,7**; EN 12845 **7,5** mm/dk | 🔧 Kaynaklar farklı. İhtiyatlı olarak 7,7 alındı. |
| Su temin süresi 30/60/90 dk | BYKHY md. 92/3 | ✅ |
| Minimum depo hacmi (Ek-8/A) | BYKHY Ek-8/A | ✅ Tablo okundu. Satır eşleşmeleri PDF düzeninden çıkarıldı. |
| Dolap/hidrant ek debisi (100/200, 400/1000/1500 l/dk) | BYKHY Ek-8/C | ✅ |
| Yarı-sert dolap 100 l/dk @ 4 bar; yassı 400 l/dk @ 4 bar; lüle > 9 bar → basınç düşürücü | BYKHY md. 94/1-b-5,6 | ✅ |
| Dolap aralığı 30 m (sprinkler hattından beslenirse 45 m) | BYKHY md. 94/1-b-2 | ✅ |
| Hidrant 1900 l/dk @ 7 bar; ring yoksa min DN100 | BYKHY md. 95/2,5 | ✅ |
| Pompa: kapalı vana ≤ %140; %150 debide ≥ %65; talep ≤ %130 anma; yedek pompa | BYKHY md. 93/1-2 | ✅ |
| Sprinkler zorunluluk eşikleri (30,50 / 51,50 m; 600 m² otopark; 100 oda/200 yatak; 2000 m² mağaza; 1000 m² parlayıcı) | BYKHY md. 96/2 | ✅ |
| DT ve OT-1'de sprinkler başına 21 m² | BYKHY md. 96/5 | ✅ (EN 12845 OT için 12 m² der; yönetmelik hükmü uygulandı) |
| Min. sprinkler basıncı DT 0,70 / OT 0,35 / YT 0,50 bar | İtalyan notu (EN 12845) | ✅ |
| K faktörleri DT 57, OT 80, YT 80/115 | İtalyan notu (EN 12845 Tablo 37) | ✅ |
| Min. boru çapı (K ≤ 80 tek sprinkler: 20 mm, diğer: 25 mm) | İtalyan notu (EN 12845 Tablo 36) | ✅ |
| Sprinkler başına max alan OT2-4: 12 m², YT: 9 m² | İtalyan notu (12 m²), IS 15105 özeti (9 m²) | ✅ / ⚠️ |
| Hazen-Williams biçimi `6,05·10⁵·Q^1,85/(C^1,85·d^4,87)` | Canute (EN 12845 hesap yazılımı) dokümantasyonu | ✅ |
| Eşdeğer boy C düzeltmesi `(C/120)^1,85` (C=100 → 0,714) | NICET çalışma kılavuzu | ✅ |
| Eşdeğer boy tablosu (dirsek, te, vana) | NFPA 13 tablosu (ft→m) | ⚠️ EN 12845 Tablo 39 ile teyit edilmeli. Alarm vanası için üretici değeri girilmeli. |
| Hız sınırları 6 m/s (vana) / 10 m/s | — | ⚠️ İkincil kaynakta bulunamadı. Lisanslı metinle teyit edilmeli. |
| Sprinklerler arası en az 2 m (md. 12.3) | selvi.org EN 12845 özetleri | ✅ |
| OT max aralık 4,0 m (Tablo 19) | selvi.org | ✅ |
| DT 4,6 m / YT 3,7 m max aralık | — | ⚠️ Teyit edilmeli. OT-1'de BYKHY 21 m²'ye izin verdiği için 4,6 m alındı ⚠️ |
| Duvara uzaklık ≤ min(2,0 m; S_max/2), şaşırtmalıda 2,3 m, açık kiriş/açık cephe/yanıcı-metal dış duvarda 1,5 m (md. 12.4.1) | selvi.org | ✅ |
| Tasarım alanının uzun kenarı ≥ 1,2·√A | Yaygın EN 12845 uygulaması | ⚠️ Teyit edilmeli |

### Kapsama geometrisi (`tests/test_kapsama.py`, 13 test)
- **6×6 ızgara (3,4 m aralık, duvara 1,7 m):** Her hücre 11,56 m², toplam = mahal alanı (416,16 m²). R_max = √(2² + 2²) = 2,83 m.
- **L biçimli mahal:** Köşe sprinklerinin hücresi el hesabıyla 4×4 = 16 m²; toplam = 108 m² (L alanı).
- **Hatalı yerleşimler yakalanıyor:**
  - eksik sprinkler → korunmayan bölge ve alan aşımı
  - duvar 1 m uzaklaştırılmış → 2,70 m > 2 m
  - 1,5 m aralık → < 2 m
  - mahal dışındaki sprinkler
  - kare biçimli tasarım alanı → 13,6 m < 14,4 m

### Hesap motorunun doğrulanması (`tests/test_yangin.py`, 18 test)
- **Tek sprinkler:** Kaynak basıncı el hesabıyla 2·10⁻⁴ bar içinde aynı.
- **İtalyan notundaki örnek:** OT2, 144 m², 12 m²/sprinkler → 12 sprinkler, 60 l/dk, 0,5625 bar. Birebir tuttu.
- **Dallanmış ağ:**
  - Kütle dengesi sağlanıyor.
  - Simetrik kollarda debiler eşit.
  - Her çıkışta Q = K√P geçerli.
  - Kritik çıkış tam sınırda (oran 1,0000).
  - Enerji dengesi 10⁻⁶ bar içinde.
- **Hazen-Williams:** C=120 kaybı, Darcy-Colebrook ile hesaplanan yeni çelik (k = 0,045 mm) kaybı ile eskimiş çelik (k = 0,5 mm) kaybı arasında kalıyor. Bu, iki bağımsız yöntem arasında fiziksel tutarlılık demek.

## 6. İncelenen diğer açık kaynak projeler

| Repo | Gözlem |
|---|---|
| [projecthanif/mep-toolkit](https://github.com/projecthanif/mep-toolkit) | DU değerleri bizimle uyumlu. Ancak kolon çapını standart tablosu yerine kaba eşiklerle seçiyor (Qww ≤ 2 → DN100) ve pik su debisinde EN 806-3 eğrisi yerine `0,25·√ΣLU` yaklaşımını kullanıyor. Referans olarak alınmadı. |
| [ak1080/Plumbing_Pipe_Sizer](https://github.com/ak1080/Plumbing_Pipe_Sizer), DerekEubanks Revit eklentileri | ABD kodlarını (UPC/IPC) kullanıyor; TS EN sistemine doğrudan uygulanamaz. |

## Sınırlar

- EN 12056-2 değerleri resmî bir kurumun yayımladığı alıntı görüntülerinden doğrulandı, standardın lisanslı metninden değil. Resmî onay öncesinde TSE nüshasıyla son bir kontrol yapılmalıdır.
- Bu araç bir hesap yardımcısıdır; imzalı proje sorumluluğu yetkili makine mühendisindedir.
