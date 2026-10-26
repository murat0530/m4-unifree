import { test } from 'node:test';
import assert from 'node:assert/strict';
import { eanCheckDigit, encodeEAN, encodeCode128, autoEncode, C128_PATTERNS } from '../site/barcode.js';

test('Code 128 desen tablosu: 107 desen, her biri 11 modül (Stop 13)', () => {
  assert.equal(C128_PATTERNS.length, 107);
  C128_PATTERNS.forEach((p, i) => {
    const sum = [...p].reduce((s, d) => s + Number(d), 0);
    assert.equal(sum, i === 106 ? 13 : 11, `desen ${i}`);
  });
  assert.equal(new Set(C128_PATTERNS).size, 107);
});

test('EAN kontrol hanesi', () => {
  assert.equal(eanCheckDigit('400638133393'), '1'); // 4006381333931
  assert.equal(eanCheckDigit('869000000000'), '5');
  assert.equal(eanCheckDigit('9638507'), '4'); // EAN-8: 96385074
});

test('EAN-13: uzunluk ve kontrol', () => {
  const r = encodeEAN('400638133393');
  assert.equal(r.text, '4006381333931');
  assert.equal(r.type, 'EAN-13');
  assert.equal(r.modules.length, 95);
  assert.ok(r.modules.startsWith('101') && r.modules.endsWith('101'));
  assert.throws(() => encodeEAN('4006381333932'), /Kontrol hanesi/);
});

test('EAN-8', () => {
  const r = encodeEAN('96385074');
  assert.equal(r.type, 'EAN-8');
  assert.equal(r.modules.length, 67);
});

test('Code 128: uzunluk = 11 x (karakter + start + check) + 13', () => {
  assert.equal(encodeCode128('ABC').modules.length, 11 * 5 + 13);
  // Rakamlar ikişerli sıkıştırılır: 6 hane -> 3 değer
  assert.equal(encodeCode128('123456').modules.length, 11 * 5 + 13);
  // Tek sayıda hane: son hane Code B'ye geçer
  assert.equal(encodeCode128('12345').modules.length, 11 * 6 + 13);
  assert.throws(() => encodeCode128('ŞEKER'), /yazılamaz/);
  assert.throws(() => encodeCode128(''));
});

test('autoEncode türü seçer', () => {
  assert.equal(autoEncode('4006381333931').type, 'EAN-13');
  assert.equal(autoEncode('96385074').type, 'EAN-8');
  assert.equal(autoEncode('PRS-0042').type, 'Code 128');
  assert.equal(autoEncode('123456').type, 'Code 128');
});
