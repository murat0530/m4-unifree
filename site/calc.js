// Hesaplama çekirdeği: ekrandan bağımsız, saf fonksiyonlar (tests/ altında test edilir).
// Para tutarları kuruş/cent cinsinden tamsayı olarak tutulur; kayan nokta hatası olmasın.

export const CURRENCIES = {
  TRY: { symbol: '₺', name: 'Türk lirası' },
  EUR: { symbol: '€', name: 'Euro' },
  USD: { symbol: '$', name: 'ABD doları' },
  GBP: { symbol: '£', name: 'Sterlin' },
  CNY: { symbol: '¥', name: 'Çin yuanı' },
  CAD: { symbol: 'C$', name: 'Kanada doları' },
  SAR: { symbol: 'SAR', name: 'Suudi riyali' },
};

// "1.234,56" / "1234.56" / "12,5" -> 123456 / 123456 / 1250 (cent). Geçersizse null.
export function parseAmount(text) {
  if (text == null) return null;
  let s = String(text).trim().replace(/\s/g, '');
  if (!s) return null;
  const lastComma = s.lastIndexOf(',');
  const lastDot = s.lastIndexOf('.');
  if (lastComma > -1 && lastDot > -1) {
    // Hangisi sondaysa ondalık ayırıcı odur, diğeri binlik ayırıcıdır.
    const dec = lastComma > lastDot ? ',' : '.';
    const thou = dec === ',' ? '.' : ',';
    s = s.split(thou).join('').replace(dec, '.');
  } else if (lastComma > -1) {
    s = s.replace(',', '.');
  } else if (/^\d{1,3}(\.\d{3})+$/.test(s)) {
    // Yalnızca nokta ve hep 3'lü gruplar: Türkçe binlik ayırıcı ("1.000", "12.500.000")
    s = s.split('.').join('');
  }
  if (!/^\d+(\.\d{0,2})?$/.test(s)) return null;
  const [whole, frac = ''] = s.split('.');
  return Number(whole) * 100 + Number((frac + '00').slice(0, 2));
}

// Kur: "1 birim = n TL". Metin olarak 4 ondalığa kadar kabul edilir.
export function parseRate(text) {
  if (text == null) return null;
  const s = String(text).trim().replace(/\s/g, '').replace(',', '.');
  if (!/^\d+(\.\d{1,4})?$/.test(s)) return null;
  const v = Number(s);
  return v > 0 ? v : null;
}

export function formatAmount(cents, currency) {
  const sign = cents < 0 ? '-' : '';
  const abs = Math.abs(cents);
  const whole = Math.floor(abs / 100).toString().replace(/\B(?=(\d{3})+(?!\d))/g, '.');
  const frac = String(abs % 100).padStart(2, '0');
  const sym = currency ? ' ' + CURRENCIES[currency].symbol : '';
  return `${sign}${whole},${frac}${sym}`;
}

// Kur yapısı (euro bazlı): { eurTry: 50, parity: { USD: 1.17, GBP: 0.86, CNY: 8.3, … } }
//   1 € = eurTry ₺,  1 € = parity[X] X
// perEur: 1 euro kaç birim eder (EUR = 1, TRY = eurTry, diğerleri parite)
export function perEur(cur, rates) {
  const v = cur === 'EUR' ? 1 : cur === 'TRY' ? rates.eurTry : rates.parity?.[cur];
  if (!(v > 0)) throw new Error(cur === 'TRY' ? 'Euro kuru girilmemiş' : `${cur} paritesi girilmemiş`);
  return v;
}

// Tutarı (kuruş/cent) bir para biriminden diğerine euro üzerinden çevirir, en yakın kuruşa yuvarlar.
export function convert(cents, from, to, rates) {
  const v = (cents / perEur(from, rates)) * perEur(to, rates);
  return Math.round(v + 1e-9);
}

// Ekranda gösterilecek hesap adımları: ["÷ 1,17", "× 50"]
export function convertSteps(from, to, rates) {
  const fmt = (n) => n.toLocaleString('tr-TR', { maximumFractionDigits: 4 });
  const steps = [];
  if (from !== 'EUR') steps.push(`÷ ${fmt(perEur(from, rates))}`);
  if (to !== 'EUR') steps.push(`× ${fmt(perEur(to, rates))}`);
  return steps;
}

// --- İndirim / kampanya ---

export function percentOff(priceCents, percent) {
  const discount = Math.round((priceCents * percent) / 100);
  return { discount, total: priceCents - discount };
}

// "N al M öde": her N ürünlük grupta en ucuz (N-M) ürün bedava.
// Fiyatlar pahalıdan ucuza sıralanıp gruplanır (mağazaların yaygın uygulaması).
export function buyNPayM(prices, n, m) {
  if (!(n > m && m >= 0)) throw new Error('Geçersiz kampanya');
  const sorted = [...prices].sort((a, b) => b - a);
  const gross = sorted.reduce((s, p) => s + p, 0);
  let discount = 0;
  for (let i = 0; i + n <= sorted.length; i += n) {
    const group = sorted.slice(i, i + n);
    discount += group.slice(m).reduce((s, p) => s + p, 0);
  }
  return { gross, discount, total: gross - discount };
}

// "İkinci ürüne %X": pahalıdan ucuza sıralanır, her çiftin ucuz olanına indirim.
export function secondItemOff(prices, percent) {
  const sorted = [...prices].sort((a, b) => b - a);
  const gross = sorted.reduce((s, p) => s + p, 0);
  let discount = 0;
  for (let i = 1; i < sorted.length; i += 2) discount += Math.round((sorted[i] * percent) / 100);
  return { gross, discount, total: gross - discount };
}

