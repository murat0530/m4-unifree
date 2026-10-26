import {
  CURRENCIES, parseAmount, parseRate, formatAmount, settle, breakdown,
  percentOff, buyNPayM, secondItemOff,
} from './calc.js';
import { autoEncode } from './barcode.js';

const $ = (id) => document.getElementById(id);
const CODES = Object.keys(CURRENCIES);
const FOREIGN = CODES.filter((c) => c !== 'TRY');
const TABS = ['doviz', 'indirim', 'barkod', 'kurallar', 'ifadeler'];

// --- Yerel kayıt (yalnızca bu cihazda; erişilemezse sessizce varsayılana döner) ---
const STORE_KEY = 'm4kasa';
const state = Object.assign(
  { codes: [], rates: {}, ratesAt: null, saleCur: 'EUR', changeCur: 'TRY', tab: 'doviz', lang: 'en', discCur: 'EUR' },
  load(),
);
function load() {
  try { return JSON.parse(localStorage.getItem(STORE_KEY)) || {}; } catch { return {}; }
}
function save() {
  try { localStorage.setItem(STORE_KEY, JSON.stringify(state)); } catch { /* özel sekme vb. */ }
}

// DOM yardımcısı: içerik her zaman textContent ile basılır (HTML enjeksiyonu yok).
function el(tag, props = {}, children = []) {
  const n = document.createElement(tag);
  for (const [k, v] of Object.entries(props)) {
    if (v === undefined) continue;
    if (k === 'class') n.className = v;
    else if (k === 'text') n.textContent = v;
    else if (k.startsWith('on')) n.addEventListener(k.slice(2), v);
    else n.setAttribute(k, v);
  }
  for (const c of [].concat(children)) if (c != null) n.append(c);
  return n;
}
function curOptions(select, selected, codes = CODES) {
  select.replaceChildren(...codes.map((c) =>
    el('option', { value: c, text: `${CURRENCIES[c].symbol} ${c}` })));
  select.value = selected;
}
async function loadJson(path) {
  try {
    const r = await fetch(path, { cache: 'no-cache' });
    if (!r.ok) throw new Error(r.status);
    return await r.json();
  } catch { return null; }
}

// --- Sekmeler ---
function showTab(name) {
  if (!TABS.includes(name)) name = state.tab || 'doviz';
  for (const t of TABS) $('tab-' + t).hidden = t !== name;
  document.querySelectorAll('.tabs a').forEach((a) => a.classList.toggle('on', a.dataset.tab === name));
  state.tab = name;
  save();
}
window.addEventListener('hashchange', () => showTab(location.hash.slice(1)));

// --- Kur çubuğu ve ayarlar ---
function hasRates() { return FOREIGN.some((c) => state.rates[c] > 0); }
function renderRateBar() {
  const bar = $('rateBar');
  if (!hasRates()) {
    bar.textContent = '⚠ Kur girilmedi, dokunun';
    bar.classList.add('missing');
    return;
  }
  bar.classList.remove('missing');
  const parts = FOREIGN.filter((c) => state.rates[c] > 0)
    .map((c) => `${CURRENCIES[c].symbol} ${state.rates[c].toLocaleString('tr-TR', { maximumFractionDigits: 4 })}`);
  let when = '';
  if (state.ratesAt) {
    const d = new Date(state.ratesAt);
    const today = new Date().toDateString() === d.toDateString();
    when = ' · ' + (today ? '' : d.toLocaleDateString('tr-TR', { day: '2-digit', month: '2-digit' }) + ' ')
      + d.toLocaleTimeString('tr-TR', { hour: '2-digit', minute: '2-digit' });
    if (!today) bar.classList.add('missing'); // eski kur uyarısı
  }
  bar.textContent = parts.join(' · ') + when;
}
function openSettings() {
  $('rateInputs').replaceChildren(...FOREIGN.map((c) => el('div', { class: 'rate-row' }, [
    el('label', { for: 'rate-' + c, text: `1 ${CURRENCIES[c].symbol} ${c} =` }),
    el('input', {
      id: 'rate-' + c, class: 'num', inputmode: 'decimal', autocomplete: 'off', placeholder: '0,0000',
      value: state.rates[c] ? String(state.rates[c]).replace('.', ',') : '',
    }),
    el('span', { text: '₺' }),
  ])));
  $('rateError').hidden = true;
  $('settingsOverlay').hidden = false;
}
function saveRates() {
  const next = {};
  for (const c of FOREIGN) {
    const raw = $('rate-' + c).value;
    if (!raw.trim()) continue;
    const v = parseRate(raw);
    if (v == null) {
      $('rateError').textContent = `${c} kuru geçersiz. Örnek: 38,5 veya 38,1234`;
      $('rateError').hidden = false;
      return;
    }
    next[c] = v;
  }
  state.rates = next;
  state.ratesAt = Date.now();
  save();
  $('settingsOverlay').hidden = true;
  renderRateBar();
  renderDoviz();
}
$('rateBar').addEventListener('click', openSettings);
$('openSettings').addEventListener('click', openSettings);
$('closeSettings').addEventListener('click', () => { $('settingsOverlay').hidden = true; });
$('settingsOverlay').addEventListener('click', (e) => { if (e.target === e.currentTarget) e.currentTarget.hidden = true; });
$('saveRates').addEventListener('click', saveRates);

