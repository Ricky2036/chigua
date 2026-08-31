#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
把单文件页面 index.html 拆解为「公共资产 + 多话题目录」结构，并生成其余话题页。

用法（在仓库根目录执行）：
    python3 tools/migrate.py --snapshot   # 把 dingnei/index.html 存为迁移输入快照
    python3 tools/migrate.py              # 由快照重新生成全部页面

注意：快照 tools/data/dingnei_source.html 不入库（见 .gitignore）。
它只是迁移输入；日常改文章请直接改 dingnei/index.html，需要重建时再 --snapshot。


产出：
    assets/theme.css          公共样式 = 原内联 <style> + 多话题扩展组件
    assets/reader.js          公共脚本（加固版，含自动目录 / 话题切换器 / 内容保护）
    assets/brand.png          共享品牌图标（从源抽取，降采样到 128px，三页共用）
    dingnei/index.html        原文章（内容零改动，仅外链化 + 加话题切换器）
    sunyuchen/index.html      话题二：我的女友景甜
    index.html                话题首页

图标处理：形状/配色一律从源文件抽取，脚本不写死任何图标造型。
上游换图标后只需两步重放：python3 tools/migrate.py --snapshot && python3 tools/migrate.py
"""
import base64
import os
import re
import shutil
import urllib.parse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)

DATA = "tools/data"
# 公共资产（assets/）是唯一真源；tools/data/ 只放「话题专属内容」和「公共样式的扩展段」，
# 避免同一份 reader.js 存两处、日后改一处忘一处。
CSS_EXT = open(f"{DATA}/theme_ext.css", encoding="utf-8").read()
SUNY_BODY = open(f"{DATA}/sunyuchen_body.html", encoding="utf-8").read()
SUNY_OVR = open(f"{DATA}/sunyuchen_override.css", encoding="utf-8").read()
HOME_BODY = open(f"{DATA}/home_body.html", encoding="utf-8").read()

# ---------------------------------------------------------------- 品牌图标（源驱动）
# 设计原则：图标的「形状」与「配色」一律从源文件抽取，脚本只负责
#   1) 抽成共享资产 assets/brand.{ext}
#   2) 按页面深度拼对相对路径
# 为什么这样改：
#   · 品牌方已换过多次图标概念（对话气泡 → 机密档案 → 3D 黏土咖啡杯），
#     把形状写死在脚本里，每换一次就得改代码；源驱动后只需重放 --snapshot + 重跑。
#   · 图标原始 PNG 512×512 约 347KB，转 base64 后单页内联两份（logo + favicon）
#     ≈ 925KB，三个话题页就是 2.8MB。抽成共享文件后全站只需一份。
# 注：图标本身是暖调米褐色咖啡杯（非品牌橙色），逐话题换色会变成「红色咖啡杯」，
#     因此三页共用同一张；话题区分交给各页的 CSS 变量 --brand。
BRAND_SIZE = 128          # .logo-icon 实际渲染 26px，128 足够 4x 屏
BRAND_INFO = {}           # {"ext": "png"/"svg", "path": "assets/brand.png"}


def _downscale(raw, size):
    """把图标降到 size×size。Pillow 不可用时原样返回，不阻断构建。"""
    import io as _io
    try:
        from PIL import Image
    except ImportError:
        return raw, None
    try:
        im = Image.open(_io.BytesIO(raw))
        if max(im.size) <= size:
            return raw, im.size          # 已够小，原样保留（保证多轮重建字节稳定）
        im = im.resize((size, size), Image.LANCZOS)
        buf = _io.BytesIO()
        im.save(buf, "PNG", optimize=True)
        return buf.getvalue(), im.size
    except Exception as e:
        print(f"  (图标降采样失败，改用原图：{e})")
        return raw, None


def extract_brand_asset(src):
    """从源文件抽取品牌图标 → assets/brand.{ext}，返回该文件相对仓库根的路径。"""
    import base64
    os.makedirs("assets", exist_ok=True)
    # 1) 光栅图（data URI）
    m = re.search(r'<img class="logo-icon" src="data:image/(png|gif|jpeg|jpg);base64,([^"]+)"', src)
    if m:
        ext = "jpg" if m.group(1) in ("jpeg", "jpg") else m.group(1)
        raw = base64.b64decode(m.group(2))
        out, size = _downscale(raw, BRAND_SIZE)
        name = f"assets/brand.{'jpg' if ext == 'jpg' else 'png'}"
        open(name, "wb").write(out)
        dim = f"{size[0]}×{size[1]}" if size else "原尺寸"
        print(f"{name}  {os.path.getsize(name)} bytes"
              f"（源 {len(raw)} B / {dim} → {BRAND_SIZE}px，节省 {100 - os.path.getsize(name) * 100 // max(len(raw), 1)}%）")
        BRAND_INFO.update(ext=os.path.splitext(name)[1].lstrip("."), path=name)
        return name
    # 2) 内联 SVG（历史版本形态，保留兼容）
    m = re.search(r'<svg class="logo-icon".*?</svg>', src, re.S)
    if m:
        name = "assets/brand.svg"
        open(name, "w", encoding="utf-8").write(m.group(0))
        print(f"{name}  {os.path.getsize(name)} bytes（内联 SVG 原样抽出）")
        BRAND_INFO.update(ext="svg", path=name)
        return name
    raise SystemExit("源文件中找不到品牌图标（既无 data URI 也无内联 svg.logo-icon）")


def brand_img(rel):
    """.logo-icon 的 <img> 标签。rel 是页面到仓库根的相对路径（'../' 或 './'）"""
    return f'<img class="logo-icon" src="{rel}{BRAND_INFO["path"]}" alt="Logo">'


def brand_favicon(rel):
    ext = BRAND_INFO["ext"]
    mime = "image/svg+xml" if ext == "svg" else ("image/jpeg" if ext == "jpg" else f"image/{ext}")
    return f'<link rel="icon" type="{mime}" href="{rel}{BRAND_INFO["path"]}">'


BRAND_ASSET_CANDIDATES = ("assets/brand.png", "assets/brand.jpg", "assets/brand.svg")


def brand_data_uri():
    """把共享图标文件还原成 data URI，供 --snapshot 反向使用（保证往返无损）。"""
    path = next((c for c in BRAND_ASSET_CANDIDATES if os.path.exists(c)), None)
    if not path:
        raise SystemExit("找不到共享图标资产 assets/brand.*，无法生成快照")
    ext = os.path.splitext(path)[1].lstrip(".")
    if ext == "svg":
        return "data:image/svg+xml," + urllib.parse.quote(
            open(path, encoding="utf-8").read()), "image/svg+xml"
    mime = "image/jpeg" if ext == "jpg" else "image/png"
    return "data:" + mime + ";base64," + base64.b64encode(open(path, "rb").read()).decode(), mime


# ---------------------------------------------------------------- 话题配置
TOPICS = [
    {"slug": "dingnei",   "label": "阿里巴巴 · 内网风暴", "sub": "钉钉离职长文全编", "color": "#ff6b00"},
    {"slug": "sunyuchen", "label": "孙宇晨 · 我的女友景甜", "sub": "长文精校与事件全貌", "color": "#C0392B"},
]

def topic_switcher(current):
    """生成话题切换器（下拉面板）。current 为空表示在首页。"""
    items = []
    for t in TOPICS:
        cls = "topic-item current" if t["slug"] == current else "topic-item"
        items.append(
            f'<a href="../{t["slug"]}/" class="{cls}">'
            f'<span class="dot" style="background:{t["color"]}"></span>'
            f'<span class="txt">{t["label"]}<span class="sub">{t["sub"]}</span></span></a>'
        )
    home_cls = "topic-item home current" if not current else "topic-item home"
    return f'''            <!-- topic-switch:begin -->
            <div class="topic-switch">
                <button class="btn icon-btn" id="topicToggle" title="切换话题" aria-label="切换话题">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/></svg>
                </button>
                <div class="topic-dropdown" id="topicDropdown">
                    <div class="dd-label">全 部 话 题</div>
                    {"".join(items)}
                    <div class="dd-sep"></div>
                    <a href="../" class="{home_cls}"><span class="dot" style="background:var(--ink)"></span><span class="txt">返回话题首页</span></a>
                </div>
            </div>
            <!-- topic-switch:end -->
'''


# ================================================================ 1. 抽资产
# 源文章单独存快照，避免脚本把生成出来的首页当成输入（重要：本脚本必须幂等）
import sys
SOURCE = f"{DATA}/dingnei_source.html"
if "--snapshot" in sys.argv:
    cur = open("dingnei/index.html", encoding="utf-8").read()
    assert "<main class=\"main-content\"" in cur, "dingnei/index.html 不是完整文章页"
    full_css = open("assets/theme.css", encoding="utf-8").read()
    assert full_css.endswith(CSS_EXT), "assets/theme.css 结尾不是扩展段，无法反推基础样式"
    base = full_css[: len(full_css) - len(CSS_EXT)].strip()
    rjs = open("assets/reader.js", encoding="utf-8").read()
    # 1) 去掉话题切换器（重建时会重新插入）
    cur = re.sub(r"[ \t]*<!-- topic-switch:begin -->\n.*?[ \t]*<!-- topic-switch:end -->\n", "", cur, count=1, flags=re.S)
    # 2) 外链 CSS/JS 还原为内联
    # 注意：替换串里含反斜杠（CSS content 转义、JS 正则 \s 等），必须用 lambda 避免被当转义解析
    cur = re.sub(r'<link rel="stylesheet" href="\.\./assets/theme\.css">',
                 lambda m: "<style>\n" + base + "\n</style>", cur, count=1)
    cur = re.sub(r'<script src="\.\./assets/reader\.js"></script>',
                 lambda m: "<script>\n" + rjs + "\n    </script>", cur, count=1)
    # 3) 共享图标还原为内联 data URI（否则下一轮会把 128px 图再当源，且快照不自包含）
    uri, mime = brand_data_uri()
    cur = re.sub(r'<img class="logo-icon" src="[^"]*assets/brand\.(?:png|jpg|svg)"[^>]*>',
                 lambda m: f'<img class="logo-icon" src="{uri}" alt="Logo">', cur, count=1)
    cur = re.sub(r'<link rel="icon"[^>]*href="[^"]*assets/brand\.(?:png|jpg|svg)"[^>]*>',
                 lambda m: f'<link rel="icon" type="{mime}" href="{uri}">', cur, count=1)
    assert "<style" in cur, "快照还原失败：未变回自包含单文件"
    assert "assets/reader.js" not in cur and "assets/brand." not in cur, \
        "快照还原失败：仍残留在 assets/ 的外链引用"
    open(SOURCE, "w", encoding="utf-8").write(cur)
    print(f"已快照 dingnei/index.html → {SOURCE}（{len(cur)} 字符，已还原为自包含单文件）")
if not os.path.exists(SOURCE):
    sys.exit(f"缺少迁移输入快照 {SOURCE}\n请先执行：python3 tools/migrate.py --snapshot")
src = open(SOURCE, encoding="utf-8").read()
assert "<main class=\"main-content\"" in src, "快照不是完整文章页，拒绝继续"
style = re.findall(r"<style[^>]*>(.*?)</style>", src, re.S)[0]
scripts = re.findall(r"<script>(.*?)</script>", src, re.S)
main_js = scripts[-1]

os.makedirs("assets", exist_ok=True)
THEME_BASE = style.strip()
open("assets/theme.css", "w", encoding="utf-8").write(THEME_BASE + "\n\n" + CSS_EXT)
extract_brand_asset(src)

# reader.js 是「抽取 + 人工加固」的产物，原地不动，只校验它的功能段落仍在
READER_JS = open("assets/reader.js", encoding="utf-8").read()

# 校验：加固版 reader.js 的基础部分应与原脚本一致（加固只加空值守卫和追加函数）
BASE_MARK = "// Smart Table Column Alignment"
if BASE_MARK not in main_js or BASE_MARK not in READER_JS:
    print("!! 警告：reader.js 与原脚本结构差异较大，请人工核对")
else:
    # 加固版只做「加空值守卫 + 追加函数」，不做逻辑改动；
    # 这里抽查主脚本的大块逻辑是否仍原样保留（守卫改动会让前缀匹配提前中断，属正常）
    kept = sum(1 for seg in [
        "Wrap tables for responsive scrolling",
        "Smart Table Column Alignment",
        "Scroll Spy for TOC",
        "Back to Top",
        "Lightbox for Images",
        "Security & Anti-Scraping Measures",
        "Mobile TOC Toggle",
    ] if seg in main_js and seg in READER_JS)
    print(f"reader.js 功能模块保留: {kept}/7（加固版={{守卫 + 自动目录 + 话题切换器}}）")

print(f"assets/theme.css  {os.path.getsize('assets/theme.css')} bytes")
print(f"assets/reader.js  {os.path.getsize('assets/reader.js')} bytes")


# ================================================================ 2. dingnei
h = src
h = re.sub(r"<style[^>]*>.*?</style>", '<link rel="stylesheet" href="../assets/theme.css">', h, count=1, flags=re.S)
# 只替换页面末尾那个主脚本（保留 body 开头的防闪烁内联脚本）
last = h.rfind("<script>")
h = h[:last] + '<script src="../assets/reader.js"></script>\n</body>\n</html>\n'
h = re.sub(r'<link rel="icon"[^>]*>', lambda m: brand_favicon("../"), h, count=1)
h = re.sub(r'<img class="logo-icon"[^>]*>', lambda m: brand_img("../"), h, count=1)
h = h.replace('<div class="controls">\n', '<div class="controls">\n' + topic_switcher("dingnei"), 1)

os.makedirs("dingnei", exist_ok=True)
open("dingnei/index.html", "w", encoding="utf-8").write(h)
print(f"dingnei/index.html  {os.path.getsize('dingnei/index.html')} bytes")
assert '<style' not in h, "仍有内联 style"
assert len(re.findall(r'class="topic-item[^"]*current"', h)) == 1


# ================================================================ 3. sunyuchen
s = h
# 3.1 正文
m = re.search(r'<main class="main-content"[^>]*>', s)
start = m.end()
tag_re = re.compile(r"<(/?)(main|div|section|article)\b[^>]*>")
stack, end = [], None
for t in tag_re.finditer(s, start):
    if t.group(1):
        if stack and stack[-1] == t.group(2):
            stack.pop()
        if not stack:
            end = t.start()   # finditer 返回的是绝对索引，不能再加 start
            break
    else:
        stack.append(t.group(2))
s = s[:start] + "\n" + SUNY_BODY + "\n        " + s[end:]

# 3.2 目录容器清空 → reader.js 自动生成
def empty_toc(x):
    mm = re.search(r'<div id="toc-container"\s*>', x)
    if not mm:
        return x
    st = mm.end()
    tg = re.compile(r"<(/?)(div|ul|li|a)\b[^>]*>")
    depth, ed = 0, None
    for t in tg.finditer(x, st):
        if t.group(1):
            depth -= 1
            if depth == 0:
                ed = t.end()
                break
        else:
            depth += 1
    return (x[:st] + "\n            \n            " + x[ed:]) if ed else x

s = empty_toc(s)

# 3.3 主题覆盖 + 图标换色
s = s.replace('<link rel="stylesheet" href="../assets/theme.css">',
              '<link rel="stylesheet" href="../assets/theme.css">\n    <style>\n' + SUNY_OVR + "\n    </style>", 1)
# 图标不再逐话题换色：三页共用 assets/brand.*（见 extract_brand_asset 注释）
s = s.replace("<title>大厂八卦 · 阿里巴巴</title>", "<title>大厂八卦 · 我的女友景甜</title>")
s = s.replace("                大厂八卦 · 阿里巴巴\n", "                大厂八卦 · 我的女友景甜\n")
s = s.replace('<a href="../dingnei/" class="topic-item current">', '<a href="../dingnei/" class="topic-item">')
s = s.replace('<a href="../sunyuchen/" class="topic-item">', '<a href="../sunyuchen/" class="topic-item current">')

os.makedirs("sunyuchen", exist_ok=True)
open("sunyuchen/index.html", "w", encoding="utf-8").write(s)
print(f"sunyuchen/index.html  {os.path.getsize('sunyuchen/index.html')} bytes")
assert len(re.findall(r'class="topic-item[^"]*current"', s)) == 1
toc_html = re.search(r'<div id="toc-container"\s*>(.*?)</div>\s*</aside>', s, re.S).group(1)
assert "<a" not in toc_html, "目录容器未清空（会继承上一篇的目录）"
assert re.search(r'<main class="main-content"[^>]*>.*</main>', s, re.S), "正文 main 结构被破坏"
assert 'src="../assets/reader.js"' in s, "reader.js 引用丢失"


# ================================================================ 4. 首页
home = '''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>大厂八卦 · 原文汇编</title>
    <meta name="description" content="互联网公开长文的精校汇编：阿里钉钉内网离职长文全编、孙宇晨《我的女友景甜》精校版。">
    __FAVICON__
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Noto+Serif+SC:wght@400;700;900&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="./assets/theme.css">
    <style>
        .back-to-top { box-shadow: 0 4px 14px rgba(26,26,46,.28); }
        .footer-divider { background: linear-gradient(90deg, #ff6b00, #C0392B); width: 56px; }
    </style>
</head>
<body>
    <script>
        (function(){
            var font = localStorage.getItem('pref-font');
            if (font === 'serif') document.body.classList.add('font-serif');
            var size = localStorage.getItem('pref-size');
            if (size && size !== 'medium') document.body.classList.add('size-' + size);
            var width = localStorage.getItem('pref-width');
            if (width && width !== 'medium') document.body.classList.add('width-' + width);
        })();
    </script>
    <div class="mobile-overlay" id="mobileOverlay"></div>
    <div id="progress-container"><div id="progress-bar"></div></div>

    <div class="topbar">
        <div class="topbar-inner">
            <div class="logo">
                __ICON__
                大厂八卦
            </div>
            <div class="controls">
                __SWITCHER__
            </div>
        </div>
    </div>

__HOME_BODY__
    <footer class="site-footer">
        <div class="footer-divider"></div>
        <p>本文内容来源于网络公开资料，仅供学习交流使用</p>
        <p style="margin-top: 6px; opacity: 0.7;">Lovingly typeset · 2026</p>
    </footer>

    <script src="./assets/reader.js"></script>
</body>
</html>
'''
home = home.replace("__FAVICON__", brand_favicon("./"))
home = home.replace("__ICON__", brand_img("./"))
sw = topic_switcher(None).replace('href="../', 'href="./').replace('"../"', '"./"')
home = home.replace("__SWITCHER__", sw)
home = home.replace("__HOME_BODY__", HOME_BODY)
open("index.html", "w", encoding="utf-8").write(home)
print(f"index.html（首页）  {os.path.getsize('index.html')} bytes")
assert len(re.findall(r'class="topic-item[^"]*current"', home)) == 1
assert home.count('href="./dingnei/"') == 2, "首页话题卡片/切换器链接数不对"

print("\n全部生成完成。")
