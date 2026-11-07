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

## 5. İncelenen diğer açık kaynak projeler

| Repo | Gözlem |
|---|---|
| [projecthanif/mep-toolkit](https://github.com/projecthanif/mep-toolkit) | DU değerleri bizimle uyumlu. Ancak kolon çapını standart tablosu yerine kaba eşiklerle seçiyor (Qww ≤ 2 → DN100) ve pik su debisinde EN 806-3 eğrisi yerine `0,25·√ΣLU` yaklaşımını kullanıyor. Referans olarak alınmadı. |
| [ak1080/Plumbing_Pipe_Sizer](https://github.com/ak1080/Plumbing_Pipe_Sizer), DerekEubanks Revit eklentileri | ABD kodlarını (UPC/IPC) kullanıyor; TS EN sistemine doğrudan uygulanamaz. |

## Sınırlar

- EN 12056-2 değerleri resmî bir kurumun yayımladığı alıntı görüntülerinden doğrulandı, standardın lisanslı metninden değil. Resmî onay öncesinde TSE nüshasıyla son bir kontrol yapılmalıdır.
- Bu araç bir hesap yardımcısıdır; imzalı proje sorumluluğu yetkili makine mühendisindedir.