// --- Döviz ve para üstü ---
function addPaymentRow(cur = state.saleCur, amount = '') {
  const input = el('input', { class: 'num', inputmode: 'decimal', autocomplete: 'off', placeholder: 'Ödenen', 'aria-label': 'Ödenen tutar' });
  input.value = amount;
  const select = el('select', { class: 'cur-select', 'aria-label': 'Ödeme para birimi' });
  curOptions(select, cur);
  const row = el('div', { class: 'pay-row' }, [input, select]);
  if ($('payments').children.length > 0) {
    row.append(el('button', {
      class: 'del-btn', type: 'button', 'aria-label': 'Ödemeyi sil', text: '✕',
      onclick: () => { row.remove(); renderDoviz(); },
    }));
  }
  input.addEventListener('input', renderDoviz);
  select.addEventListener('change', renderDoviz);
  $('payments').append(row);
  return input;
}

let lastSettle = null; // "Müşteriye göster" için
function renderDoviz() {
  const box = $('result');
  box.className = 'result';
  lastSettle = null;
  const sale = parseAmount($('saleAmt').value);
  if (sale == null) { box.replaceChildren(); return; }
  if (!hasRates() && state.saleCur !== 'TRY') {
    box.replaceChildren(el('div', { class: 'warn-text', text: 'Önce kurları girin (üstteki çubuğa dokunun).' }));
    return;
  }
  const payments = [];
  let invalid = false;
  for (const row of $('payments').children) {
    const [input, select] = row.querySelectorAll('input, select');
    if (!input.value.trim()) continue;
    const a = parseAmount(input.value);
    if (a == null) { invalid = true; continue; }
    payments.push({ amount: a, currency: select.value });
  }
  const saleObj = { amount: sale, currency: state.saleCur };

  let r;
  try {
    r = settle(saleObj, payments, state.rates);
  } catch (e) {
    box.replaceChildren(el('div', { class: 'warn-text', text: e.message + '. Kurlara dokunup ekleyin.' }));
    return;
  }
  lastSettle = { sale: saleObj, payments, result: r };

  const children = [];
  if (payments.length === 0) {
    // Ödeme yoksa: satış tutarının diğer para birimlerindeki karşılığı
    box.classList.add('remaining');
    children.push(el('div', { class: 'head', text: 'TOPLAM' }));
    children.push(el('div', { class: 'main', text: formatAmount(sale, state.saleCur) }));
    children.push(altsRow(r.perCurrency, state.saleCur));
  } else if (r.status === 'exact') {
    box.classList.add('exact');
    children.push(el('div', { class: 'head', text: 'TAM ÖDENDİ' }));
    children.push(el('div', { class: 'main', text: '✓ Para üstü yok' }));
  } else if (r.status === 'remaining') {
    box.classList.add('remaining');
    const main = r.perCurrency[state.saleCur] ?? r.perCurrency.TRY;
    const mainCur = state.saleCur in r.perCurrency ? state.saleCur : 'TRY';
    children.push(el('div', { class: 'head', text: 'KALAN ÖDEME' }));
    children.push(el('div', { class: 'main', text: formatAmount(main, mainCur) }));
    children.push(altsRow(r.perCurrency, mainCur));
  } else {
    box.classList.add('change');
    if (!(state.changeCur in r.perCurrency)) state.changeCur = 'TRY';
    const c = state.changeCur;
    children.push(el('div', { class: 'head', text: 'PARA ÜSTÜ' }));
    children.push(el('div', { class: 'main', text: formatAmount(r.perCurrency[c], c) }));
    children.push(altsRow(r.perCurrency, c, true));
    const b = breakdown(r.perCurrency[c], c);
    if (b.parts.length) {
      children.push(el('div', { class: 'breakdown' }, b.parts.map((p) =>
        el('span', { class: 'denom', text: `${p.count} × ${formatAmount(p.denom, c)}` }))));
    }
    if (b.rest > 0) children.push(el('div', { class: 'sub', text: `Küsurat: ${formatAmount(b.rest, c)} (bozuk para yok)` }));
  }
  if (invalid) children.push(el('div', { class: 'sub warn-text', text: 'Geçersiz bir ödeme tutarı yok sayıldı.' }));
  box.replaceChildren(...children);
}
// Diğer para birimlerindeki karşılıklar; para üstünde dokunulan birim seçilir.
function altsRow(per, current, selectable = false) {
  return el('div', { class: 'alts' }, Object.entries(per)
    .filter(([c]) => c !== current || selectable)
    .map(([c, v]) => el(selectable ? 'button' : 'span', {
      class: 'alt' + (c === current ? ' on' : ''),
      type: selectable ? 'button' : undefined,
      text: formatAmount(v, c),
      onclick: selectable ? () => { state.changeCur = c; save(); renderDoviz(); } : undefined,
    })));
}

