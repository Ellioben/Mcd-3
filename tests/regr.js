global.window = {};
require('/Users/yongbo/WorkBuddy/Offline/mcd/data/catalog.js');

const fs = require('fs');
const code = fs.readFileSync('/Users/yongbo/WorkBuddy/Offline/mcd/recommend.html', 'utf8')
  .match(/<script>([\s\S]*)<\/script>/)[1];

function el(){
  const e = { innerHTML:'', textContent:'', value:'', className:'', style:{}, title:'',
    dataset:{}, onclick:null, disabled:false,
    classList:{ _set:{}, add(c){this._set[c]=1;}, remove(c){delete this._set[c];},
      toggle(c,f){ if(f===undefined) this._set[c]=!this._set[c]; else f?this._set[c]=1:delete this._set[c]; return !!this._set[c];},
      contains(c){return !!this._set[c];} },
    querySelectorAll(){ return []; }, addEventListener(){}, _src:'' };
  Object.defineProperty(e, 'src', { get(){ return e._src; }, set(v){ e._src = v; } });
  return e;
}
const els = {};
const selMap = {};
global.document = {
  getElementById(id){ return els[id] || (els[id] = el()); },
  querySelector(s){ return selMap[s] || (selMap[s] = el()); },
  querySelectorAll(){ return []; },
  createElement(){ return el(); },
};

const api = new Function('window', 'document', 'console',
  code + '\n; return { parseMust, makeCards, state, evaluate, unitPriceOf, cardHTML, tagValue, render, renderRuler, renderBands, renderGuardState, removeLine, changeQty, appendMusts, doGenerate, regenerate, renderPeople, requantize, selfTest, guardOK, poolOf, buildBasket, blockedByAvoid, imgNext, USABLE, TIER_KEYS, dropMust };'
)(global.window, global.document, console);

let pass = 0, fail = 0;
const ok = (c, msg) => { if(c){ pass++; } else { fail++; console.log('  ✗ ' + msg); } };

api.state.env = { store:'1450713', slot:'normal', coupon:true, soldOut:false };

// ---------- 1. 页内自检 ----------
const st = api.selfTest(600);
ok(st.run > 0 && st.fail === 0, `selfTest(600) 护栏零失败（实跑 ${st.run}，败 ${st.fail}）`);

// ---------- 2. 多必点 + 行数量 ----------
const m1 = api.parseMust('巨无霸').sku;
const m2 = api.parseMust('薯条').sku;
api.state.musts = [m1, m2];
api.state.cards = api.makeCards([m1, m2], 't1', null, 0);
['satisfy','cheap','fit'].forEach(k => {
  const lines = api.state.cards[k].lines;
  ok(lines.some(l => l.sku.code === m1.code && l.must), k + ' 含必点巨无霸');
  ok(lines.every(l => l.qty === 1), k + ' 一人时全部 qty=1');
});

// ---------- 3. 行级数量合计（智能量级：主食/饮料每人1份，小吃两人1份） ----------
api.state.people = 2;
api.state.cards = api.makeCards([m1, m2], 't2', null, 0);
const c2 = api.state.cards.cheap;
ok(c2.lines.filter(l => l.role === 'main').every(l => l.qty === 2), '2人 主食 qty=2（每人1份）');
ok(c2.lines.filter(l => l.role === 'drink').every(l => l.qty === 2), '2人 饮料 qty=2');
ok(c2.lines.filter(l => l.role === 'side').every(l => l.qty === 1), '2人 小吃 qty=1（两人1份，多行平分）');
ok(c2.lines.filter(l => l.role === 'extra').every(l => l.qty === 1), '2人 甜品 qty=1');
const t2exp = c2.lines.reduce((a, l) => a + api.unitPriceOf(l.sku, api.state.env) * l.qty, 0);
ok(Math.abs(c2.total - t2exp) < 0.02, 'total = Σ单价×各行数量');
ok(c2.pieces === c2.lines.reduce((a, l) => a + l.qty, 0), 'pieces = Σqty');
const beforeTotal = c2.total;
const linePrice = api.unitPriceOf(c2.lines[0].sku, api.state.env);
api.changeQty('cheap', 0, +1);
ok(Math.abs(api.state.cards.cheap.total - (beforeTotal + linePrice)) < 0.02, 'changeQty +1 → total 加单价');
ok(api.state.cards.cheap.lines[0].qty === 3, 'qty 2→3');
api.changeQty('cheap', 0, -1);
api.changeQty('cheap', 0, -1);
ok(api.state.cards.cheap.lines[0].qty === 1, 'qty 减到 1 为下限');
ok(isFinite(api.state.cards.cheap.satisfyPct), '数量不均 satisfyPct 有限');
api.state.people = 1;
api.state.cards = api.makeCards([m1, m2], 't3', null, 0);

// ---------- 3b. 多必点同角色平分配额（4人 × 2个必点主食 → 各×2） ----------
const mm = api.parseMust('板烧').sku;
api.state.people = 4;
api.state.cards = api.makeCards([m1, mm], 't5', null, 0);
['satisfy','cheap','fit'].forEach(k => {
  const mains = api.state.cards[k].lines.filter(l => l.role === 'main');
  ok(mains.length === 2 && mains.every(l => l.must && l.qty === 2),
    k + ' 4人两个必点主食各×2（平分配额，不各×4）');
});
api.state.people = 1;

