# -*- coding: utf-8 -*-
"""Проверка целостности страницы перед публикацией.
Ловит то, на чём мы уже обжигались: задвоенные блоки, битую вёрстку,
разъехавшийся CSS и невидимые заголовки."""
import io, re, sys, collections
from html.parser import HTMLParser

PAGE = 'index.html'
s = io.open(PAGE, encoding='utf-8').read()
errors, warns = [], []

# ---------- 1. вёрстка ----------
VOID = {'img','br','hr','meta','link','input','source','path','use','circle','rect',
        'area','col','embed','track','wbr','polygon','stop','animate'}
SKIP = {'svg','defs','lineargradient','radialgradient','g','text','textpath'}
class P(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True); self.st=[]; self.bad=[]
    def handle_starttag(self, t, a):
        if t in VOID or t in SKIP: return
        self.st.append((t, self.getpos()[0]))
    def handle_endtag(self, t):
        if t in VOID or t in SKIP: return
        if not self.st: return
        if self.st[-1][0] == t: self.st.pop(); return
        for i in range(len(self.st)-1, -1, -1):
            if self.st[i][0] == t: del self.st[i:]; return
        self.bad.append((t, self.getpos()[0]))
body = s[s.index('</style>')+8 : s.rindex('\n<script>')]
p = P(); p.feed(body)
for t, line in p.bad:
    errors.append(f'лишний </{t}> в разметке')

# ---------- 2. задвоенные блоки ----------
counts = collections.Counter(re.findall(r'<section class="([a-z-]+)"', body))
for k, v in counts.items():
    if v > 1: errors.append(f'секция .{k} встречается {v} раза')
for tag, name in [('<header class="hero">','первый экран'), ('<footer class="ftr">','футер'),
                  ('<div class="nav-wrap">','навигация'), ('<div class="topbar"','верхняя строка'),
                  ('<div class="cookie"','уведомление')]:
    n = body.count(tag)
    if n != 1: errors.append(f'{name}: блоков {n}, ожидался 1')

# ---------- 3. CSS ----------
css = s[s.index('<style>')+7 : s.index('</style>')]
depth = 0
for ch in css:
    depth += 1 if ch == '{' else (-1 if ch == '}' else 0)
if depth: errors.append(f'скобки в CSS не сходятся: {depth}')
# селектор, в который затесался комментарий, — признак склейки правил
for m in re.findall(r'[^{}\n]*/\*[^*]*\*/[^{}\n]*\{', css):
    errors.append('склеены правила: ' + m.strip()[:60])
# вырезаем блоки @media/@supports/@keyframes, в том числе вложенные друг в друга
top = re.sub(r'@(?:media|keyframes|supports)[^{]*\{(?:[^{}]|\{(?:[^{}]|\{[^{}]*\})*\})*\}', '', css)
sel = collections.Counter(r.strip() for r in re.findall(r'([^{}]+)\{[^{}]*\}', top) if r.strip())
for k, v in sel.items():
    if v > 1 and k not in ('.btn', '@font-face'):
        warns.append(f'селектор {k[:50]} объявлен {v} раза')

# ---------- 4. скрипты целы ----------
js = s[s.rindex('\n<script>'):]
for frag, name in [("var splitSel='.book-title", 'разбор заголовков на слова'),
                   ('IntersectionObserver', 'наблюдатель проявления'),
                   ("getElementById('cookie')", 'уведомление о cookie'),
                   ("querySelector('.rv-track')", 'слайдер отзывов')]:
    if frag not in js: errors.append(f'скрипт повреждён: {name}')
if js.count('function(){') < 5: errors.append('скриптов подозрительно мало')

# ---------- 5. заголовки не должны быть спрятаны ----------
for sel_name in ['t-display', 'book-title', 'about-title', 'consult-h', 'quote-t', 'tg-title']:
    m = re.search(r'^[^{\n]*\.' + sel_name + r'\b[^{\n]*\{([^}]*)\}', css, re.M)
    if m and ('visibility:hidden' in m.group(1) or 'position:fixed' in m.group(1)):
        errors.append(f'.{sel_name} получил стили всплывающего окна')

# ---------- итог ----------
print(f'страница: {len(s)//1024} КБ, секций {sum(counts.values())}')
for w in warns: print('  ! ' + w)
if errors:
    print('\nОШИБКИ:')
    for e in errors: print('  ✗ ' + e)
    sys.exit(1)
print('\nвсё чисто — можно публиковать')
