// 冒烟测试：用 jsdom 跑一遍 reader.js，验证
//  1) 无 JS 异常
//  2) 孙宇晨页目录能自动生成
//  3) 三个页面的关键控件/标记位正确
const fs = require('fs');
const path = require('path');
const { JSDOM, VirtualConsole } = require('jsdom');

const ROOT = path.dirname(__dirname);  // 仓库根目录（本脚本位于 tools/）

// 话题目录自动发现：加新话题后本测试无需改动
const SKIP_DIRS = new Set(['assets', 'tools', 'node_modules', '.git', '.github']);
const TOPIC_DIRS = fs.readdirSync(ROOT, { withFileTypes: true })
    .filter(d => d.isDirectory() && !SKIP_DIRS.has(d.name)
                 && fs.existsSync(path.join(ROOT, d.name, 'index.html')))
    .map(d => d.name);
const PAGES = ['index.html', ...TOPIC_DIRS.map(d => `${d}/index.html`)];
console.log(`发现话题 ${TOPIC_DIRS.length} 个：${TOPIC_DIRS.join(', ')}`);

let failed = 0;
const ok = (c, m) => { console.log((c ? '  ✓ ' : '  ✗ ') + m); if (!c) failed++; return !!c; };
const brandRefs = {};   // 页面 → 图标引用路径（用于跨页一致性检查）

