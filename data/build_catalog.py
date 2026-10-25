#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
把 data/raw/ 下的三份真实 MCP 返回，构建成前端可直接用的 catalog。

输入：
  data/raw/meals-1450713.txt        query-meals 的商品价格表
  data/raw/categories-1450713.json  query-meals 的分类与卖点标签
  data/raw/nutrition.txt            list-nutrition-foods 的营养表

输出：
  data/catalog.json    全量结构化数据（供程序读）
  data/catalog.js      window.MCD_CATALOG = {...}（供 file:// 下 <script> 直接引）

字段约定：
  顶层字段名与 MCP 返回一致（code/name/image/currentPrice/originalPrice/
  discountType/canWithOrder/tags），未来接真接口时只需替换数据源。
  所有本地推导出来的东西一律放进 `_d`，方便和原生字段区分。

用法：python3 data/build_catalog.py
"""

import json
import os
import re
import statistics
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, 'raw')
IMG_BASE = 'https://menu-img.mcd.cn/pcm/prod/menu/'
IMG_DIR = os.path.join(HERE, 'img')

# ---------------------------------------------------------------- 分类规则

# 分类 → 槽位。None 表示该分类混装，交给名称规则判断
CAT_ROLE = {
    '鸡肉汉堡/卷': 'main',
    '蘸酱炸鸡': 'side',
    '大堡口福单人餐': 'main',
    '巨无霸牛鱼肉堡': 'main',
    '安格斯MAX厚牛堡': 'main',
    '开心乐园': 'main',
    '炸鸡': 'side',
    '麦咖啡': 'drink',
    '饮品': 'drink',
}

# 名称关键词 → 槽位。顺序即优先级：extra → drink → side → main
NAME_ROLE_HINTS = [
    (r'冰淇淋|圆筒|新地|麦旋风|阿芙佳朵|^派$|派\b|雪冰|拉明顿', 'extra'),
    (r'可乐|雪碧|纯悦|怡泉|咖啡|奶|茶|汁|豆浆|炫酷|美汁源|柠柠|橙橙|水$', 'drink'),
    (r'薯|鸡块|鸡翅|鸡排|鸡球|鸡条|玉米杯|芝士条|薯饼|薯条|双翅|V翅|脆汁鸡|肉骨鸡|卷$|炸鸡|苹果片', 'side'),
    (r'堡|汉堡|麦满分|套餐|件套', 'main'),
]

# 非食物：周边、酱料。不进推荐池
NON_FOOD = re.compile(r'帽|丝巾|星愿贴|按摩捶|痒痒挠|玩偶|周边|酱$')

# 名字归一化
NORM_MAP = {'（': '(', '）': ')', '™': '', ' ': '', '　': ''}

# 菜单名 → 营养表名 的人工别名（只列自动匹配不到的）
ALIAS = {
    '阳光橙麦炫酷': '麦旋酷阳光橙',
    '薯条': '中薯条',
    '可乐': '可乐中杯',
    '雪碧': '雪碧中杯',
    '怡泉+C': '中杯怡泉+C',
    '阳光柠檬红茶': '阳光柠檬红茶中杯',
    '卡布奇诺': '卡布奇诺中杯',
    '鲜萃咖啡': '小杯鲜萃咖啡',
    '牛奶': '纯牛奶(盒装)',
    '100% 苹果汁(盒装)': '100%苹果汁',
    '燕麦奶': '冰燕麦奶中杯',
    '燕麦奶铁': '冰燕麦奶铁中杯',
    '麦咖啡™奶铁': '冰奶铁中杯',
    '麦咖啡™美式': '冰美式中杯',
    '浓浓黑巧（冰/热）': '热浓浓黑巧中杯',
    '浓浓燕麦黑巧（冰/热）': '热浓浓燕麦黑巧中杯',
    '玉米杯': '小杯玉米杯',
    '麦乐鸡': '麦乐鸡5块',
    '麦辣鸡翅': '麦辣鸡翅-2块',
    '那么大鸡排（椒盐风味）': '那么大鸡排',
    '新地': '朱古力新地',
    '派': '香芋派',
    '经典麦旋风': '奥利奥麦旋风',
    '麦麦脆汁鸡1块': '麦麦脆汁鸡-琵琶腿',
    '红提风味薄皮焦香V翅': '柠萌风味薄皮焦香V翅',
}


def norm(s: str) -> str:
    for a, b in NORM_MAP.items():
        s = s.replace(a, b)
    return s.strip().lower()


# ---------------------------------------------------------------- 读取原始数据

def load_meals():
    rows = []
    with open(os.path.join(RAW, 'meals-1450713.txt'), encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            p = line.split('|')
            assert len(p) == 7, f'字段数不对: {line}'
            code, name, cur, orig, dtype, cwo, img = p
            # 本地图片优先：fetch_images.py 落过盘的 SKU 直接指到 data/img/，页面不再走 CDN
            local_img = None
            for ext in ('.png', '.jpg'):
                cand = os.path.join(IMG_DIR, code + ext)
                if os.path.exists(cand) and os.path.getsize(cand) > 1000:
                    local_img = 'data/img/' + code + ext
                    break
            rows.append({
                'code': code,
                'name': name,
                'image': IMG_BASE + img,
                **({'localImg': local_img} if local_img else {}),
                'currentPrice': float(cur),
                'originalPrice': float(orig),
                'discountType': None if dtype == '-' else dtype,
                'canWithOrder': cwo == 'true',
            })
    return rows


def load_categories():
    with open(os.path.join(RAW, 'categories-1450713.json'), encoding='utf-8') as f:
        d = json.load(f)
    code_cats, code_tags = defaultdict(list), defaultdict(list)
    for cat in d['categories']:
        for m in cat['meals']:
            c = m['code']
            if cat['name'] not in code_cats[c]:
                code_cats[c].append(cat['name'])
            for t in m.get('tags', []):
                if t not in code_tags[c]:
                    code_tags[c].append(t)
    return code_cats, code_tags


def load_nutrition():
    items = []
    with open(os.path.join(RAW, 'nutrition.txt'), encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            p = line.split(',')
            if len(p) != 9:
                continue
            name, desc, kj, kcal, pro, fat, carb, na, ca = p
            items.append({
                'name': name,
                'nutritionDescription': None if desc == 'null' else desc,
                'energyKj': float(kj),
                'energyKcal': float(kcal),
                'protein': float(pro),
                'fat': float(fat),
                'carbohydrate': float(carb),
                'sodium': float(na),
                'calcium': float(ca),
            })
    return items


def load_json(name):
    with open(os.path.join(RAW, name), encoding='utf-8') as f:
        return json.load(f)


# ---------------------------------------------------------------- 推导

# 甜品关键词：即使归在「麦咖啡」「小食甜品」分类，也应当进 extra 槽
DESSERT_RE = re.compile(r'冰淇淋|圆筒|新地|麦旋风|阿芙佳朵|^派$|雪冰|拉明顿')


def guess_role(name, cats):
    # 甜品优先：阿芙佳朵在「麦咖啡」分类下，但语义是加餐甜点
    if DESSERT_RE.search(name):
        return 'extra'
    for c in cats:
        if CAT_ROLE.get(c):
            return CAT_ROLE[c]
    for pat, role in NAME_ROLE_HINTS:
        if re.search(pat, name):
            return role
    return None


def is_combo(name, cats):
    if re.search(r'套餐|件套|双人餐|单人餐|分享餐|随心选|随心拼|随心配|拼盘|小食盘|乐园餐', name):
        return True
    return any('多人餐' in c or '500大卡' in c for c in cats)


def fit_line(samples):
    """最小二乘拟合 y = a + b·x。用于按价位估热量。"""
    n = len(samples)
    if n < 2:
        return None
    sx = sum(x for x, _ in samples)
    sy = sum(y for _, y in samples)
    sxx = sum(x * x for x, _ in samples)
    sxy = sum(x * y for x, y in samples)
    den = n * sxx - sx * sx
    if abs(den) < 1e-9:
        return None
    b = (n * sxy - sx * sy) / den
    a = (sy - b * sx) / n
    return a, b


def main():
    meals = load_meals()
    code_cats, code_tags = load_categories()
    nutri = load_nutrition()

    by_name = {}
    for n in nutri:
        by_name.setdefault(norm(n['name']), []).append(n)

    def find_nutrition(name):
        if name in ALIAS:
            k = norm(ALIAS[name])
            if k in by_name:
                return by_name[k][0], 'alias'
        k = norm(name)
        if k in by_name:
            return by_name[k][0], 'exact'
        cands = [(nk, v) for nk, v in by_name.items() if nk.startswith(k)]
        if cands:
            cands.sort(key=lambda x: len(x[0]))
            return cands[0][1][0], 'prefix'
        stripped = re.sub(r'\(.*?\)', '', k)
        if stripped and stripped != k:
            if stripped in by_name:
                return by_name[stripped][0], 'stripped'
            cands = [(nk, v) for nk, v in by_name.items() if nk.startswith(stripped)]
            if cands:
                cands.sort(key=lambda x: len(x[0]))
                return cands[0][1][0], 'stripped-prefix'
        return None, None

    # --- 第一遍：基础属性
    for m in meals:
        m['categories'] = code_cats.get(m['code'], [])
        m['tags'] = code_tags.get(m['code'], [])
        n, how = find_nutrition(m['name'])
        m['nutrition'] = n
        m['_nMatch'] = how
        m['withOrder'] = {'membershipCode': '106', 'specId': '880'} \
            if m['discountType'] == '随单购麦金卡优惠' else None

    # --- 第二遍：缺营养的，按「同槽位 价格→热量」线性拟合估算（明确标 estimated）
    for m in meals:
        m['_role0'] = guess_role(m['name'], m['categories'])

    NUT_KEYS = ('energyKj', 'energyKcal', 'protein', 'fat', 'carbohydrate', 'sodium', 'calcium')
    pool_by_role = defaultdict(list)
    for m in meals:
        if m['nutrition'] and m['_role0']:
            pool_by_role[m['_role0']].append((m['currentPrice'], m['nutrition']))

    fits = {}
    for role, samples in pool_by_role.items():
        pts = [(p, n['energyKcal']) for p, n in samples if n['energyKcal'] > 0]
        fits[role] = fit_line(pts)

    for m in meals:
        if m['nutrition'] is not None or m['_role0'] not in pool_by_role:
            continue
        pool = pool_by_role[m['_role0']]
        med = {k: statistics.median([n[k] for _, n in pool]) for k in NUT_KEYS}
        f = fits.get(m['_role0'])
        if f and med['energyKcal'] > 0:
            a, b = f
            pred = a + b * m['currentPrice']
            # 别让拟合结果跑飞：下限 60kcal，上限是槽位中位数的 3 倍
            pred = max(60.0, min(med['energyKcal'] * 3, pred))
            scale = pred / med['energyKcal']
        else:
            scale = 1.0
        est = {k: round(med[k] * scale, 1) for k in NUT_KEYS}
        est.update({'name': None, 'nutritionDescription': None})
        m['nutrition'] = est
        m['_nMatch'] = 'fit-by-price'

    # --- 第三遍：派生字段
    for m in meals:
        is_food = not NON_FOOD.search(m['name'])
        role = m['_role0'] if is_food else None
        kind = 'combo' if is_combo(m['name'], m['categories']) else 'single'
        save = round(m['originalPrice'] - m['currentPrice'], 2)
        if m['discountType'] and '随单购' in m['discountType']:
            save_kind = 'conditional'
        elif save > 0:
            save_kind = 'bare'
        else:
            save_kind = 'none'

        m['_d'] = {
            'isFood': is_food,
            'role': role,
            'kind': kind,
            # 能不能进推荐池：食物 + 有槽位 + 单品 + 有营养
            'usable': bool(is_food and role and kind == 'single' and m['nutrition']),
            'listPrice': m['originalPrice'],
            'cardPrice': m['currentPrice'],
            # 不买卡时的实付价：随单购优惠不买卡就按原价
            'priceIfNoCard': m['originalPrice'] if save_kind == 'conditional' else m['currentPrice'],
            'saveAmount': save,
            'saveRate': round(save / m['originalPrice'], 4) if m['originalPrice'] else 0,
            'saveKind': save_kind,
            'nutritionSource': 'api' if m['_nMatch'] in
                              ('alias', 'exact', 'prefix', 'stripped', 'stripped-prefix') else
                              ('estimated' if m['_nMatch'] == 'fit-by-price' else None),
            'nutritionPredict': m['_nMatch'] == 'fit-by-price',
            'kcal': (m['nutrition'] or {}).get('energyKcal'),
        }
        del m['_role0'], m['_nMatch']

    usable = [m for m in meals if m['_d']['usable']]
    stat = {
        'total': len(meals),
        'usable': len(usable),
        'combo': sum(1 for m in meals if m['_d']['kind'] == 'combo'),
        'single': sum(1 for m in meals if m['_d']['kind'] == 'single'),
        'nonFood': sum(1 for m in meals if not m['_d']['isFood']),
        'nutritionApi': sum(1 for m in meals if m['_d']['nutritionSource'] == 'api'),
        'nutritionEstimated': sum(1 for m in meals if m['_d']['nutritionSource'] == 'estimated'),
        'nutritionNone': sum(1 for m in meals if m['nutrition'] is None),
        'roleMissing': sum(1 for m in meals if not m['_d']['role']),
        'usableByRole': dict(Counter(m['_d']['role'] for m in usable)),
        'saveKindCount': dict(Counter(m['_d']['saveKind'] for m in meals)),
        'discountTypes': dict(Counter(m['discountType'] for m in meals)),
        'nutritionRows': len(nutri),
    }

    catalog = {
        '_meta': {
            'storeCode': '1450713',
            'storeName': '上海黄浦华旭国际大厦',
            'orderType': 1,
            'beType': 1,
            'fetchedAt': '2026-10-24T13:31:48+08:00',
            'sources': ['query-meals', 'list-nutrition-foods'],
            'note': '顶层字段名与接口返回一致；本地推导结果统一放在 _d 里。'
                    'nutritionRows 接口声明 160 行，去重后 158（小杯玉米杯、纯牛奶(盒装) 各重复一次）。',
            'stats': stat,
        },
        'meals': meals,
        'nutritionTable': nutri,
        'coupons': load_json('coupons.json')['coupons'],
        'stores': load_json('stores.json')['stores'],
        'timeSlots': load_json('stores.json')['timeSlots'],
    }

    out_json = os.path.join(HERE, 'catalog.json')
    with open(out_json, 'w', encoding='utf-8') as f:
        json.dump(catalog, f, ensure_ascii=False, indent=1)

    out_js = os.path.join(HERE, 'catalog.js')
    with open(out_js, 'w', encoding='utf-8') as f:
        f.write('/* 自动生成，勿手改。源: data/build_catalog.py */\n')
        f.write('window.MCD_CATALOG = ')
        json.dump(catalog, f, ensure_ascii=False, separators=(',', ':'))
        f.write(';\n')

    print(json.dumps(stat, ensure_ascii=False, indent=1))
    print('\n写出:', out_json, os.path.getsize(out_json), 'bytes')
    print('写出:', out_js, os.path.getsize(out_js), 'bytes')

    print('\n=== 可用池（usable）按槽位 ===')
    for role in ('main', 'side', 'drink', 'extra'):
        rows = [m for m in usable if m['_d']['role'] == role]
        print(f'  {role:<6} {len(rows):>2} 个: ' + '、'.join(
            f"{m['name']}(¥{m['currentPrice']:g})" for m in rows[:8]) + (' …' if len(rows) > 8 else ''))

    print('\n=== 抽查 ===')
    for code in ('1440', '1100', '521952', '4810', '9900008751', '9900016566', '9900000890'):
        m = next(x for x in meals if x['code'] == code)
        n = m['nutrition'] or {}
        d = m['_d']
        print(f"  {m['name']:<18} ¥{m['currentPrice']:<6} 原¥{m['originalPrice']:<6} "
              f"省¥{d['saveAmount']:<6} {d['saveKind']:<11} {str(d['role']):<5} "
              f"{int(n.get('energyKcal') or 0)}kcal [{d['nutritionSource']}] "
              f"usable={d['usable']}")


if __name__ == '__main__':
    main()
