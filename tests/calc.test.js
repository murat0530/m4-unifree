import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  parseAmount, parseRate, formatAmount, settle, breakdown,
  percentOff, buyNPayM, secondItemOff, splitChange, notesOnly,
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

const rates = { EUR: 40, USD: 35, GBP: 46 };

test('settle: tek para birimi, para üstü', () => {
  const r = settle({ amount: 8500, currency: 'EUR' }, [{ amount: 10000, currency: 'EUR' }], rates);
  assert.equal(r.status, 'change');
  assert.equal(r.perCurrency.EUR, 1500);
  assert.equal(r.perCurrency.TRY, 60000);
});

test('settle: karışık ödeme, kalan yukarı yuvarlanır', () => {
  // 100 € = 4000 TL; 50 € (2000) + 20 $ (700) = 2700 TL; kalan 1300 TL
  const r = settle({ amount: 10000, currency: 'EUR' },
    [{ amount: 5000, currency: 'EUR' }, { amount: 2000, currency: 'USD' }], rates);
  assert.equal(r.status, 'remaining');
  assert.equal(r.perCurrency.TRY, 130000);
  assert.equal(r.perCurrency.EUR, 3250);
  assert.equal(r.perCurrency.USD, 3715); // 37,1428.. -> 37,15 (yukarı)
});

test('settle: para üstü aşağı yuvarlanır (fazla verilmez)', () => {
  // 10 $ öder, 300 TL'lik ürün: 350-300 = 50 TL üstü; EUR olarak 1,25; GBP 1,0869.. -> 1,08
  const r = settle({ amount: 30000, currency: 'TRY' }, [{ amount: 1000, currency: 'USD' }], rates);
  assert.equal(r.status, 'change');
  assert.equal(r.perCurrency.GBP, 108);
  assert.equal(r.perCurrency.EUR, 125);
});

test('settle: tam ödeme', () => {
  const r = settle({ amount: 4000, currency: 'TRY' }, [{ amount: 100, currency: 'EUR' }], rates);
  assert.equal(r.status, 'exact');
});

test('settle: kuru girilmemiş birim hesaplamaya katılmaz, ödemede hata verir', () => {
  const r = settle({ amount: 1000, currency: 'TRY' }, [{ amount: 2000, currency: 'TRY' }], { EUR: 40 });
  assert.equal(r.perCurrency.USD, undefined);
  assert.throws(() => settle({ amount: 1000, currency: 'USD' }, [], { EUR: 40 }));
});

test('settle: kayan nokta kuru', () => {
  const r = settle({ amount: 1000, currency: 'EUR' }, [{ amount: 1000, currency: 'EUR' }], { EUR: 38.1234 });
  assert.equal(r.status, 'exact');
});

test('breakdown', () => {
  assert.deepEqual(breakdown(1750, 'EUR'), {
    parts: [{ denom: 1000, count: 1 }, { denom: 500, count: 1 }, { denom: 200, count: 1 }, { denom: 50, count: 1 }],
    rest: 0,
  });
  // TL'de 1 kuruş yok: 3 kuruş küsurat kalır
  assert.equal(breakdown(1003, 'TRY').rest, 3);
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

test('notesOnly: bozuk para atılır', () => {
  assert.equal(notesOnly(36250, 'EUR'), 36000);
  assert.equal(notesOnly(1799, 'USD'), 1700);
  assert.equal(notesOnly(400, 'EUR'), 0);
});

test('splitChange: otomatik, önce € banknot sonra ₺', () => {
  // 18.000 TL para üstü, 1 € = 50: 360 € -> banknotla 360 € tam, kalan 0 ₺
  assert.deepEqual(splitChange(1800000, 'EUR', null, 'TRY', { EUR: 50 }), { first: 36000, second: 0, maxFirst: 36000 });
  // 18.120 TL: 362,40 € -> 360 € banknot + 120 ₺
  assert.deepEqual(splitChange(1812000, 'EUR', null, 'TRY', { EUR: 50 }), { first: 36000, second: 12000, maxFirst: 36240 });
});

test('splitChange: elle tutar, kalanı başka dövizde', () => {
  // 18.000 TL, 100 € verilir (5.000 TL), kalan 13.000 TL = 302,32 $ (1 $ = 43)
  const r = splitChange(1800000, 'EUR', 10000, 'USD', { EUR: 50, USD: 43 });
  assert.equal(r.first, 10000);
  assert.equal(r.second, 30232);
});

test('splitChange: fazla tutar ve aynı birim reddedilir', () => {
  assert.throws(() => splitChange(1800000, 'EUR', 40000, 'TRY', { EUR: 50 }), /en fazla 360,00/);
  assert.throws(() => splitChange(1800000, 'TRY', null, 'TRY', {}), /farklı/);
});