function resetDoviz() {
  $('saleAmt').value = '';
  $('payments').replaceChildren();
  addPaymentRow();
  renderDoviz();
}
curOptions($('saleCur'), state.saleCur);
$('saleCur').addEventListener('change', (e) => {
  state.saleCur = e.target.value;
  save();
  // Tek ödeme satırı varsa ve boşsa onun da birimini eşitle
  const rows = $('payments').children;
  if (rows.length === 1 && !rows[0].querySelector('input').value) rows[0].querySelector('select').value = state.saleCur;
  renderDoviz();
});
$('saleAmt').addEventListener('input', renderDoviz);
$('addPay').addEventListener('click', () => addPaymentRow('TRY').focus());
$('clearSale').addEventListener('click', () => { resetDoviz(); $('saleAmt').focus(); });

// --- Müşteriye göster ---
function showOverlay(nodes, dir = 'auto') {
  const body = $('showBody');
  body.setAttribute('dir', dir);
  body.replaceChildren(...nodes);
  $('showOverlay').hidden = false;
}
$('showOverlay').addEventListener('click', () => {
  $('showOverlay').hidden = true;
  wakeLock?.release().catch(() => {});
  wakeLock = null;
});
$('showCustomer').addEventListener('click', () => {
  if (!lastSettle) return;
  const { sale, payments, result: r } = lastSettle;
  const nodes = [el('div', { class: 'lab', text: 'TOTAL · TOPLAM' }), el('div', { class: 'money', text: formatAmount(sale.amount, sale.currency) })];
  if (payments.length && r.status === 'change') {
    nodes.push(el('div', { class: 'lab', text: 'CHANGE · PARA ÜSTÜ' }));
    nodes.push(el('div', { class: 'money', text: formatAmount(r.perCurrency[state.changeCur], state.changeCur) }));
  } else if (payments.length && r.status === 'remaining') {
    const c = state.saleCur in r.perCurrency ? state.saleCur : 'TRY';
    nodes.push(el('div', { class: 'lab', text: 'REMAINING · KALAN' }));
    nodes.push(el('div', { class: 'money', text: formatAmount(r.perCurrency[c], c) }));
  }
  showOverlay(nodes, 'ltr');
});

