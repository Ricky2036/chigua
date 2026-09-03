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
HOME_BODY = open(f"{DATA}/home_body.html", encoding="utf-8").read()
# 各话题的正文 / 主题覆盖由 build_topic_page() 按 slug 约定读取（tools/data/<slug>_body.html、
# <slug>_override.css），这里不硬编码任何具体话题，加话题时本文件不用改。

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
# 加新话题只需两步，不用改本文件：
#   1. 在下面的 TOPICS 里加一条
#   2. 往 tools/data/ 放两个文件：<slug>_body.html（必需）、<slug>_override.css（可选，主题色覆盖）
# 目录名 <slug> 就是访问路径，例如 slug="xyz" → /xyz/
#
# 注意：TOPICS[0] 是「源话题」，它的正文来自迁移快照（原始单文件页面），
# 其余话题都以它生成的页面为模板换掉正文。所以删除 TOPICS[0] 会让脚本失去模板来源。
TOPICS = [
    {
        "slug": "alibaba",
        "label": "阿里巴巴 · 内网风暴",      # 切换器标题
        "sub": "钉钉离职长文全编",           # 首页条目副标题
        "color": "#ff6b00",                 # 主题色（切换器圆点 + 首页卡片）
        "title": "阿里巴巴 · 内网风暴",      # 浏览器标签标题
        "kicker": "话 题 一",               # 首页条目眉标
        "desc": "2025 年阿里内网一篇离职长文引发的连锁反应。收录「置身钉内」「置身钉外」等 5 篇原文、官方回应与收官篇。",
        "tags": ["<b>5</b> 篇长文", "约 <b>8.9 万</b> 字", "含官方回应"],
    },
    {
        "slug": "zhishen",
        "label": "置身体 · 遍地开花",
        "sub": "大厂职场长文浪潮",
        "color": "#ff6b00",
        "title": "置身体 · 遍地开花",
        "kicker": "话 题 二",
        "desc": "2026 年夏天，从钉钉扩散到美团、小米、小红书与大疆的「置身 X 内」写作浪潮。本册收录阿里系之外的各家原文，标注保真度，不评论、不演绎；缘起与回应各篇见「阿里巴巴 · 内网风暴」。",
        "tags": ["<b>4</b> 篇原文", "<b>4</b> 家企业", "保真度标注", "系列年表"],
    },
    {
        "slug": "sunge",
        "label": "孙宇晨 · 我的女友景甜",
        "sub": "长文精校与事件全貌",
        "color": "#C0392B",
        "title": "孙宇晨 · 我的女友景甜",
        "kicker": "话 题 三",
        "desc": "2026 年孙宇晨发布的长文，以及事件双方表态、公开信息比对与时间线梳理；"
                "另按时间顺序收录赵长鹏、胡锡进、卢克文、孙宇晨的公开发言原文，逐字照录。",
        "tags": ["<b>4</b> 大板块", "约 <b>1.5 万</b> 字", "名物注释", "双方表态", "公众反馈原文"],
    },
]
SOURCE_TOPIC = TOPICS[0]      # 正文来自迁移快照的那个话题
SITE_NAME = "理性吃瓜"


def topic_card(t, idx):
    """首页话题「目录条目」（由 TOPICS 配置生成，不再手写 HTML）
    编号 01/02 按配置顺序自动排，增删话题不用另外维护。"""
    tags = "".join(f'<span>{x}</span>' for x in t["tags"])
    return (f'            <a href="./{t["slug"]}/" class="topic-row" style="--tc:{t["color"]}">\n'
            f'                <span class="tr-num">{idx + 1:02d}</span>\n'
            f'                <span class="tr-body">\n'
            f'                    <span class="tr-kicker">{t["kicker"]}<i>·</i>{t["sub"]}</span>\n'
            f'                    <h2>{t["label"]}</h2>\n'
            f'                    <p class="tr-desc">{t["desc"]}</p>\n'
            f'                    <span class="tr-meta">{tags}</span>\n'
            f'                </span>\n'
            f'                <span class="tr-arrow" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14"/><path d="m13 6 6 6-6 6"/></svg></span>\n'
            f'            </a>\n')


def topic_grid():
    """首页话题索引。注意：不带末尾换行，由 home_body.html 里占位符那一行提供。"""
    cards = [topic_card(t, i) for i, t in enumerate(TOPICS)]
    return '        <div class="topic-index">\n' + "\n".join(cards) + '        </div>'

