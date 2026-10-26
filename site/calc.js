// Hesaplama çekirdeği: ekrandan bağımsız, saf fonksiyonlar (tests/ altında test edilir).
// Para tutarları kuruş/cent cinsinden tamsayı olarak tutulur; kayan nokta hatası olmasın.

export const CURRENCIES = {
  TRY: { symbol: '₺', name: 'Türk lirası', denoms: [20000, 10000, 5000, 2000, 1000, 500, 100, 50, 25, 10, 5] },
  EUR: { symbol: '€', name: 'Euro', denoms: [50000, 20000, 10000, 5000, 2000, 1000, 500, 200, 100, 50, 20, 10, 5, 2, 1] },
  USD: { symbol: '$', name: 'ABD doları', denoms: [10000, 5000, 2000, 1000, 500, 200, 100, 25, 10, 5, 1] },
  GBP: { symbol: '£', name: 'Sterlin', denoms: [5000, 2000, 1000, 500, 200, 100, 50, 20, 10, 5, 2, 1] },
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

// rates: { EUR: 38.5, USD: 35.2, ... } (TRY her zaman 1)
function rateOf(rates, cur) {
  if (cur === 'TRY') return 1;
  const r = rates[cur];
  if (!(r > 0)) throw new Error(`${cur} kuru girilmemiş`);
  return r;
}

// Tutarı TL kuruşa çevirir (tam değer, yuvarlamasız).
export function toTry(cents, cur, rates) {
  return cents * rateOf(rates, cur);
}

// TL kuruştan hedef para birimine. mode: 'up' (müşterinin ödeyeceği) | 'down' (verilecek para üstü)
export function fromTry(tryCents, cur, rates, mode) {
  const v = tryCents / rateOf(rates, cur);
  const eps = 1e-6; // 12.000000001 gibi kayan nokta artıklarını yutar
  return mode === 'up' ? Math.ceil(v - eps) : Math.floor(v + eps);
}

// Satış: { amount, currency }, ödemeler: [{ amount, currency }]
// Döner: { status: 'remaining' | 'change' | 'exact', tryDiff, perCurrency: { CUR: cents } }
// remaining: müşterinin her para biriminde ödemesi gereken kalan (yukarı yuvarlanır)
// change: her para biriminde verilecek para üstü (aşağı yuvarlanır, fazla verilmez)
export function settle(sale, payments, rates, currencies = Object.keys(CURRENCIES)) {
  const due = toTry(sale.amount, sale.currency, rates);
  const paid = payments.reduce((sum, p) => sum + toTry(p.amount, p.currency, rates), 0);
  const diff = paid - due;
  const perCurrency = {};
  // Yarım kuruştan küçük farkları tam ödeme say.
  if (Math.abs(diff) < 0.5) {
    for (const c of currencies) perCurrency[c] = 0;
    return { status: 'exact', tryDiff: 0, perCurrency };
  }
  const status = diff < 0 ? 'remaining' : 'change';
  for (const c of currencies) {
    if (c !== 'TRY' && !(rates[c] > 0)) continue;
    perCurrency[c] = fromTry(Math.abs(diff), c, rates, status === 'remaining' ? 'up' : 'down');
  }
  return { status, tryDiff: diff, perCurrency };
}

// Para üstünü küpürlere böler (açgözlü). Kalan küsurat 'rest' olarak döner.
export function breakdown(cents, currency) {
  const out = [];
  let rest = cents;
  for (const d of CURRENCIES[currency].denoms) {
    const n = Math.floor(rest / d);
    if (n > 0) {
      out.push({ denom: d, count: n });
      rest -= n * d;
    }
  }
  return { parts: out, rest };
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