// --- İndirim ---
let campaigns = [];
function addPriceRow(value = '') {
  const input = el('input', { class: 'num', inputmode: 'decimal', autocomplete: 'off', placeholder: 'Fiyat', 'aria-label': 'Ürün fiyatı' });
  input.value = value;
  const row = el('div', { class: 'pay-row' }, [input, el('button', {
    class: 'del-btn', type: 'button', 'aria-label': 'Ürünü sil', text: '✕',
    onclick: () => { row.remove(); if (!$('prices').children.length) addPriceRow(); renderIndirim(); },
  })]);
  input.addEventListener('input', renderIndirim);
  $('prices').append(row);
  return input;
}
function syncParams() {
  const m = $('discMode').value;
  $('paramN').hidden = m !== 'nAlMOde';
  $('paramM').hidden = m !== 'nAlMOde';
  $('paramP').hidden = m === 'nAlMOde';
}
let lastDiscTotal = null;
function renderIndirim() {
  syncParams();
  const box = $('discResult');
  box.className = 'result';
  lastDiscTotal = null;
  const prices = [...$('prices').querySelectorAll('input')].map((i) => parseAmount(i.value)).filter((v) => v != null);
  if (!prices.length) { box.replaceChildren(); return; }
  const cur = state.discCur;
  const mode = $('discMode').value;
  let r;
  try {
    if (mode === 'yuzde' || mode === 'ikinciye') {
      const p = Number($('discP').value.replace(',', '.'));
      if (!(p >= 0 && p <= 100)) throw new Error('Yüzde 0-100 arasında olmalı');
      if (mode === 'yuzde') {
        const gross = prices.reduce((s, x) => s + x, 0);
        r = { gross, ...percentOff(gross, p) };
      } else {
        r = secondItemOff(prices, p);
      }
    } else {
      const n = parseInt($('discN').value, 10);
      const m = parseInt($('discM').value, 10);
      if (!(n > m && m >= 0)) throw new Error('N, M\'den büyük olmalı (ör. 3 al 2 öde)');
      r = buyNPayM(prices, n, m);
      if (prices.length < n) r.note = `Kampanya için en az ${n} ürün gerekli.`;
    }
  } catch (e) {
    box.replaceChildren(el('div', { class: 'warn-text', text: e.message }));
    return;
  }
  lastDiscTotal = { amount: r.total, currency: cur };
  box.classList.add('change');
  box.replaceChildren(
    el('div', { class: 'line' }, [el('span', { text: `${prices.length} ürün` }), el('span', { text: formatAmount(r.gross, cur) })]),
    el('div', { class: 'line' }, [el('span', { text: 'İndirim' }), el('span', { text: '− ' + formatAmount(r.discount, cur) })]),
    el('div', { class: 'line total' }, [el('span', { text: 'Ödenecek' }), el('span', { text: formatAmount(r.total, cur) })]),
    ...(r.note ? [el('div', { class: 'sub warn-text', text: r.note })] : []),
  );
}
function renderCampaignChips() {
  $('campaignChips').replaceChildren(...campaigns.map((k) => el('button', {
    class: 'chip', type: 'button', text: k.ad,
    onclick: (e) => {
      $('discMode').value = k.tip;
      if (k.tip === 'nAlMOde') { $('discN').value = k.n; $('discM').value = k.m; }
      else $('discP').value = k.oran;
      document.querySelectorAll('#campaignChips .chip').forEach((c) => c.classList.remove('on'));
      e.currentTarget.classList.add('on');
      renderIndirim();
    },
  })));
}
curOptions($('discCur'), state.discCur);
$('discCur').addEventListener('change', (e) => { state.discCur = e.target.value; save(); renderIndirim(); });
['discMode', 'discN', 'discM', 'discP'].forEach((id) => $(id).addEventListener('input', () => {
  document.querySelectorAll('#campaignChips .chip').forEach((c) => c.classList.remove('on'));
  renderIndirim();
}));
$('addPrice').addEventListener('click', () => addPriceRow().focus());
$('clearDisc').addEventListener('click', () => { $('prices').replaceChildren(); addPriceRow(); renderIndirim(); });
$('toDoviz').addEventListener('click', () => {
  if (!lastDiscTotal) return;
  state.saleCur = lastDiscTotal.currency;
  $('saleCur').value = state.saleCur;
  resetDoviz();
  $('saleAmt').value = formatAmount(lastDiscTotal.amount);
  $('payments').querySelector('select').value = state.saleCur;
  renderDoviz();
  location.hash = 'doviz';
});