def topic_switcher(current):
    """生成话题切换器（下拉面板）。current 为空表示在首页。"""
    items = []
    for t in TOPICS:
        cls = "topic-item current" if t["slug"] == current else "topic-item"
        items.append(
            f'<a href="../{t["slug"]}/" class="{cls}">'
            f'<span class="dot" style="background:{t["color"]}"></span>'
            f'<span class="txt">{t["label"]}</span></a>'
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
    cur = open(f"{SOURCE_TOPIC['slug']}/index.html", encoding="utf-8").read()
    assert "<main class=\"main-content\"" in cur, f"{SOURCE_TOPIC['slug']}/index.html 不是完整文章页"
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
    print(f"已快照 {SOURCE_TOPIC['slug']}/index.html → {SOURCE}（{len(cur)} 字符，已还原为自包含单文件）")
if not os.path.exists(SOURCE):
    sys.exit(f"缺少迁移输入快照 {SOURCE}\n请先执行：python3 tools/migrate.py --snapshot")
src = open(SOURCE, encoding="utf-8").read()
assert "<main class=\"main-content\"" in src, "快照不是完整文章页，拒绝继续"
# 页脚（site-footer）是站点装饰，不属于迁移正文，三个页面统一去掉
# （样式表里的 .site-footer 死规则无害，仅剥离 HTML 结构）
src = re.sub(r'\n?\s*<footer class="site-footer">.*?</footer>', "", src, count=1, flags=re.S)
assert '<footer class="site-footer">' not in src, "快照 footer 未剥离干净"
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


# ================================================================ 2. 源话题页
# 它的正文来自迁移快照（原始单文件页面），也是其余话题页的模板来源。
slug0 = SOURCE_TOPIC["slug"]
h = src
h = re.sub(r"<style[^>]*>.*?</style>", '<link rel="stylesheet" href="../assets/theme.css?v=20260903b">', h, count=1, flags=re.S)
# 只替换页面末尾那个主脚本（保留 body 开头的防闪烁内联脚本）
last = h.rfind("<script>")
h = h[:last] + '<script src="../assets/reader.js?v=20260903b"></script>\n</body>\n</html>\n'
h = re.sub(r'<link rel="icon"[^>]*>', lambda m: brand_favicon("../"), h, count=1)
h = re.sub(r'<img class="logo-icon"[^>]*>', lambda m: brand_img("../"), h, count=1)
# 标题：浏览器标签设置为话题标题
h = re.sub(r"<title>.*?</title>", lambda m: f"<title>{SOURCE_TOPIC['title']}</title>", h, count=1)
# 顶栏标题显示为该话题名称（与切换器一致）
h = re.sub(r'(<img class="logo-icon"[^>]*>\n\s+)[^\n<]+(\n\s*</div>)',
           lambda m: m.group(1) + SOURCE_TOPIC["label"] + m.group(2), h, count=1)
h = h.replace('<div class="controls">\n', '<div class="controls">\n' + topic_switcher(slug0), 1)

os.makedirs(slug0, exist_ok=True)
open(f"{slug0}/index.html", "w", encoding="utf-8").write(h)
print(f"{slug0}/index.html  {os.path.getsize(slug0 + '/index.html')} bytes")
assert '<style' not in h, "仍有内联 style"
assert len(re.findall(r'class="topic-item[^"]*current"', h)) == 1
assert SOURCE_TOPIC["label"] in h, f"{slug0} 顶栏标题未设置为话题名称"


# ================================================================ 3. 其余话题页
def empty_toc(x):
    """清空目录容器 → 交给 reader.js 按本页标题自动生成（否则会继承源话题的目录）"""
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


def replace_main(x, body):
    """用 body 换掉 <main class="main-content"> 的内容（标签栈精确定位结束位置）"""
    m = re.search(r'<main class="main-content"[^>]*>', x)
    start = m.end()
    tag_re = re.compile(r"<(/?)(main|div|section|article)\b[^>]*>")
    stack, end = [], None
    for t in tag_re.finditer(x, start):
        if t.group(1):
            if stack and stack[-1] == t.group(2):
                stack.pop()
            if not stack:
                end = t.start()   # finditer 返回的是绝对索引，不能再加 start
                break
        else:
            stack.append(t.group(2))
    return x[:start] + "\n" + body + "\n        " + x[end:]


def build_topic_page(tpl, cfg):
    """以源话题页为模板生成一个话题页。加新话题时不需要改这个函数。"""
    slug = cfg["slug"]
    body_path = f"{DATA}/{slug}_body.html"
    if not os.path.exists(body_path):
        raise SystemExit(f"缺少话题正文 {body_path}（新增话题时要在 tools/data/ 放这个文件）")
    body = open(body_path, encoding="utf-8").read()
    ovr_path = f"{DATA}/{slug}_override.css"
    ovr = open(ovr_path, encoding="utf-8").read() if os.path.exists(ovr_path) else None

    s = replace_main(tpl, body)
    s = empty_toc(s)

    # 主题色覆盖（可选：只覆盖 CSS 变量，公共样式不动）
    if ovr:
        # 必须用正则：模板里 href 带版本号（?v=20260903b），
        # 用 str.replace 精确匹配无版本号的串会「静默不命中」，
        # 结果是话题专属样式（.versus/.tl/.glossary/.anno 等）整块丢失且无任何报错。
        s, n = re.subn(r'<link rel="stylesheet" href="\.\./assets/theme\.css(?:\?[^"]*)?">',
                       lambda m: m.group(0) + "\n    <style>\n" + ovr + "\n    </style>",
                       s, count=1)
        assert n == 1, f"{slug}: 找不到 theme.css 引用，话题专属样式未注入（检查第 300 行写入的 href 写法）"
    # 图标不逐话题换色：三页共用 assets/brand.*（见 extract_brand_asset 注释）

    # 标题：浏览器标签保留话题区分；顶栏标题设置为本话题名称（与切换器一致）
    s = re.sub(r"<title>.*?</title>", lambda m: f"<title>{cfg['title']}</title>", s, count=1)
    mark = f"                {SOURCE_TOPIC['label']}\n"
    if mark not in s:
        raise SystemExit(f"{slug}: 模板里找不到顶栏标题（缩进变了？）→ {mark!r}")
    s = s.replace(mark, f"                {cfg['label']}\n", 1)

    # 切换器的 current 标记移到本话题
    for t in TOPICS:
        s = s.replace(f'<a href="../{t["slug"]}/" class="topic-item current">',
                      f'<a href="../{t["slug"]}/" class="topic-item">')
    s = s.replace(f'<a href="../{slug}/" class="topic-item">',
                  f'<a href="../{slug}/" class="topic-item current">')

    os.makedirs(slug, exist_ok=True)
    open(f"{slug}/index.html", "w", encoding="utf-8").write(s)

    assert len(re.findall(r'class="topic-item[^"]*current"', s)) == 1, f"{slug}: current 标记不唯一"
    toc_html = re.search(r'<div id="toc-container"\s*>(.*?)</div>\s*</aside>', s, re.S).group(1)
    assert "<a" not in toc_html, f"{slug}: 目录容器未清空（会继承源话题的目录）"
    assert re.search(r'<main class="main-content"[^>]*>.*</main>', s, re.S), f"{slug}: 正文 main 结构被破坏"
    assert 'src="../assets/reader.js' in s, f"{slug}: reader.js 引用丢失"
    print(f"{slug}/index.html  {os.path.getsize(slug + '/index.html')} bytes")
    return s


for cfg in TOPICS[1:]:
    build_topic_page(h, cfg)


# ================================================================ 4. 首页
home = '''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>理性吃瓜 · 原文汇编</title>
    <meta name="description" content="互联网公开长文的精校汇编：阿里钉钉内网离职长文全编、孙宇晨《我的女友景甜》精校版。">
    __FAVICON__
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Noto+Serif+SC:wght@400;700;900&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="./assets/theme.css?v=20260903b">
    <style>
        .back-to-top { box-shadow: 0 4px 14px rgba(26,26,46,.28); }
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
                理性吃瓜
            </div>
            <div class="controls">
                __SWITCHER__
            </div>
        </div>
    </div>

__HOME_BODY__

    <script src="./assets/reader.js?v=20260903b"></script>
</body>
</html>
'''
home = home.replace("__FAVICON__", brand_favicon("./"))
home = home.replace("__ICON__", brand_img("./"))
sw = topic_switcher(None).replace('href="../', 'href="./').replace('"../"', '"./"')
home = home.replace("__SWITCHER__", sw)
home = home.replace("__HOME_BODY__", HOME_BODY)
home = home.replace("__TOPIC_GRID__", topic_grid())   # 必须在 HOME_BODY 之后，占位符在它里面
open("index.html", "w", encoding="utf-8").write(home)
print(f"index.html（首页）  {os.path.getsize('index.html')} bytes")
assert len(re.findall(r'class="topic-item[^"]*current"', home)) == 1
assert "site-footer" not in home, "首页 footer 未删除"
for t in TOPICS:
    # 每个话题在首页出现两次：卡片 + 切换器
    assert home.count(f'href="./{t["slug"]}/"') == 2, f'首页链接数不对：{t["slug"]}'

print("\n全部生成完成。")
