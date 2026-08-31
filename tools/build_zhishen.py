#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
生成「置身体 · 现象研究」话题页正文 tools/data/zhishen_body.html。

设计约定（与 alibaba / sunge 两个话题页完全一致）：
  · h1 = 篇目，h2 = 章节 —— reader.js 据此生成两级目录，sidebar 样式也只有两级
  · 只收录原文（或明确标注保真度的转述），不写分析、不编造正文
  · 每篇开头是元信息条（作者 / 归属 / 时间 / 保真度），结尾是来源校勘记

收录边界：
  缘起与回应各篇（《置身钉内》《置身钉外》《云空未必空》，以及阿里合伙人委员会
  的官方回应）已收录于「阿里巴巴 · 内网风暴」话题，本册不重复，只在年表中存目。
  本册只收浪潮扩散到其他企业之后的原文。

语料来源见 tools/data/zhishen_src/，改动语料后重跑本脚本即可。
"""
import html
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
SRC = "tools/data/zhishen_src"
OUT = "tools/data/zhishen_body.html"


def read(name):
    return open(os.path.join(SRC, name), encoding="utf-8").read()


def md_to_html(md_text):
    """markdown → html（去掉 frontmatter 与分隔线），失败时退回极简转换。"""
    md_text = re.sub(r"^---\n.*?\n---\n", "", md_text, count=1, flags=re.S)
    try:
        import markdown
        body = markdown.markdown(md_text, extensions=["extra", "sane_lists"])
    except ImportError:
        out, buf = [], []
        for line in md_text.split("\n"):
            if line.startswith("#"):
                if buf:
                    out.append("<p>" + "".join(buf) + "</p>")
                    buf = []
                lv = len(line) - len(line.lstrip("#"))
                out.append(f"<h{lv}>{line.lstrip('# ').strip()}</h{lv}>")
            elif line.strip():
                buf.append(html.escape(line.strip()))
        if buf:
            out.append("<p>" + "".join(buf) + "</p>")
        body = "\n".join(out)
    return body


def demote(h, frm, to):
    """把 h<frm> 变为 h<to>（用于把篇内标题统一到章节层级 h2）。"""
    return re.sub(rf"<h{frm}>", f"<h{to}>", re.sub(rf"</h{frm}>", f"</h{to}>", h))


def strip_blocks(h, startswith):
    """从 startswith 那个标题起，把后面的内容切出来返回 (前半, 后半)。"""
    for tag in ("h2", "h3", "h4"):
        m = re.search(rf"<{tag}>{re.escape(startswith)}", h)
        if m:
            return h[:m.start()], h[m.start():]
    return h, ""


def article(no, title, meta, body, note):
    """一篇原文的标准结构：篇目标题 h1 / 元信息条 / 正文 / 校勘记。"""
    badges = "".join(f'<span class="zp-badge">{b}</span>' for b in meta["badges"])
    return f'''        <h1 id="p{no}">{no}、{title}</h1>
        <div class="zp-meta">
            <span class="zp-who">{meta["who"]}</span>
            <span class="zp-when">{meta["when"]}</span>
            {badges}
        </div>
{body}
        <p class="zp-note">{note}</p>
'''


parts = []

# ---------------------------------------------------------------- 编者按
parts.append('''        <p class="zp-lead">2026 年 6 月起，一批大厂员工借用兰小欢《置身事内》的命名格式，写下以「置身 X 内」为题的职场长文，两个月内从钉钉扩散到美团、小米、字节、小红书，最后溢出互联网进入制造业。本册逐篇收录可核实的原文，按发表时间编排，不做评论、不作演绎；原文未完整公开的篇目，只保留可核实的事实与摘录，并如实标注保真度。</p>
        <p class="zp-lead">缘起之作《置身钉内》，以及由此引出的《置身钉外》《云空未必空》与阿里巴巴合伙人委员会的官方回应《有情有义有成长，才是阿里文化》，均已收录于本站<a href="../alibaba/">「阿里巴巴 · 内网风暴」</a>话题。本册不再重复，只呈现浪潮扩散到其他企业之后的原文。</p>
''')

# ---------------------------------------------------------------- 1 置身团内
tn = read("tuannei.html")
tn_body, tn_tail = strip_blocks(tn, "信息来源与说明")
tn_body = demote(tn_body, 3, 2)                        # 篇内章节统一到 h2
parts.append(article(
    1, "置身团内",
    {"who": "美团到餐基层产品经理（已离职）· 脉脉匿名帖",
     "when": "2026-06-22",
     "badges": ["原文全文", "约两千字"]},
    tn_body,
    "校勘记：原文首发于脉脉匿名帖，经新浪科技、快科技等转载，本页据公开存档版整理。美团官方未作公开回应。",
))

# ---------------------------------------------------------------- 2 置身米内
mi = md_to_html(read("zhishen_minei_original.md"))
mi_body, mi_tail = strip_blocks(mi, "补充说明")
mi_body = re.sub(r"<h1>.*?</h1>", "", mi_body, flags=re.S)     # 篇名交给 h1
mi_body = re.sub(r"\n{2,}", "\n", mi_body).strip()
mi_body = "\n".join("        " + ln if ln.strip() else ln for ln in mi_body.split("\n"))
parts.append(article(
    2, "置身米内",
    {"who": "小米前校招生（2024 届入职，已离职）",
     "when": "2026-06-23 发于小米内网，数小时后被删",
     "badges": ["完整版原文", "约四千字"]},
    mi_body,
    "校勘记：据小米内网流出、雪球等平台转发的完整版整理；另有存档 OCR 版本，个别段落字句略有出入，此处从完整版。小米官方未作公开回应。",
))

# ---------------------------------------------------------------- 3 置身抖内
dn = read("dounei.html")
dn = strip_blocks(dn, "信息来源与说明")[0]
dn = demote(dn, 3, 2)
parts.append(article(
    3, "置身抖内（置身 dou 内）",
    {"who": "字节跳动同事圈 · 脉脉短帖",
     "when": "2026-06-25 19:24",
     "badges": ["原帖摘录", "非长文"]},
    dn,
    "校勘记：此篇并非数千字长文，而是一条脉脉短帖与评论区摘录，是「置身 X 内」从长文退化为职场梗的切片。原帖发布于 2026-06-25 19:24:58，抓取时显示点赞 27、传播 43、评论 19（配图内评论数 67，来源自不同时间截屏）。截至 2026-08，脉脉原帖已被作者删除，本页据 2aran 存档与脉脉配图 OCR 整理，照录存档。",
))

# ---------------------------------------------------------------- 4 置身薯内
sn = read("shunei_full.html")
parts.append(article(
    4, "置身薯内",
    {"who": "小红书前校招程序员 · 脉脉「小红书前同事圈」",
     "when": "2026-07-08",
     "badges": ["原文全文", "约两千字"]},
    sn,
    "校勘记：原文以 5 页图文形式流传于脉脉，本页据截图逐段校对录入，并与两个独立转载来源交叉核对，文字一致。作者自述为理科生，写作时借助 AI 做过润色整理。小红书官方未作公开回应。",
))

# ---------------------------------------------------------------- 5 身在江湖
jh = md_to_html(read("zhishen_jianghu.md"))
jh = re.sub(r"<h1>.*?</h1>", "", jh, flags=re.S)
jh = re.sub(r"<blockquote>.*?</blockquote>", "", jh, flags=re.S)   # 去掉来源说明引用块
jh = re.sub(r"\n{2,}", "\n", jh).strip()
jh = "\n".join("        " + ln if ln.strip() else ln for ln in jh.split("\n"))
parts.append(article(
    5, "身在江湖",
    {"who": "D 司（深圳大疆创新）前员工",
     "when": "2026-07（微信私域首发）",
     "badges": ["原文全文", "标题变体"]},
    jh,
    "校勘记：原文首发于微信私域，标题用「身在江湖」而非「置身江湖」，与系列同源；本篇据原文截图逐段校对录入。",
))

# ---------------------------------------------------------------- 附录：年表
parts.append('''        <h1 id="p6">6、系列年表与保真度说明</h1>
        <div class="zp-table-wrap">
        <table>
            <thead><tr><th>时间</th><th>篇目</th><th>归属</th><th>收录情况</th></tr></thead>
            <tbody>
                <tr><td>06-04</td><td>置身钉内</td><td>钉钉</td><td>已收录，见「阿里巴巴 · 内网风暴」</td></tr>
                <tr><td>06-08</td><td>置身钉外</td><td>钉钉</td><td>已收录，见「阿里巴巴 · 内网风暴」</td></tr>
                <tr><td>06-10</td><td>有情有义有成长，才是阿里文化</td><td>阿里合伙人委员会</td><td>官方回应，见「阿里巴巴 · 内网风暴」</td></tr>
                <tr><td>06-11</td><td colspan="3">钉钉换帅：无招（陈航）卸任 CEO，陈宇森接棒</td></tr>
                <tr><td>06-12</td><td>云空未必空</td><td>钉钉</td><td>原文未公开，该话题内已存目</td></tr>
                <tr><td>06-22</td><td>置身团内</td><td>美团</td><td>本册 · 原文全文</td></tr>
                <tr><td>06-23</td><td>置身米内</td><td>小米</td><td>本册 · 完整版原文</td></tr>
                <tr><td>06-25</td><td>置身抖内</td><td>字节跳动</td><td>本册 · 原帖摘录</td></tr>
                <tr><td>07-08</td><td>置身薯内</td><td>小红书</td><td>本册 · 原文全文</td></tr>
                <tr><td>07（月内）</td><td>身在江湖</td><td>大疆</td><td>本册 · 原文全文</td></tr>
            </tbody>
        </table>
        </div>
        <p class="zp-note">说明：本册只做公开信息的汇编、校对与排版，不代表对文中任何事实的确认。文中观点均为作者个人陈述，涉事企业的回应以官方发布为准。</p>
''')

body = "\n".join(parts)
open(OUT, "w", encoding="utf-8").write(body)
print(f"{OUT}  {os.path.getsize(OUT)} bytes / {len(parts)} 段 / "
      f"h1×{body.count('<h1')} h2×{body.count('<h2')} h3×{body.count('<h3')}")