// --- Barkod ---
const SVG_NS = 'http://www.w3.org/2000/svg';
const QUIET = 12; // her iki yanda boş modül (okuyucunun kenarı bulması için)
// Modül genişliği tam piksel olsun diye genişlik, sığan en büyük tam sayıya göre seçilir
function barcodeSvg(modules, maxWidth, height) {
  const total = modules.length + QUIET * 2;
  const unit = Math.max(1, Math.floor(maxWidth / total));
  const svg = document.createElementNS(SVG_NS, 'svg');
  svg.setAttribute('viewBox', `0 0 ${total} 1`);
  svg.setAttribute('width', total * unit);
  svg.setAttribute('height', height);
  svg.setAttribute('preserveAspectRatio', 'none');
  svg.setAttribute('shape-rendering', 'crispEdges');
  svg.setAttribute('role', 'img');
  const bg = document.createElementNS(SVG_NS, 'rect');
  bg.setAttribute('width', total); bg.setAttribute('height', 1); bg.setAttribute('fill', '#fff');
  svg.append(bg);
  for (let i = 0; i < modules.length;) {
    if (modules[i] !== '1') { i++; continue; }
    let j = i;
    while (modules[j] === '1') j++;
    const r = document.createElementNS(SVG_NS, 'rect');
    r.setAttribute('x', QUIET + i); r.setAttribute('width', j - i);
    r.setAttribute('height', 1); r.setAttribute('fill', '#000');
    svg.append(r);
    i = j;
  }
  return svg;
}
let currentCode = null;
function renderBarcode() {
  const out = $('codeOut');
  const raw = $('codeInput').value.trim();
  currentCode = null;
  out.className = 'code-out';
  if (!raw) { out.replaceChildren(); return; }
  try {
    currentCode = autoEncode(raw);
  } catch (e) {
    out.classList.add('error');
    out.replaceChildren(el('div', { text: e.message }));
    return;
  }
  const svg = barcodeSvg(currentCode.modules, out.clientWidth || 340, 120);
  svg.setAttribute('aria-label', `${currentCode.type} barkod: ${currentCode.text}`);
  out.replaceChildren(svg,
    el('div', { class: 'code-text', text: currentCode.text }),
    el('div', { class: 'code-type', text: currentCode.type }));
}
let wakeLock = null;
function showBarcodeFull(code, name) {
  let enc;
  try { enc = autoEncode(code); } catch { return; }
  const w = Math.min(window.innerWidth, window.innerHeight * 1.6) - 32;
  const svg = barcodeSvg(enc.modules, w, Math.round(Math.min(220, window.innerHeight * 0.3)));
  showOverlay([
    name ? el('div', { class: 'lab', text: name }) : null,
    svg,
    el('div', { class: 'code-text', text: enc.text }),
  ].filter(Boolean), 'ltr');
  // Okutulurken ekran kararmasın (destekleyen tarayıcılarda)
  navigator.wakeLock?.request('screen').then((l) => { wakeLock = l; }).catch(() => {});
}
function codeItem(c, onDelete) {
  return el('div', { class: 'code-item' }, [
    el('button', {
      class: 'open', type: 'button',
      onclick: () => showBarcodeFull(c.code, c.name),
    }, [el('b', { text: c.name || c.code }), el('span', { text: c.code })]),
    onDelete ? el('button', { class: 'del-btn', type: 'button', 'aria-label': 'Kodu sil', text: '✕', onclick: onDelete }) : null,
  ].filter(Boolean));
}
function renderCodeList() {
  const codes = Array.isArray(state.codes) ? state.codes : [];
  $('codeList').replaceChildren(...(codes.length
    ? codes.map((c, i) => codeItem(c, () => { state.codes.splice(i, 1); save(); renderCodeList(); }))
    : [el('div', { class: 'empty', text: 'Henüz kayıtlı kod yok. Bir kod yazıp "Kaydet"e dokunun.' })]));
}
let sharedCodes = [];
function renderSharedCodes() {
  $('sharedCodesWrap').hidden = !sharedCodes.length;
  $('sharedCodes').replaceChildren(...sharedCodes.map((c) => codeItem(c)));
}
$('codeInput').addEventListener('input', renderBarcode);
$('codeFull').addEventListener('click', () => { if (currentCode) showBarcodeFull(currentCode.text); });
$('codeSave').addEventListener('click', () => {
  if (!currentCode) return;
  $('codeSaveRow').hidden = false;
  $('codeName').focus();
});
$('codeSaveOk').addEventListener('click', () => {
  if (!currentCode) return;
  if (!Array.isArray(state.codes)) state.codes = [];
  state.codes.unshift({ name: $('codeName').value.trim(), code: currentCode.text });
  save();
  $('codeName').value = '';
  $('codeSaveRow').hidden = true;
  renderCodeList();
});

