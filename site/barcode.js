// Barkod kodlayıcı: EAN-13, EAN-8 ve Code 128. Çıktı, "1" = siyah modül olan bir modül dizisidir.

const EAN_L = ['0001101', '0011001', '0010011', '0111101', '0100011', '0110001', '0101111', '0111011', '0110111', '0001011'];
const EAN_R = EAN_L.map((p) => [...p].map((b) => (b === '1' ? '0' : '1')).join(''));
const EAN_G = EAN_R.map((p) => [...p].reverse().join(''));
// EAN-13'te ilk hane, sol yarıdaki L/G sırasını belirler
const EAN13_PARITY = ['LLLLLL', 'LLGLGG', 'LLGGLG', 'LLGGGL', 'LGLLGG', 'LGGLLG', 'LGGGLL', 'LGLGLG', 'LGLGGL', 'LGGLGL'];

// Sağdan sola 3,1,3,1 ağırlıklı kontrol hanesi (EAN-8 ve EAN-13 için aynı)
export function eanCheckDigit(body) {
  let sum = 0;
  for (let i = body.length - 1, w = 3; i >= 0; i--, w = 4 - w) sum += Number(body[i]) * w;
  return String((10 - (sum % 10)) % 10);
}

export function encodeEAN(digits) {
  if (!/^\d+$/.test(digits) || ![7, 8, 12, 13].includes(digits.length)) {
    throw new Error('EAN için 8 veya 13 hane gerekli');
  }
  const full = digits.length === 7 || digits.length === 12 ? digits + eanCheckDigit(digits) : digits;
  if (eanCheckDigit(full.slice(0, -1)) !== full.slice(-1)) {
    throw new Error(`Kontrol hanesi hatalı: son hane ${eanCheckDigit(full.slice(0, -1))} olmalı`);
  }
  let left, right;
  if (full.length === 13) {
    const parity = EAN13_PARITY[Number(full[0])];
    left = [...full.slice(1, 7)].map((d, i) => (parity[i] === 'L' ? EAN_L : EAN_G)[d]).join('');
    right = [...full.slice(7)].map((d) => EAN_R[d]).join('');
  } else {
    left = [...full.slice(0, 4)].map((d) => EAN_L[d]).join('');
    right = [...full.slice(4)].map((d) => EAN_R[d]).join('');
  }
  return { type: full.length === 13 ? 'EAN-13' : 'EAN-8', text: full, modules: '101' + left + '01010' + right + '101' };
}

// Code 128 desenleri: her değer için çubuk/boşluk genişlikleri (0-106; 106 = Stop)
const C128 = (
  '212222 222122 222221 121223 121322 131222 122213 122312 132212 221213 '
  + '221312 231212 112232 122132 122231 113222 123122 123221 223211 221132 '
  + '221231 213212 223112 312131 311222 321122 321221 312212 322112 322211 '
  + '212123 212321 232121 111323 131123 131321 112313 132113 132311 211313 '
  + '231113 231311 112133 112331 132131 113123 113321 133121 313121 211331 '
  + '231131 213113 213311 213131 311123 311321 331121 312113 312311 332111 '
  + '314111 221411 431111 111224 111422 121124 121421 141122 141221 112214 '
  + '112412 122114 122411 142112 142211 241211 221114 413111 241112 134111 '
  + '111242 121142 121241 114212 124112 124211 411212 421112 421211 212141 '
  + '214121 412121 111143 111341 131141 114113 114311 411113 411311 113141 '
  + '114131 311141 411131 211412 211214 211232 2331112'
).split(' ');
export const C128_PATTERNS = C128;
const START_B = 104, START_C = 105, CODE_B = 100, STOP = 106;

function widthsToModules(widths) {
  let out = '';
  [...widths].forEach((w, i) => { out += (i % 2 === 0 ? '1' : '0').repeat(Number(w)); });
  return out;
}

// Yalnızca rakamsa çift haneleri Code C ile sıkıştırır; aksi halde Code B (ASCII 32-126).
export function encodeCode128(text) {
  if (!text) throw new Error('Kod boş');
  if (text.length > 48) throw new Error('Kod çok uzun (en fazla 48 karakter)');
  const values = [];
  if (/^\d+$/.test(text) && text.length >= 2) {
    values.push(START_C);
    const even = text.length - (text.length % 2);
    for (let i = 0; i < even; i += 2) values.push(Number(text.slice(i, i + 2)));
    if (even < text.length) values.push(CODE_B, text.charCodeAt(even) - 32);
  } else {
    values.push(START_B);
    for (const ch of text) {
      const c = ch.charCodeAt(0);
      if (c < 32 || c > 126) throw new Error(`"${ch}" karakteri barkoda yazılamaz (Türkçe harf kullanmayın)`);
      values.push(c - 32);
    }
  }
  const check = values.reduce((s, v, i) => s + v * (i === 0 ? 1 : i), 0) % 103;
  values.push(check, STOP);
  return { type: 'Code 128', text, modules: values.map((v) => widthsToModules(C128[v])).join('') };
}

// Girdiye göre türü seçer: 8/13 haneli (veya kontrol hanesiz 7/12) rakam -> EAN, diğerleri -> Code 128
export function autoEncode(input) {
  const s = String(input).trim();
  if (/^\d+$/.test(s) && [7, 8, 12, 13].includes(s.length)) return encodeEAN(s);
  return encodeCode128(s);
}
