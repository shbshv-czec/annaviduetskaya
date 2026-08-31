# -*- coding: utf-8 -*-
"""Обновляет число просмотров у роликов на странице. Запускается раз в сутки."""
import re, io, json, urllib.request

PAGE = 'index.html'

def fetch(vid):
    req = urllib.request.Request(
        f'https://www.youtube.com/watch?v={vid}',
        headers={'User-Agent': 'Mozilla/5.0', 'Accept-Language': 'ru'})
    html = urllib.request.urlopen(req, timeout=30).read().decode('utf-8', 'ignore')
    m = re.search(r'"viewCount":"(\d+)"', html)
    return int(m.group(1)) if m else None

def fmt(n):
    if n >= 1_000_000:
        v = n / 1_000_000
        head = f'{v:.1f}'.replace('.', ',') if v < 10 else str(round(v))
        return head + ' млн просмотров'
    if n >= 1000:
        v = n / 1000
        head = f'{v:.1f}'.replace('.', ',') if v < 10 else str(round(v))
        return head + ' тыс. просмотров'
    last, two = n % 10, n % 100
    word = 'просмотров' if two in range(11, 15) or last == 0 or last >= 5 else ('просмотр' if last == 1 else 'просмотра')
    return f'{n} {word}'

s = io.open(PAGE, encoding='utf-8').read()
changed = 0
for vid in sorted(set(re.findall(r'data-vid="([A-Za-z0-9_-]+)"', s))):
    try:
        n = fetch(vid)
    except Exception as e:
        print(f'{vid}: ошибка запроса — {e}'); continue
    if not n:
        print(f'{vid}: счётчик не найден'); continue
    new = fmt(n)
    pat = re.compile(r'(<p class="pc-views" data-vid="' + re.escape(vid) + r'">)(.*?)(</p>)')
    m = pat.search(s)
    if m and m.group(2) != new:
        s = pat.sub(lambda mm: mm.group(1) + new + mm.group(3), s, count=1)
        changed += 1
        print(f'{vid}: {m.group(2)} -> {new}')
    else:
        print(f'{vid}: без изменений ({new})')

if changed:
    io.open(PAGE, 'w', encoding='utf-8').write(s)
print(f'обновлено роликов: {changed}')
