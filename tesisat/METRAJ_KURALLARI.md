# Metraj Kuralları — Yangın Tesisatı

Bu belge `tesisat/metraj.py` dosyasının uyguladığı kuralların tamamıdır. Kodda bir kural değişirse bu belge de aynı commit'te güncellenmelidir.

## Temel ilkeler

1. **Miktar ile fiyat ayrıdır.** Metraj motoru yalnızca miktar üretir. Poz numarası ve birim fiyat Excel'in **Fiyatlar** sayfasında kullanıcı tarafından girilir. **Motor poz numarası üretmez veya tahmin etmez.** Pozu girilmemiş kalem keşifte "POZ YOK" olarak görünür.
2. **Her satır izlenebilir.** Her satırda şu bilgiler bulunur:
   - kaynak nesne (ağ hattı ya da düğüm)
   - sistem, kat, birim, miktar
   - **çıkarım yöntemi** ve ondan **ayrı** olarak **onay durumu**
3. **Belirsiz durumlar otomatik kesinleştirilmez.** Kural kesin karar veremiyorsa iki şeyden biri yapılır:
   - kalem "kontrol gerekli" yöntemiyle yazılır,
   - ya da kalem yazılmaz ve **Belirsizlikler** sayfasına kayıt düşülür.
4. **Kontrol edilmiş bir referans yoksa sonuç "doğrulandı" sayılmaz.** Doğrulama sayfası iç tutarlılığı (model ↔ metraj) gösterir. Bu bir doğruluk kanıtı değildir.

## Çıkarım yöntemleri

| Yöntem | Anlamı |
|---|---|
| `ölçülen` | Çizimden (DXF) doğrudan ölçülen uzunluk veya konum |
| `hesaplanan` | Ağ topolojisinden veya bu belgedeki yazılı bir kuraldan türetilen miktar |
| `elle girilen` | Proje dosyasına kullanıcının girdiği değer. Hattın `uzunluk_yontemi` veya `konum_yontemi` alanı yoksa varsayılan budur. |
| `kontrol gerekli` | Kural karar veremedi; mühendis çizimden doğrulamalı |

## Onay durumu (çıkarım yönteminden ayrı)

Çıkarım yöntemi miktarın **nereden geldiğini** söyler. Onay durumu ise satırın **teklife girip giremeyeceğini** söyler. Onay durumu Excel'de formülle hesaplanır:

| Onay durumu | Koşul |
|---|---|
| `belirsizlik açık` | Satıra bağlı belirsizliklerden en az birinin Belirsizlikler sayfasındaki durumu "açık" |
| `onay bekliyor` | Açık belirsizlik yok ve mühendis onayı (L sütunu) boş |
| `onaylandı` | Açık belirsizlik yok ve L sütununda "evet" |

**Belirsizlik bağlantısı:**
- Her belirsizliğin bir numarası vardır (B01…).
- Belirsizlik, satırlara **kaynak nesne** ya da **kalem kodu öneki** üzerinden bağlanır.
- Detay metrajdaki "Belirsizlik no" sütunu satırın bağlı olduğu kayıtları listeler.

Bu sayede yöntemi "hesaplanan" olan bir satır da, belirsizliği çözülene kadar keşifte "belirsizliği açık miktar" olarak görünür.

**Belirsizliğin etkisi** üç türlüdür:
- `miktar`: adet ya da uzunluk değişebilir.
- `kalem tanımı`: satın alma tanımı eksik (bağlantı yöntemi, malzeme, sprinkler tipi gibi).
- `kapsam`: bu kalem grubu teklifte hiç yer almıyor.

## Teklif durumu

"Teklif durumu" sayfası aşağıdakilerin **hepsi** sağlanırsa **TEKLİFE HAZIR**, aksi halde **TEKLİF TAMAMLANMADI** gösterir:
- açık belirsizlik = 0 (kapsam eksiklikleri dahil)
- "kontrol gerekli" satır = 0
- "belirsizlik açık" satır = 0
- onay bekleyen satır = 0
- pozu eksik kalem = 0 (B4 = "hayır" ise bu koşul aranmaz)
- fiyatı eksik kalem = 0
- fiyatı girilmiş ama tarihi veya kaynağı eksik kalem = 0
- referans doğrulaması = "REFERANSLA TUTARLI"

## Sistem sınıflaması

Her hattın sistemi, o hattın **aşağısında** kalan çıkışlara göre belirlenir:

| Aşağıdaki çıkışlar | Sistem |
|---|---|
| yalnız sprinkler | Yangın — sprinkler |
| yalnız dolap veya hidrant | Yangın — dolap/hidrant |
| her ikisi | Yangın — ortak besleme |
| hiç çıkış yok | Yangın — çıkışsız hat (belirsizlik kaydı açılır) |

## Boru

- **B1:** Her ağ hattı = 1 satır. Miktar = `uzunluk_m`, birim m. Kalem: boru serisi ve DN.
- **B2:** Düşey bileşen (`kot_farki_m`) uzunluğa dahildir ve not olarak yazılır.
- **B3:** Uzunluğu 0 olan hat metraja girmez ve belirsizlik kaydı açılır.

