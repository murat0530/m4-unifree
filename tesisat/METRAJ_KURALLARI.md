# Metraj Kuralları — Yangın Tesisatı

Bu belge `tesisat/metraj.py` dosyasının uyguladığı kuralların tamamıdır. Kodda bir kural değişirse bu belge de aynı commit'te güncellenmelidir.

## Temel ilkeler

1. **Miktar ile fiyat ayrıdır.** Metraj motoru yalnızca miktar üretir. Poz numarası ve birim fiyat Excel'in **Fiyatlar** sayfasında kullanıcı tarafından girilir. **Motor poz numarası üretmez veya tahmin etmez.** Pozu girilmemiş kalem keşifte "POZ YOK" olarak görünür.
2. **Her satır izlenebilir.** Her satırda şu bilgiler bulunur:
   - kaynak nesne (ağ hattı ya da düğüm)
   - sistem, kat, birim, miktar
   - **çıkarım yöntemi**
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
| **R2** | k = 1 ve hidrolik girdide c için te beyan edilmiş | Kalem yok; "uç bağlantı: dirsek mi, te + tapa mı?" belirsizliği | — |
| **T1** | k = 2 | 1 adet te DN(P)×DN(kol). **Kol = küçük çaplı çıkış.** Çaplar eşitse kol, girdide te beyan edilen çıkıştır. | hesaplanan |
| **T2** | k = 2 ve DN(geçiş) ≠ DN(P) | Ek olarak redüksiyon DN(P)×DN(geçiş). Redüksiyonlu te olarak da temin edilebilir. | hesaplanan |
| **T3** | k = 2, iki çıkış eşit çaplı ve DN(P)'den küçük | Geçiş yönü belirlenemez; belirsizlik kaydı | — |
| **C1** | k ≥ 3 | "(k+1) yollu bağlantı" (kollektör, haç ya da ardışık te) | **kontrol gerekli** |

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
- **S2:** Yedek sprinkler adedi `yangin.yedek_sprinkler` değerinden alınır (elle girilen; BYKHY md. 96/8 en az 6 ister).
- **O1:** Her yangın dolabı veya hidrant = 1 adet.

## Askı

- **A1:** Yalnızca kural tanımlıysa uygulanır: `kurallar_ek.metraj.aski_araligi_m: {DN: m}`.
  - Miktar = ⌈Σ yatay boru(DN) / aralık(DN)⌉.
  - Yöntem: **hesaplanan**. Not satırında kuralın kendisi yazılır.
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
