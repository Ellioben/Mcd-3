#!/usr/bin/env python3
"""把 catalog.json 里全部 SKU 图片下载到 data/img/{code}.png。

- 命中即落盘，文件存在且非空则跳过（可反复跑，增量补漏）。
- 回退链与页面 imgNext 一致：原日期目录 → ProductPool → 20260824。
- 产出 data/img/_manifest.json：每个 code 的最终命中的 URL 与结果。
"""
import json
import os
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
CATALOG = os.path.join(HERE, 'catalog.json')
IMG_DIR = os.path.join(HERE, 'img')

UA = {'User-Agent': 'Mozilla/5.0', 'Referer': 'https://www.mcdonalds.com.cn/'}


def candidates(url):
    """原 URL + 两个替代日期目录，去重保序。"""
    import re
    out = [url]
    m = re.search(r'/(\d{8})/product/', url)
    if m:
        out.append(re.sub(r'/\d{8}/product/', '/ProductPool/product/', url))
        out.append(re.sub(r'/\d{8}/product/', '/20260824/product/', url))
    return [u for i, u in enumerate(out) if u and u not in out[:i]]


def fetch(url, dest):
    for u in candidates(url):
        try:
            req = urllib.request.Request(u, headers=UA)
            with urllib.request.urlopen(req, timeout=15) as r:
                data = r.read()
            if data and len(data) > 1000:  # 真图片至少几 KB；404 页面很小
                with open(dest, 'wb') as f:
                    f.write(data)
                return u, len(data)
        except Exception:
            continue
    return None, 0


def main():
    with open(CATALOG, encoding='utf-8') as f:
        cat = json.load(f)
    os.makedirs(IMG_DIR, exist_ok=True)
    manifest_path = os.path.join(IMG_DIR, '_manifest.json')
    manifest = {}
    if os.path.exists(manifest_path):
        with open(manifest_path, encoding='utf-8') as f:
            manifest = json.load(f)

    ok = miss = skip = 0
    missed = []
    for meal in cat['meals']:
        code, url = meal.get('code'), meal.get('image')
        if not code or not url:
            continue
        ext = '.png' if '.png' in url.lower() else '.jpg'
        dest = os.path.join(IMG_DIR, code + ext)
        if os.path.exists(dest) and os.path.getsize(dest) > 1000:
            skip += 1
            manifest.setdefault(code, {'file': code + ext, 'status': 'cached'})
            continue
        hit, size = fetch(url, dest)
        if hit:
            ok += 1
            manifest[code] = {'file': code + ext, 'status': 'ok', 'url': hit, 'size': size}
        else:
            miss += 1
            missed.append((code, meal.get('name'), url))
            manifest[code] = {'file': code + ext, 'status': 'miss', 'url': url}

    with open(manifest_path, 'w', encoding='utf-8') as f:
        json.dump(manifest, f, ensure_ascii=False, indent=1)
    print(json.dumps({'downloaded': ok, 'skipped': skip, 'missed': miss}, ensure_ascii=False))
    for code, name, url in missed:
        print(f"  MISS {code} {name} {url}", file=sys.stderr)


if __name__ == '__main__':
    main()