## Fittingler — ağ topolojisinden

Düğüm = bir hattın bitiş noktası. Gelen hat P, giden hatlar c₁…c_k.

| Kural | Durum | Sonuç | Yöntem |
|---|---|---|---|
| **K0** | k = 0 ve P bir çıkış elemanı değil | Kalem yok; "kör uç / tapa gerekebilir" belirsizliği | — |
| **R1** | k = 1 ve DN(c) ≠ DN(P) | Redüksiyon DN(P)×DN(c) | hesaplanan |
| **R1a** | k = 1 ve DN(c) > DN(P) | Ek olarak "akış yönünde çap büyüyor" belirsizliği | — |
| **R2** | k = 1 ve hidrolik girdide c için te beyan edilmiş | Kalem yok ("bu bağlantı parçası metrajda YOK"). Belirsizlik, düğüme ve c'nin satırlarına bağlanır. | — |
| **T1** | k = 2 | 1 adet **üç ağızlı te: giriş × geçiş × kol**, örneğin `FIT-TE-40x32x25`. Kol küçük çaplı çıkıştır; çaplar eşitse kol, girdide te beyan edilen çıkıştır. Geçiş giriş çapından küçükse not satırına satın alma alternatifi ("eşit te + redüksiyon") yazılır, ama bu alternatif **ayrıca sayılmaz**. | hesaplanan |
| **T4** | P'nin ucunda sprinkler var ve k = 1 (sprinkler hat ortasında) | 1 adet te DN(P)×DN(c)×½", sprinkler çıkışlı | hesaplanan |
| **E1** | P'nin ucunda sprinkler var ve k = 0 (hat ucunda sprinkler) | 1 adet "sprinkler uç bağlantısı DN(P)×½" (redüksiyonlu dirsek veya redüksiyonlu manşon)". Adet kesindir, tipi geometriye bağlı olduğu için "kalem tanımı" belirsizliği bağlanır. | hesaplanan |
| **C1** | k ≥ 3, ya da sprinkler çıkışı + 2 devam | "(k+1) yollu bağlantı" (kollektör, haç ya da ardışık te) | **kontrol gerekli** |

*Önceki sürümden değişiklik:* Eski T2 kuralı te'ye ek olarak ayrı bir redüksiyon sayıyordu; bu çift sayımdı ve kaldırıldı. Eski T3 kuralı ("eşit çaplı iki çıkışta geçiş yönü belirsiz") da kaldırıldı. Üç ağızlı tanımda iki çıkış eşit çaplı olduğundan yön, satın alınacak kalemi değiştirmez.

**Satın alma tanımı:**
- Fitting kalemlerine bağlantı yöntemi ve malzeme sınıfı eklenir: `yangin.metraj.baglanti_yontemi` (tek değer ya da `{"<=50": "dişli", ">=65": "yivli"}`) ve `yangin.metraj.fitting_malzeme`.
- Bu bilgiler tanımlı değilse tüm `FIT-` satırlarına "kalem tanımı" etkili bir belirsizlik bağlanır.

**Neden dirsek topolojiden çıkarılmıyor?** Ağ modelinde boru güzergâhının geometrisi (köşe noktaları) yok. Tek çıkışlı bir düğümün dirsek mi yoksa düz devam mı olduğu topolojiden anlaşılamaz. DXF'ten boru katmanı okunduğunda açıya bakan bir kural (D2) eklenecek.

**Çizgilerin kesişmesi bağlantı demek değildir.** DXF'ten ağ kurulurken yalnızca uç noktası çakışan ya da açıkça bağlantı bloğu olan çizgiler birleştirilecek. Kesişen ama bağlanmayan çizgiler ayrı tutulacak.

## Fittingler ve vanalar — girdideki parça listesinden

- **D1:** Hattın `parcalar` listesindeki `dirsek_90` ve `dirsek_45` adetleri, o hattın DN'inde dirsek olarak yazılır. Yöntem: **elle girilen**. Not: "Hidrolik parça listesinden; geometriyle doğrulanmadı."
- **V1:** `kelebek_vana`, `surgulu_vana`, `cekvalf` ve `alarm_vanasi` adetleri, hattın DN'inde vana olarak yazılır. Yöntem: **elle girilen**.
- `te_donus` beyanları **fiziksel te olarak sayılmaz**, çünkü te'ler T1 kuralıyla topolojiden çıkar. Bu beyanlar yalnızca R2 ve T1'de tutarlılık kontrolü için kullanılır.

## Çıkış elemanları

- **S1:** Her sprinkler = 1 adet, K faktörüne göre kalem. Yöntem hattın `konum_yontemi` alanından alınır.
  - DXF bloğundan gelmişse `ölçülen` olur.
  - Yerleşim önerisinden gelmişse `hesaplanan` olur.
  - Sprinkler tipi, sıcaklık sınıfı ve tepki süresi tanımlı değilse belirsizlik kaydı açılır.
