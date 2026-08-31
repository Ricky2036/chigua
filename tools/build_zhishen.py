#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
生成「置身体 · 遍地开花」话题页正文 tools/data/zhishen_body.html。

设计约定：
  · h1 = 篇目，h2 = 章节 —— reader.js 据此生成两级目录，sidebar 样式也只有两级
  · 只收录原文（或明确标注保真度的转述），不写分析、不编造正文
  · 每篇开头是元信息条（作者 / 归属 / 时间 / 保真度），结尾是来源校勘记
  · 美团篇：二级标题为 第一个奇观 / 第二个奇观 / 第三个奇观 / 百因皆有果，正文完整保留原文表述。
  · 小米篇 / 大疆篇 / 薯内篇：严格精细分段，结构化列表排版。
"""
import html
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
SRC = "tools/data/zhishen_src"
OUT = "tools/data/zhishen_body.html"


def read(name):
    path = os.path.join(SRC, name)
    if os.path.exists(path):
        return open(path, encoding="utf-8").read()
    return ""


def parse_markdown_blocks(md_text):
    """
    高保真轻量 Markdown 解析器：
    - 精确按空行划分段落 <p>，单行自然段均作为独立 <p>
    - 列表支持多行与松散列表（跳过空行保持同一个 <ol>/<ul>），杜绝断裂成多个孤立 <ol>
    - 标题 # / ## / ###
    - 引用 >
    - 行内 **加粗**
    """
    # 去除 yaml frontmatter
    md_text = re.sub(r"^---\n.*?\n---\n", "", md_text, count=1, flags=re.S)
    
    # 统一换行
    md_text = md_text.replace("\r\n", "\n")
    
    # 按行扫描
    lines = md_text.split("\n")
    html_out = []
    
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if not line:
            i += 1
            continue
        
        # 标题处理
        if line.startswith("#"):
            lv = len(line) - len(line.lstrip("#"))
            htext = line.lstrip("# ").strip()
            htext = re.sub(r"\*\*(.*?)\*\*", r"<strong>\1</strong>", htext)
            html_out.append(f"<h{lv}>{htext}</h{lv}>")
            i += 1
            continue
            
        # 引用块处理
        if line.startswith(">"):
            quote_lines = []
            while i < len(lines) and (lines[i].strip().startswith(">") or (lines[i].strip() and not lines[i].strip().startswith("#"))):
                curr = lines[i].strip()
                if curr.startswith(">"):
                    curr = re.sub(r"^>\s*", "", curr)
                quote_lines.append(curr)
                i += 1
                if i < len(lines) and not lines[i].strip():
                    break
            qcontent = " ".join(quote_lines).strip()
            qcontent = re.sub(r"\*\*(.*?)\*\*", r"<strong>\1</strong>", qcontent)
            html_out.append(f"<blockquote>{qcontent}</blockquote>")
            continue
            
        # 有序列表（支持跨空行的连续条目）
        if re.match(r"^\d+\.\s", line):
            items = []
            while i < len(lines):
                curr = lines[i].strip()
                if not curr:
                    # 窥探后续非空行是否依然为数字列表项
                    j = i + 1
                    has_more = False
                    while j < len(lines):
                        if not lines[j].strip():
                            j += 1
                            continue
                        if re.match(r"^\d+\.\s", lines[j].strip()):
                            has_more = True
                        break
                    if has_more:
                        i = j
                        continue
                    else:
                        break

                m = re.match(r"^\d+\.\s*(.*)", curr)
                if m:
                    item_text = m.group(1)
                    item_text = re.sub(r"\*\*(.*?)\*\*", r"<strong>\1</strong>", item_text)
                    items.append(f"<li>{item_text}</li>")
                elif items and not curr.startswith("#"):
                    items[-1] = items[-1][:-5] + "<br>" + re.sub(r"\*\*(.*?)\*\*", r"<strong>\1</strong>", curr) + "</li>"
                else:
                    break
                i += 1
            if items:
                html_out.append(f'<ol class="zp-list">\n' + "\n".join(items) + "\n</ol>")
            continue

        # 无序列表（支持跨空行的连续条目）
        if line.startswith("- ") or line.startswith("* "):
            items = []
            while i < len(lines):
                curr = lines[i].strip()
                if not curr:
                    j = i + 1
                    has_more = False
                    while j < len(lines):
                        if not lines[j].strip():
                            j += 1
                            continue
                        if lines[j].strip().startswith("- ") or lines[j].strip().startswith("* "):
                            has_more = True
                        break
                    if has_more:
                        i = j
                        continue
                    else:
                        break

                m = re.match(r"^[-*]\s*(.*)", curr)
                if m:
                    item_text = m.group(1)
                    item_text = re.sub(r"\*\*(.*?)\*\*", r"<strong>\1</strong>", item_text)
                    items.append(f"<li>{item_text}</li>")
                elif items and not curr.startswith("#"):
                    items[-1] = items[-1][:-5] + "<br>" + re.sub(r"\*\*(.*?)\*\*", r"<strong>\1</strong>", curr) + "</li>"
                else:
                    break
                i += 1
            if items:
                html_out.append(f'<ul class="zp-list">\n' + "\n".join(items) + "\n</ul>")
            continue

        # 普通自然段落（单段收集）
        p_lines = []
        while i < len(lines):
            curr = lines[i].strip()
            if not curr:
                break
            if curr.startswith("#") or curr.startswith(">") or re.match(r"^\d+\.\s", curr) or curr.startswith("- ") or curr.startswith("* "):
                break
            p_lines.append(re.sub(r"\*\*(.*?)\*\*", r"<strong>\1</strong>", curr))
            i += 1
            
        if p_lines:
            p_content = "<br>".join(p_lines) if len(p_lines) > 1 and len("".join(p_lines)) < 80 else "".join(p_lines)
            html_out.append(f"<p>{p_content}</p>")
        
    return "\n".join(html_out)


def demote(h, frm, to):
    """把 h<frm> 变为 h<to>。"""
    return re.sub(rf"<h{frm}>", f"<h{to}>", re.sub(rf"</h{frm}>", f"</h{to}>", h))


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
parts.append('''        <p class="zp-lead">2026 年 6 月起，一批大厂员工借用兰小欢《置身事内》的命名格式，写下以「置身 X 内」为题的职场长文，两个月内从钉钉扩散到美团、小米、小红书，最后溢出互联网进入制造业。本册逐篇收录可核实的原文，按发表时间编排，不做评论、不作演绎；原文未完整公开的篇目，只保留可核实的事实与摘录，并如实标注保真度。</p>
        <p class="zp-lead">缘起之作《置身钉内》，以及由此引出的《置身钉外》《云空未必空》与阿里巴巴合伙人委员会的官方回应《有情有义有成长，才是阿里文化》，均已收录于本站<a href="../alibaba/">「阿里巴巴 · 内网风暴」</a>话题。本册不再重复，只呈现浪潮扩散到其他企业之后的原文。</p>
''')

# ---------------------------------------------------------------- 1、置身团内
tuannei_html = '''        <p>从一个到餐基层产品的视角，简单聊聊我理解的美团困境。算是一篇 Super Mini 版的《置身团内》。</p>
        <p>楼主算是互联网浪子，一年一跳的那种。各个大厂表面上看都是鲜花着锦，背后也都难免烈火烹油。但美团这段短暂经历，还是刷新了我对组织下限的认知。</p>
        <p>我不想把问题简单归因于“某几个同事菜”。菜只是表象。更深层的问题是：在一个长期靠强执行和强管控取胜的组织里，一线产品、技术和管理链路，已经逐渐形成了一套非常稳定的低效结构。换句话说，<strong>君以此兴，必以此亡</strong>。</p>
        <p>简单讲几个我看到的奇观。</p>

        <h2>第一个奇观</h2>
        <p>到餐的 PM 名义上是产品，实际上更接近传话的太监。</p>
        <p>在其他厂，产品水平再差，至少表面上还会鼓励你讨论、探索、跨部门协作，鼓励你自己发掘一点新矿。但在我经历的到餐链路里，这些表面工程都可以省掉。组织非常直白地告诉你：你不需要有自己的判断，你只需要猜 +1 的意图，并把它拆成动作。</p>
        <p>这对刚毕业的同学尤其危险。因为这种工作模式对产品成长几乎百害而无一利。产品最核心的能力，不是写需求、排期、跟进、汇报，（这些都差不多被 AI 替代了）而是定义问题、识别机会、整合资源、对结果负责。如果一家公司长期只训练你听话和传话，那你最后得到的不是产品能力，而是一套组织内生存技巧。</p>
        <p>除非你非常确定自己能在美团干一辈子，否则这种能力结构在外部市场上的价值约等于 0。</p>

        <h2>第二个奇观</h2>
        <p>所谓“海量本地生活数据”，在很多具体业务链路里并没有真正资产化。</p>
        <p>美团对外一直强调自己拥有海量本地生活交易数据，这个说法当然没错。问题在于，有数据不等于会用数据，有交易数据不等于形成了业务资产，有算法团队不等于技术能力真正反哺了业务。</p>
        <p>至少在我看到的到餐场景里，大量问题仍然停留在非常原始的状态。举一个非常具体的例子：到今天为止，在我看到的到餐链路里，内部依然缺少一套足够准确的数据体系，去描述“一个套餐内容是否符合用户预期”。</p>
        <p>这件事听起来很细，但其实是到餐团购最核心的问题之一。</p>
        <p>用户买套餐，本质上买的不是一个抽象 SKU，而是一个关于“这一顿饭值不值、够不够、是不是我想象中那样”的预期。但如果平台没有能力准确刻画“套餐内容是否符合预期”，那就很难真正理解交易质量。</p>
        <p>有人可能会说：看转化率不就行了吗？</p>
        <p>问题恰恰在这里。</p>
        <p>如果只看线上转化率，那么转化率最高的套餐，往往可能是“一块钱两碗冰粉”这类极端低价、低决策成本、强价格刺激的商品。它当然好转化。但这是否意味着平台应该鼓励所有商家都把套餐改成“一块钱两碗冰粉”？</p>
        <p>一个平台如果只能知道什么东西好卖，却不知道什么东西该被卖，那它本质上是树上的大象：没人知道它怎么上去的，但它一定会掉下来。</p>
        <p>这也是我最震惊的地方。</p>
        <p>美团明明坐拥最稀缺的本地生活交易数据，但很多一线问题的解法，仍然不像一家拥有十几年数据积累的科技公司，更像一个靠人肉、经验和临时协调维持运转的手工作坊。</p>

        <h2>第三个奇观</h2>
        <p>AI 时代来了，但组织对 AI 的理解仍然停留在“许愿池”。</p>
        <p>我打个比方：现在很多 AI 项目给我的感觉，类似于“造了一个核聚变机器人，然后让它去当船夫”。</p>
        <p>一夜之间，AI 在美团内部从玩具变成了万能灵药。什么问题都可以挂 AI，什么项目都可以包装成智能化。但真正重要的问题是：AI 应该被装进哪一个发动机里？如果组织没有重新定义问题，只是把 AI 当作一个更高级的外包工具，那么 AI 只会放大原有组织的问题。过去靠人肉填坑，现在让模型填坑；过去没有底层结构，现在让大模型临场发挥；过去没有产品判断，现在让 AI 生成一个看起来像答案的答案。</p>
        <p>这不是智能化，这是许愿池化。</p>

        <h2>百因皆有果</h2>
        <p>美团今天的困境，并不是突然出现的。</p>
        <p>到餐团购的商业模式，本质上起源于 Groupon。美团早年在百团大战中笑到最后，靠的是极致的 UE 控制、极强的地推和执行力，以及对成本的近乎本能的敏感。从那个时候开始，“节俭”和“听话”就写进了这家公司的组织基因。</p>
        <p>在一个高增长、强渗透、竞争结构相对清晰的时代，这套基因当然有效。目标明确，路径清楚，资源有限，那就比谁更能吃苦、更能压成本、更能执行到底。</p>
        <p>但问题是，时代变了，大人。</p>
        <p>当到餐团购长期处在事实上的优势地位时，组织内部的资源分配也开始异化。既然业务还在赚钱，既然过去的方法一直有效，那为什么要把资源分给那些难以管理、难以量化、难以立刻产出的人和事？为什么不把资源继续分给更听话、更好用、更能完成汇报动作的人？</p>
        <p>如果岁月静好，如果经济和技术环境永远停留在 2015 年，这套系统也许还能继续运转很久。但现实不是这样。</p>
        <p>美团的老师，Groupon 没有在法律意义上死亡，但作为一种商业想象，它早就死亡很多年了。餐饮商家一夜之间用脚投票：单纯靠低价团购拉新、靠平台流量撮合交易的模式，已经越来越难解释今天的本地生活竞争。</p>
        <p>与此同时，抖音给商家提供的是另一套更清晰的叙事：内容种草-达人分发-品牌曝光-交易闭环。它不一定完美，甚至有很多问题，但它至少给商家讲了一个新的增长故事。</p>
        <p>而美团这边的问题是：它当然还有交易心智，还有履约能力，还有用户规模，还有本地生活基础设施。但在到餐这个具体场景里，它到底要给商家提供什么新的增长想象？商家宵衣旰食，把自己的排名从第 10 上涨到第 5，他的客流和收入能提升 50% 吗？</p>
        <p>如果这个问题回答不清楚，那么所有执行力都会变成空转。</p>
        <p>所以我理解的美团困境，不是没有执行力，而是执行力太强之后，形成了路径依赖。</p>
        <p>过去的美团，擅长把一个确定方向压到极致。今天的问题是，方向本身变得不确定了。这个时候，组织需要的不是更多传话筒、更多复盘会、更多 AI 包装项目，更长的加班时长。而是重新建立看见问题，定义问题的能力。</p>
        <p>节俭和听话曾经是美团的武器。但在新的历史潮流面前，节俭和听话是创新不共戴天的死敌。</p>
        <p>君不见 Nokia 与 Kodak 之故事乎？'''

parts.append(article(
    1, "置身团内",
    {"who": "美团到餐基层产品经理（已离职）· 脉脉匿名帖",
     "when": "2026-06-22",
     "badges": ["原文全文", "约两千字"]},
    tuannei_html,
    "校勘记：原文首发于脉脉匿名帖，经新浪科技、快科技等转载，本页据公开存档版整理。美团官方未作公开回应。"
))

# ---------------------------------------------------------------- 2、置身米内
minei_md = read("zhishen_minei_original.md")
# 去掉非正文的“补充说明”
if "## 补充说明" in minei_md:
    minei_md = minei_md.split("## 补充说明")[0]
minei_html = parse_markdown_blocks(minei_md)
minei_html = re.sub(r"<h1>.*?</h1>", "", minei_html, flags=re.S)
minei_html = demote(minei_html, 3, 2)
parts.append(article(
    2, "置身米内",
    {"who": "小米前校招生（2024 届入职，已离职）",
     "when": "2026-06-23 发于小米内网，数小时后被删",
     "badges": ["完整版原文", "约四千字"]},
    minei_html,
    "校勘记：据小米内网流出、雪球等平台转发的完整版整理；另有存档 OCR 版本，个别段落字句略有出入，此处从完整版。小米官方未作公开回应。"
))

# ---------------------------------------------------------------- 3、置身薯内
shunei_html = read("shunei_full.html")
parts.append(article(
    3, "置身薯内",
    {"who": "小红书前校招程序员 · 脉脉「小红书前同事圈」",
     "when": "2026-07-08",
     "badges": ["原文全文", "约两千字"]},
    shunei_html,
    "校勘记：原文以 5 页图文形式流传于脉脉，本页据截图逐段校对录入，并与两个独立转载来源交叉核对，文字一致。作者自述为理科生，写作时借助 AI 做过润色整理。小红书官方未作公开回应。"
))

# ---------------------------------------------------------------- 4、身在江湖
jianghu_md = read("zhishen_jianghu.md")
jianghu_html = parse_markdown_blocks(jianghu_md)
jianghu_html = re.sub(r"<h1>.*?</h1>", "", jianghu_html, flags=re.S)
jianghu_html = re.sub(r"<blockquote>.*?</blockquote>", "", jianghu_html, count=1, flags=re.S) # 移除开头的来源 blockquote
jianghu_html = demote(jianghu_html, 3, 2)
parts.append(article(
    4, "身在江湖",
    {"who": "D 司（深圳大疆创新）前员工",
     "when": "2026-07（微信私域首发）",
     "badges": ["原文全文", "标题变体"]},
    jianghu_html,
    "校勘记：原文首发于微信私域，标题用「身在江湖」而非「置身江湖」，与系列同源；本篇据作者公开的完整截图逐字核对录入全文。"
))

# ---------------------------------------------------------------- 附录：年表
parts.append('''        <h1 id="p5">5、系列年表</h1>
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