// --- Kurallar ---
let rules = [];
let ruleCat = 'Tümü';
function renderRules() {
  const q = $('ruleSearch').value.trim().toLocaleLowerCase('tr');
  const cats = ['Tümü', ...new Set(rules.map((r) => r.kategori).filter(Boolean))];
  $('ruleCats').replaceChildren(...cats.map((c) => el('button', {
    class: 'chip' + (c === ruleCat ? ' on' : ''), type: 'button', text: c,
    onclick: () => { ruleCat = c; renderRules(); },
  })));
  const list = rules.filter((r) => (ruleCat === 'Tümü' || r.kategori === ruleCat)
    && (!q || `${r.baslik} ${r.kategori} ${r.metin}`.toLocaleLowerCase('tr').includes(q)));
  $('rules').replaceChildren(...(list.length ? list.map((r) => el('article', { class: 'card' }, [
    el('h3', { text: r.baslik }),
    el('div', { class: 'tag', text: r.kategori || '' }),
    el('p', { text: r.metin }),
  ])) : [el('div', { class: 'empty', text: rules.length ? 'Sonuç yok' : 'Kurallar yüklenemedi. İnternete bağlanıp tekrar açın.' })]));
}
$('ruleSearch').addEventListener('input', renderRules);

// --- İfadeler ---
let phraseData = null;
function renderPhrases() {
  if (!phraseData) {
    $('phrases').replaceChildren(el('div', { class: 'empty', text: 'İfadeler yüklenemedi. İnternete bağlanıp tekrar açın.' }));
    return;
  }
  const lang = phraseData.diller.find((d) => d.kod === state.lang) || phraseData.diller[0];
  $('langChips').replaceChildren(...phraseData.diller.map((d) => el('button', {
    class: 'chip' + (d.kod === lang.kod ? ' on' : ''), type: 'button', text: d.ad,
    onclick: () => { state.lang = d.kod; save(); renderPhrases(); },
  })));
  const dir = lang.rtl ? 'rtl' : 'ltr';
  $('phrases').replaceChildren(...phraseData.ifadeler.map((p) => el('button', {
    class: 'phrase', type: 'button',
    onclick: () => showOverlay([
      el('div', { class: 'big', lang: lang.kod, text: p[lang.kod] || p.en }),
      el('div', { class: 'small-tr', dir: 'ltr', text: p.tr }),
    ], dir),
  }, [
    el('div', { class: 'fl', lang: lang.kod, dir, text: p[lang.kod] || p.en }),
    el('div', { class: 'tr', text: p.tr }),
  ])));
}

// --- Kasa kartı çıktısı ---
$('printCard').addEventListener('click', () => {
  const now = new Date();
  const rateRows = FOREIGN.filter((c) => state.rates[c] > 0).map((c) => el('tr', {}, [
    el('td', { text: `1 ${CURRENCIES[c].symbol} ${c}` }),
    el('td', { text: state.rates[c].toLocaleString('tr-TR', { maximumFractionDigits: 4 }) + ' ₺' }),
  ]));
  const cardRules = rules.filter((r) => r.kart);
  $('printArea').replaceChildren(
    el('h1', { text: 'M4 Kasa Kartı' }),
    el('div', { text: now.toLocaleDateString('tr-TR') + ' ' + now.toLocaleTimeString('tr-TR', { hour: '2-digit', minute: '2-digit' }) }),
    rateRows.length ? el('table', {}, rateRows) : el('p', { text: 'Kur girilmedi.' }),
    ...cardRules.flatMap((r) => [el('h3', { text: r.baslik }), el('p', { text: r.metin })]),
  );
  $('settingsOverlay').hidden = true;
  window.print();
});

// Escape ile katmanları kapat
document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') { $('showOverlay').hidden = true; $('settingsOverlay').hidden = true; }
});

// --- Başlat ---
resetDoviz();
addPriceRow();
renderIndirim();
renderRateBar();
renderCodeList();
showTab(location.hash.slice(1) || state.tab);

Promise.all([
  loadJson('data/kurallar.json'),
  loadJson('data/kampanyalar.json'),
  loadJson('data/ifadeler.json'),
  loadJson('data/barkodlar.json'),
]).then(([k, c, i, b]) => {
  sharedCodes = Array.isArray(b?.barkodlar) ? b.barkodlar.filter((x) => x && typeof x.code === 'string') : [];
  renderSharedCodes();
  rules = Array.isArray(k?.kurallar) ? k.kurallar : [];
  campaigns = Array.isArray(c?.kampanyalar) ? c.kampanyalar : [];
  phraseData = Array.isArray(i?.ifadeler) && Array.isArray(i?.diller) ? i : null;
  renderRules();
  renderCampaignChips();
  renderPhrases();
});

if ('serviceWorker' in navigator) {
  navigator.serviceWorker.register('sw.js').catch(() => { /* çevrimdışı önbellek olmadan da çalışır */ });
}