- **S2:** Yedek sprinkler başlığı adedi `yangin.yedek_sprinkler` değerinden alınır (elle girilen; BYKHY md. 96/8 en az 6 ister). **Yalnızca başlık.**
- **S3:** Yedek sprinkler dolabı (kabin) **ayrı kalemdir**. Adet `yangin.metraj.yedek_dolap_adet` değerinden gelir. Girilmemişse tesis başına 1 alınır (varsayım, hesaplanan) ve belirsizlik bağlanır.
- **S4:** Sprinkler değiştirme anahtarı **ayrı kalemdir**. Adet `yangin.metraj.sprinkler_anahtari_adet` değerinden gelir. Girilmemişse sprinkler tipi (K) başına 1 alınır (varsayım) ve belirsizlik bağlanır.
- **O1:** Her yangın dolabı veya hidrant = 1 adet.

## Askı

- **A1 (ÖN HESAP):** Yalnızca kural tanımlıysa uygulanır: `kurallar_ek.metraj.aski_araligi_m: {DN: m}`.
  - Miktar = ⌈Σ yatay boru(DN) / aralık(DN)⌉. Kalem adı "(ÖN HESAP)" ile biter.
  - Bu kural hat uçlarını, branşman başlarını, vana ve ağırlık noktalarını ve özel (sismik) destekleri **temsil etmez**. Bu yüzden askı satırlarına **her zaman** açık bir belirsizlik bağlanır.
  - Nihai metraj için hat bazında askı yerleşimi gerekir.
- Kural tanımlı değilse askı **hesaplanmaz** ve belirsizlik kaydı açılır. Varsayılan bir aralık bilerek konmamıştır: aralık şartnameye ve firma uygulamasına göre değişir.

## Kapsam dışı (belirsizlik olarak listelenir)

İşçilik, boya ve korozyon koruması, pompa grubu, depo, alarm ve izleme ekipmanı.

## Doğrulama

- **İç tutarlılık:** Şu değerler metraj ile ağ modeli arasında karşılaştırılır:
  - Σ boru uzunluğu
  - sprinkler adedi
  - dolap ve hidrant adedi

  Karşılaştırma Excel formülleriyle yapılır.
- **Referans karşılaştırması:** `--referans` ile kontrol edilmiş bir metraj (CSV: `kalem_kodu,miktar`) verilirse kalem bazında fark hesaplanır. Tolerans: uzunlukta %2, adette tam eşitlik.
- **Referans verilmezse** Doğrulama sayfası açıkça **"DOĞRULANMADI — referans metraj yok"** yazar.

## DXF'ten ağ (boru_agi.py)

- **G1:** Boru, boru katmanındaki LINE, LWPOLYLINE ve POLYLINE parçalarıdır. Yaylar kirişle yaklaşıklanır.
- **G2:** Bağlantı yalnızca iki durumda kurulur:
  - Uç noktalar birleştirme toleransı içindeyse.
  - Bir parçanın **ucu** başka bir parçanın **gövdesi** üzerindeyse. Bu bir T bağlantısıdır ve gövde o noktada bölünür.

  **İki gövdenin kesişmesi bağlantı değildir** (borunun üstünden ya da altından geçiş). Bu durum belirsizlik olarak raporlanır.
- **G3:** Sprinkler bloğu en yakın boruya bağlanır (tolerans içinde). Bağlanamayan sprinkler raporlanır.
- **G4:** Çap etiketi, en yakın boru parçasına atanır.
  - Etiketsiz parçaya, düz devam eden bir düğüm üzerinden (yalnızca 2 bağlantılı ve sprinklersiz düğümler) komşu parçanın çapı yayılır.
  - Hâlâ etiketsiz kalan parçaya, beslediği sprinkler sayısından çap **önerilir**. Bu öneri "kalem tanımı" belirsizliği olarak işaretlenir.
- **G5:** Kaynak düğümünden ağaç kurulur. Döngü varsa hata verilir. Kaynağa bağlı olmayan parçalar ağ dışında bırakılır ve raporlanır.
- **D2:** 2 bağlantılı ara düğümde yön değişimi 67,5° ve üzerindeyse 90° dirsek, 22,5° ile 67,5° arasındaysa 45° dirsek sayılır.
- **T5:** Dallanmada, gelen yönden 45° ve üzeri sapan çıkışa hidrolik "te dönüş" kaybı eklenir.

## Yivli kaplin (K1, ÖN HESAP)

- Yivli bağlantılı her parça ve vana **ağzı** için 1 kaplin sayılır. Ağız çapı yivli aralıkta değilse sayılmaz; örneğin dişli 2" ağızlı bir çaprazın yalnızca DN65 ağzı sayılır.
- Bunlara boru boy ekleri eklenir: ⌈boy / 6 m⌉ − 1.
- İki parçanın ortak bağlantı uçları ayırt edilmediği için sonuç **üst sınırdır**. Bu yüzden satıra her zaman belirsizlik bağlanır.

## Ek kalemler

Ağdan türetilmeyen kalemler (heat plate, zon ekipmanı, platform, test vb.) proje ayarındaki `ek_kalemler` listesinden gelir.
- Miktar bir sayı ya da `sprinkler`, `kat`, `boru_m` olabilir (× çarpan).
- Sayı girilmişse yöntem "elle girilen", diğerlerinde "hesaplanan" olur.
