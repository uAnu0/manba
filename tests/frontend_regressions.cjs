// Exercise the actual fix and verdict functions without a browser or paid API.
const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const path = require('node:path');
const source = fs.readFileSync(path.resolve(__dirname, '../app/static/app.js'), 'utf8');
const begin = source.slice(0, source.indexOf('  // ---------- state ----------'));
const quoteHelpers = source.slice(source.indexOf('  function quoteOf('), source.indexOf('  function wordingScore('));
const fixes = source.slice(source.indexOf('  const CONSENSUS_RE'), source.indexOf('  function progressHtml()'));
const context = { localStorage: { getItem: () => null }, document: { getElementById: () => null } };
vm.createContext(context);
vm.runInContext(begin + '\n const store = {data:null, entries:[], fixes:{}};\n' + quoteHelpers + fixes +
                '\n globalThis.api = {store, fixPlan, draftNow, verdictOf};})();', context);
const { store, fixPlan, draftNow, verdictOf } = context.api;
const text = 'قال تعالى: «وأحل الله البيع وحرم الزنا». قال تعالى: «وأحل الله البيع وحرم الزنا».';
const q = '«وأحل الله البيع وحرم الزنا»';
const start = text.lastIndexOf(q);
const sg = { status: 'semantic_variant', source: {book:'القرآن الكريم', number:'2:275', matched_text:'وأحل الله البيع وحرم الربا'} };
const entry = { n: 2, it: {start, end:start + q.length}, v:{ k:'fix', seg:sg} };
store.data = {original_text:text}; store.entries = [entry]; store.fixes = {2:'applied'};
assert.equal(fixPlan(entry).start, start);
assert.ok(draftNow().startsWith('قال تعالى: ' + q));
assert.ok(draftNow().endsWith('﴿وأحل الله البيع وحرم الربا﴾.'));
assert.equal(draftNow().split('الزنا').length - 1, 1);
store.manualDraft = 'تحرير يدوي محفوظ\nكما كتبته';
assert.equal(draftNow(), store.manualDraft);
assert.equal(fixPlan(entry), null);
delete store.manualDraft;
entry.v.seg = {status:'semantic_variant', translation:{text:'Indeed, with hardship comes ease'}, differences:['the reference given is wrong']};
assert.equal(fixPlan(entry), null);
entry.v = {k:'neu', fiqh:{status:'school_differs', matched_by:'keywords', attribution:{school:'الحنفية'}}};
assert.equal(fixPlan(entry), null);
const v = verdictOf({kind:'quote', text:'نص', quote:{classification:'quran', status:'verified', source:{book:'القرآن الكريم',number:'1:1'}}, verdict_kind:'neu', needs_action:true});
assert.equal(v.k, 'neu');
assert.match(v.label, /مراجعة/);
// An access link (#code=...) saves the code and leaves a clean address; any other address is left alone.
{
  const html = fs.readFileSync(path.resolve(__dirname, '../app/static/app.html'), 'utf8');
  const early = html.match(/<script>\/\* An access link[\s\S]*?<\/script>/)[0].replace(/^<script>|<\/script>$/g, '');
  const open = (hash, failStorage) => {
    const saved = {}, urls = [];
    const win = { location: { hash, pathname: '/', search: '?x=1' }, history: { replaceState: (a, b, u) => urls.push(u) },
      localStorage: { setItem: (k, v) => { if (failStorage) throw new Error('blocked'); saved[k] = v; } } };
    vm.runInNewContext(early, { ...win, window: win });
    return { saved, urls, flag: win.__manbaCode };
  };
  let r = open('#code=abc%2B123%3D');
  assert.deepEqual(r.saved, { manba_access_token: 'abc+123=' }); assert.deepEqual(r.urls, ['/?x=1']); assert.equal(r.flag, 1);
  r = open('#how'); assert.deepEqual(r.saved, {}); assert.deepEqual(r.urls, []); assert.equal(r.flag, undefined);
  r = open('#code=secret', true); assert.deepEqual(r.urls, ['/?x=1']); assert.equal(r.flag, -1);   // storage blocked: the address is still cleaned
}
console.log('7 frontend regression scenarios passed');