for (const p of PAGES) {
    console.log('\n──── ' + p + ' ────');
    const html = fs.readFileSync(path.join(ROOT, p), 'utf-8');
    const errors = [];
    const vc = new VirtualConsole();
    vc.on('jsdomError', e => errors.push(e.message));
    vc.on('error', (...a) => errors.push(a.join(' ')));

    const dom = new JSDOM(html, {
        runScripts: 'dangerously',
        resources: undefined,
        pretendToBeVisual: true,
        virtualConsole: vc,
        url: 'http://127.0.0.1:8900/' + p,
        beforeParse(win) {
            // jsdom 缺这两个浏览器 API，补桩避免误报
            win.ResizeObserver = class { observe() {} unobserve() {} disconnect() {} };
            win.IntersectionObserver = class { observe() {} unobserve() {} disconnect() {} };
        },
    });

    const { window } = dom;
    const doc = window.document;

    // 手动注入外链脚本（jsdom 默认不抓取外部资源）
    const js = fs.readFileSync(path.join(ROOT, 'assets/reader.js'), 'utf-8');
    try {
        const s = doc.createElement('script');
        s.textContent = js;
        // reader.js 在 </body> 前，正文已解析完
        doc.body.appendChild(s);
    } catch (e) {
        errors.push('注入 reader.js 抛错: ' + e.message);
    }

    ok(errors.length === 0, 'JS 无异常' + (errors.length ? ' → ' + errors.slice(0, 3).join(' | ') : ''));

    const tocBox = doc.getElementById('toc-container');
    const tocLinks = tocBox ? tocBox.querySelectorAll('a') : [];
    const hasMain = !!doc.querySelector('.main-content');

    if (hasMain) {
        const hs = doc.querySelectorAll('.main-content h1, .main-content h2, .main-content h3');
        ok(tocLinks.length === hs.length,
            `目录自动/保留生成：链接 ${tocLinks.length} 条 vs 标题 ${hs.length} 个`);
        if (p.startsWith('sunyuchen')) {
            const txt = [...tocLinks].map(a => a.textContent.trim());
            ok(txt.includes('一、蒙太奇拉古纳海滩'), '目录含本话题章节（非继承钉内目录）');
            ok(!txt.some(t => t.includes('置身钉内')), '目录不含钉钉话题残留');
        }
        if (p.startsWith('dingnei')) {
            const txt = [...tocLinks].map(a => a.textContent.trim());
            ok(txt.some(t => t.includes('置身钉内')), '钉钉目录完整保留');
            ok(txt.some(t => t.includes('云空未必空')), '钉钉目录含收官篇');
        }
    } else {
        ok(true, '首页无 .main-content（跳过目录检查）');
    }

    ok(!!doc.getElementById('topicToggle') && !!doc.getElementById('topicDropdown'), '话题切换器就位');
    const topics = doc.querySelectorAll('.topic-item:not(.home)');
    ok(topics.length === TOPIC_DIRS.length,
        `话题条目 ${TOPIC_DIRS.length} 个（实际 ${topics.length}）`);
    ok(!!doc.querySelector('.topic-item.home'), '含「返回话题首页」入口');
    const cur = doc.querySelectorAll('.topic-item.current');
    ok(cur.length === 1, `current 标记唯一（${cur.length}）→ ` + (cur[0] ? cur[0].getAttribute('href') : '无'));

    // 各页品牌与资源
    const pref = p === 'index.html' ? './' : '../';
    ok(html.includes(`href="${pref}assets/theme.css"`), `公共 CSS 路径正确 (${pref})`);
    ok(html.includes(`src="${pref}assets/reader.js"`), `公共 JS 路径正确 (${pref})`);
    // 品牌图标：三页共用 assets/brand.*（共享文件，不内联 base64）
    const favTag = (html.match(/<link rel="icon"[^>]*>/) || [''])[0];
    ok(!!favTag, 'favicon 标签就位');
    ok(favTag && !favTag.includes('base64'), 'favicon 未内联 base64');

    const logoImg = doc.querySelector('img.logo-icon');
    ok(!!logoImg, 'logo 图标就位');
    if (logoImg) {
        const src = logoImg.getAttribute('src') || '';
        ok(!src.includes('base64'), 'logo 未内联 base64');
        ok(new RegExp(`^${pref.replace('/', '\\/')}assets\\/brand\\.(png|jpg|svg)$`).test(src),
            `logo 指向共享资产（${src}）`);
        brandRefs[p] = src.replace(/^\.\.?\//, '');
        const abs = path.join(ROOT, src.replace(/^\.\.?\//, ''));
        if (ok(fs.existsSync(abs), `图标文件存在（${src.replace(/^\.\.?\//, '')}）`) && fs.existsSync(abs)) {
            const buf = fs.readFileSync(abs);
            if (ok(buf[0] === 0x89 && buf.toString('ascii', 1, 4) === 'PNG', '图标是合法 PNG')) {
                const w = buf.readUInt32BE(16), h = buf.readUInt32BE(20);
                ok(w === h && w >= 64 && w <= 512, `图标尺寸 ${w}×${h}（正方形，64–512）`);
                ok(buf.length < 120 * 1024,
                    `图标体积 ${(buf.length / 1024).toFixed(1)}KB（< 120KB）`);
            }
        }
    }

    dom.window.close();
}

// 所有页面必须引用同一个图标文件（避免各页各存一份）
console.log('\n──── 品牌图标跨页一致性 ────');
{
    const refs = PAGES.map(p => brandRefs[p]).filter(Boolean);
    ok(refs.length === PAGES.length,
        `${PAGES.length} 个页面都解析到图标引用（${refs.length}/${PAGES.length}）`);
    ok(new Set(refs).size === 1,
        `所有页面共用同一图标文件 → ${[...new Set(refs)].join(', ')}`);
}

// 单独验证 reader.js 里确实挂了内容保护
const js = fs.readFileSync(path.join(ROOT, 'assets/reader.js'), 'utf-8');
console.log('\n──── 内容保护（reader.js 全局） ────');
ok(/addEventListener\('contextmenu'/.test(js), '禁右键');
ok(/addEventListener\('copy'/.test(js), '禁复制');
ok(/addEventListener\('cut'/.test(js), '禁剪切');
ok(/addEventListener\('selectstart'/.test(js), '禁选中');
ok(/keyCode === 123/.test(js), '禁 F12 / Ctrl+U 等快捷键');

console.log('\n' + (failed === 0 ? '全部通过 ✓' : `失败 ${failed} 项 ✗`));
process.exit(failed === 0 ? 0 : 1);
