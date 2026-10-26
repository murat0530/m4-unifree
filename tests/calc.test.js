import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  parseAmount, parseRate, formatAmount, perEur, convert, convertSteps,
  percentOff, buyNPayM, secondItemOff,
} from '../site/calc.js';

test('parseAmount: Türkçe ve İngilizce yazım', () => {
  assert.equal(parseAmount('12'), 1200);
  assert.equal(parseAmount('12,5'), 1250);
  assert.equal(parseAmount('12.50'), 1250);
  assert.equal(parseAmount('1.234,56'), 123456);
  assert.equal(parseAmount('1,234.56'), 123456);
  assert.equal(parseAmount(' 0,05 '), 5);
  assert.equal(parseAmount(''), null);
  assert.equal(parseAmount('abc'), null);
  assert.equal(parseAmount('1,234'), null); // belirsiz: 3 ondalık hane kabul edilmez
  assert.equal(parseAmount('1.000'), 100000); // nokta binlik ayırıcı
  assert.equal(parseAmount('12.500.000'), 1250000000);
  assert.equal(parseAmount('12.50'), 1250); // 2 hane: ondalık
  assert.equal(parseAmount('1.0000'), null);
  assert.equal(parseAmount('-5'), null);
});

test('parseRate', () => {
  assert.equal(parseRate('38,5'), 38.5);
  assert.equal(parseRate('38.1234'), 38.1234);
  assert.equal(parseRate('0'), null);
  assert.equal(parseRate('x'), null);
});

test('formatAmount', () => {
  assert.equal(formatAmount(123456, 'EUR'), '1.234,56 €');
  assert.equal(formatAmount(5), '0,05');
  assert.equal(formatAmount(-1250, 'TRY'), '-12,50 ₺');
});

const rates = { eurTry: 50, parity: { USD: 1.17, GBP: 0.86 } };

test('perEur', () => {
  assert.equal(perEur('EUR', rates), 1);
  assert.equal(perEur('TRY', rates), 50);
  assert.equal(perEur('USD', rates), 1.17);
  assert.throws(() => perEur('TRY', { parity: {} }), /Euro kuru/);
  assert.throws(() => perEur('GBP', { eurTry: 50, parity: {} }), /GBP paritesi/);
});

test('convert: 500 $ euro üzerinden', () => {
  assert.equal(convert(50000, 'USD', 'EUR', rates), 42735); // 500 / 1,17 = 427,35
  assert.equal(convert(50000, 'USD', 'TRY', rates), 2136752); // 427,3504 × 50 = 21.367,52
  assert.equal(convert(50000, 'USD', 'GBP', rates), 36752); // 427,3504 × 0,86 = 367,52
});

test('convert: euro ve lira', () => {
  assert.equal(convert(10000, 'EUR', 'TRY', rates), 500000);
  assert.equal(convert(500000, 'TRY', 'EUR', rates), 10000);
  assert.equal(convert(500000, 'TRY', 'USD', rates), 11700);
  assert.equal(convert(12345, 'EUR', 'EUR', rates), 12345);
});

test('convert: geri çevirince en fazla 1 kuruş fark', () => {
  for (const c of [1, 99, 12345, 50000, 9999999]) {
    const back = convert(convert(c, 'USD', 'TRY', rates), 'TRY', 'USD', rates);
    assert.ok(Math.abs(back - c) <= 1, `${c} -> ${back}`);
  }
});

test('convert: yuan, Kanada doları, riyal', () => {
  const r = { eurTry: 50, parity: { CNY: 8.3, CAD: 1.6, SAR: 4.4 } };
  assert.equal(convert(50000, 'TRY', 'CNY', r), 8300); // 500 ₺ = 10 € = 83 ¥
  assert.equal(convert(50000, 'TRY', 'CAD', r), 1600);
  assert.equal(convert(10000, 'SAR', 'TRY', r), 113636); // 100 SAR = 22,7273 € = 1.136,36 ₺
  assert.equal(convert(8300, 'CNY', 'SAR', r), 4400);
});

test('convertSteps', () => {
  assert.deepEqual(convertSteps('USD', 'TRY', rates), ['÷ 1,17', '× 50']);
  assert.deepEqual(convertSteps('EUR', 'TRY', rates), ['× 50']);
  assert.deepEqual(convertSteps('TRY', 'EUR', rates), ['÷ 50']);
  assert.deepEqual(convertSteps('USD', 'GBP', rates), ['÷ 1,17', '× 0,86']);
});

test('percentOff', () => {
  assert.deepEqual(percentOff(9999, 15), { discount: 1500, total: 8499 });
});

test('buyNPayM: 3 al 2 öde, en ucuzu bedava', () => {
  const r = buyNPayM([1000, 3000, 2000], 3, 2);
  assert.deepEqual(r, { gross: 6000, discount: 1000, total: 5000 });
  // 4 ürün: tek grup oluşur, 4. ürün tam fiyat
  assert.equal(buyNPayM([1000, 1000, 1000, 1000], 3, 2).total, 3000);
  assert.throws(() => buyNPayM([1000], 2, 2));
});

test('secondItemOff', () => {
  const r = secondItemOff([4000, 2000, 3000], 50);
  // sıralı: 4000, 3000, 2000 -> 3000'e %50
  assert.deepEqual(r, { gross: 9000, discount: 1500, total: 7500 });
});