// ---------- 4. 追加必点 ----------
const m3 = api.parseMust('麦旋风').sku;
const sigBefore = ['satisfy','cheap','fit'].map(k => api.state.cards[k].lines.map(l => l.sku.code).join()).join('|');
api.appendMusts([m3]);
ok(api.state.musts.length === 3, '追加后必点数 3');
['satisfy','cheap','fit'].forEach(k => {
  const lines = api.state.cards[k].lines;
  ok(lines[lines.length - 1].sku.code === m3.code && lines[lines.length - 1].must, k + ' 麦旋风追加在尾部');
});
const sigAfter = ['satisfy','cheap','fit'].map(k => api.state.cards[k].lines.slice(0, -1).map(l => l.sku.code).join()).join('|');
ok(sigBefore === sigAfter, '已生成的行保持原样（只是尾部追加）');
ok(api.appendMusts([m3]) === false, '重复追加返回 false');
api.doGenerate('板烧');
ok(api.state.musts.some(m => m.code === api.parseMust('板烧').sku.code), 'doGenerate 已生成时走追加');

// ---------- 4b. 取消单个必点：其余行不动、不重播入场动画 ----------
api.state.musts = [m1, m2, m3];
api.state.people = 1;
api.state.cards = api.makeCards([m1, m2, m3], 't6', null, 0);
api.state.entered = true;
const before = api.state.cards.satisfy.lines.map(l => l.sku.code);
api.state.musts = api.state.musts.filter(m => m.code !== m1.code);
api.dropMust(m1.code);
const after = api.state.cards.satisfy.lines.map(l => l.sku.code);
ok(after.indexOf(m1.code) < 0, '取消的必点已从卡里移除');
ok(before.filter(c => c !== m1.code).every(c => after.indexOf(c) >= 0), '其余行 SKU 原样保留（没全盘重算）');
ok(api.state.cards.satisfy.lines.some(l => l.role === 'main'), '空出来的主食槽位补了新的一件');
ok(api.state.entered === true, '取消必点不重置 entered（卡片不会重播入场动画）');
['cheap','fit'].forEach(k => {
  ok(api.state.cards[k].lines.every(l => l.sku.code !== m1.code), k + ' 同步移除该必点');
});

// ---------- 5. 删除行 ----------
const delN = api.state.cards.satisfy.lines.length;
api.removeLine('satisfy', 0);
ok(api.state.cards.satisfy.lines.length === delN - 1, '删除行数 -1');
while(api.state.cards.satisfy.lines.length > 1) api.removeLine('satisfy', 0);
const one = api.state.cards.satisfy;
api.removeLine('satisfy', 0);
ok(api.state.cards.satisfy === one, '最后一件不可删');

// ---------- 6. 守卫破灰化（同维度比较） ----------
// 注意：四必点（两个主食）时守卫本来就无解，灰化是正确行为；这里用单必点验证「领先→不着灰」
api.state.musts = [m1];
api.state.cards = api.makeCards(api.state.musts, 't4', null, 0);
if(!api.guardOK(api.state.cards)){ console.log('  (单必点也碰上无解，跳过领先断言)'); }
api.render();
['satisfy','cheap','fit'].forEach(k => {
  const tagEl = selMap[`.card[data-tier="${k}"] .tag`];
  ok(api.guardOK(api.state.cards) ? !tagEl.classList.contains('off') : true, k + ' 领先时角标不着灰');
});
api.state.cards.satisfy.satisfyPct = -5;
api.render();
ok(selMap['.card[data-tier="satisfy"] .tag'].classList.contains('off'), '满足派不领先 → off');
ok(!selMap['.card[data-tier="cheap"] .tag'].classList.contains('off'), 'cheap 不受跨维度误伤');

// ---------- 7. 渲染冒烟 ----------
api.state.people = 3;
let threw = false;
try { api.render(); api.renderRuler(); api.renderBands(); } catch(e){ threw = true; console.log('   ' + e.message); }
ok(!threw, 'n=3 渲染三件套不抛错');
api.state.people = 1;

// ---------- 8. 图片回退链 ----------
const img = el();
img.dataset.fb = 'https://a/X.png|https://b/Y.png';
api.imgNext(img);
ok(img.src === 'https://a/X.png', '第一次回退取候选1');
api.imgNext(img);
ok(img.src === 'https://b/Y.png', '第二次回退取候选2');
api.imgNext(img);
ok(img.classList.contains('off'), '候选耗尽 → off 占位');
const html = api.cardHTML('cheap', api.state.cards.cheap, api.state.musts, 1);
ok(html.indexOf('data-fb=') > 0 && html.indexOf('qstep') > 0 && html.indexOf('imgNext') > 0, '卡片 HTML 含回退链/步进器');

// ---------- 9. 人数重置（按角色配额重新搭配） ----------
api.state.people = 4;
api.requantize();
const lc = api.state.cards.cheap;
ok(lc.lines.filter(l => l.role === 'main').every(l => l.qty === 4), 'requantize 4人 主食=4');
ok(lc.lines.filter(l => l.role === 'drink').every(l => l.qty === 4), 'requantize 4人 饮料=4');
ok(lc.lines.filter(l => l.role === 'side').every(l => l.qty === 2), 'requantize 4人 小吃=2（两人1份）');
ok(lc.lines.filter(l => l.role === 'extra').every(l => l.qty === 1), 'requantize 4人 甜品=1（每3人1份）');
api.state.people = 1;

// ---------- 10. 忌口 ----------
api.state.avoid = ['咖啡因'];
['satisfy','cheap','fit'].forEach(k => {
  const b = api.buildBasket(k, api.state.musts, api.state.env, 'av', null);
  ok(b.every(l => !api.blockedByAvoid(l.sku)), k + ' 忌口无咖啡类');
});
api.state.avoid = [];

console.log(`\n=== 行级数量+追加+守卫修复: ${pass} 通过 / ${fail} 失败 ===`);
process.exit(fail ? 1 : 0);
