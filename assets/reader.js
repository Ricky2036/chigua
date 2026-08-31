// Initial load preferences script has already run in <head> or right after <body>.

// Progress Bar
window.addEventListener('scroll', () => {
    const bar = document.getElementById("progress-bar");
    if (!bar) return;
    const winScroll = document.body.scrollTop || document.documentElement.scrollTop;
    const height = document.documentElement.scrollHeight - document.documentElement.clientHeight;
    const scrolled = (winScroll / height) * 100;
    bar.style.width = scrolled + "%";
});

// Font Toggle
const fontToggle = document.getElementById('fontToggle');
if (fontToggle) {
const fontIcon = fontToggle.querySelector('span');
let isSerif = localStorage.getItem('pref-font') === 'serif';

function updateFontUI() {
    fontToggle.title = isSerif ? '切换字体 (Sans)' : '切换字体 (Serif)';
    fontIcon.style.fontFamily = isSerif ? 'var(--font-sans)' : 'var(--font-serif)';
}
updateFontUI();

fontToggle.addEventListener('click', () => {
    isSerif = document.body.classList.toggle('font-serif');
    localStorage.setItem('pref-font', isSerif ? 'serif' : 'sans');
    updateFontUI();
});
}

// Size Toggle
const sizeToggle = document.getElementById('sizeToggle');
if (sizeToggle) {
const sizes = ['medium', 'large', 'small'];
const sizeLabels = {'small': '较小', 'medium': '适中', 'large': '较大'};

let savedSize = localStorage.getItem('pref-size');
let currentSizeIdx = sizes.indexOf(savedSize);
if (currentSizeIdx === -1) currentSizeIdx = 0;

function applySize() {
    const size = sizes[currentSizeIdx];
    sizes.forEach(s => document.body.classList.remove(`size-${s}`));
    if (size !== 'medium') document.body.classList.add(`size-${size}`);
    sizeToggle.title = `字号: ${sizeLabels[size]}`;
}
applySize();

sizeToggle.addEventListener('click', () => {
    currentSizeIdx = (currentSizeIdx + 1) % sizes.length;
    localStorage.setItem('pref-size', sizes[currentSizeIdx]);
    applySize();
});
}

// Width Toggle
const widthToggle = document.getElementById('widthToggle');
if (widthToggle) {
const widths = ['medium', 'wide', 'narrow'];
const widthLabels = {'narrow': '较窄', 'medium': '适中', 'wide': '较宽'};
const widthIcons = {
    'narrow': '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 5h18M3 19h18M4 12h5M6 9l3 3-3 3M15 12h5M18 9l-3 3 3 3"/></svg>',
    'medium': '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 5h18M3 19h18M4 12h5M7 9l-3 3 3 3M15 12h5M17 9l3 3-3 3"/></svg>',
    'wide': '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 5h18M3 19h18M4 12h5M7 9l-3 3 3 3M15 12h5M17 9l3 3-3 3"/></svg>'
};

let savedWidth = localStorage.getItem('pref-width');
let currentWidthIdx = widths.indexOf(savedWidth);
if (currentWidthIdx === -1) currentWidthIdx = 0;

function applyWidth() {
    const w = widths[currentWidthIdx];
    const nextW = widths[(currentWidthIdx + 1) % widths.length];
    widths.forEach(width => document.body.classList.remove(`width-${width}`));
    if (w !== 'medium') document.body.classList.add(`width-${w}`);
    
    widthToggle.title = `切换宽度 (${widthLabels[nextW]})`;
    widthToggle.innerHTML = widthIcons[nextW];
}
applyWidth();

widthToggle.addEventListener('click', () => {
    currentWidthIdx = (currentWidthIdx + 1) % widths.length;
    localStorage.setItem('pref-width', widths[currentWidthIdx]);
    applyWidth();
});
}

// Wrap tables for responsive scrolling
document.querySelectorAll('table').forEach(table => {
    if (!table.parentElement.classList.contains('table-responsive')) {
        const wrapper = document.createElement('div');
        wrapper.className = 'table-responsive';
        table.parentNode.insertBefore(wrapper, table);
        wrapper.appendChild(table);
    }
});


// Smart Table Column Alignment (If all cells in a col are single-line -> center, else -> left)
function adjustTableAlignment() {
    document.querySelectorAll('table').forEach(table => {
        const rows = Array.from(table.querySelectorAll('tr'));
        if (rows.length === 0) return;
        let colCount = 0;
        rows.forEach(r => colCount = Math.max(colCount, r.children.length));
        
        for (let col = 0; col < colCount; col++) {
            let hasWrap = false;
            rows.forEach(row => {
                const cell = row.children[col];
                if (!cell || cell.tagName === 'TH') return;
                
                const span = document.createElement('span');
                span.style.display = 'inline';
                while(cell.firstChild) span.appendChild(cell.firstChild);
                cell.appendChild(span);
                
                if (span.getClientRects().length > 1) {
                    hasWrap = true;
                }
                
                while(span.firstChild) cell.appendChild(span.firstChild);
                cell.removeChild(span);
            });
            
            const align = hasWrap ? 'left' : 'center';
            rows.forEach(row => {
                const cell = row.children[col];
                if (cell && cell.tagName === 'TD') {
                    cell.style.setProperty('text-align', align, 'important');
                }
            });
        }
    });
}
window.addEventListener('load', adjustTableAlignment);

// Use ResizeObserver for better performance
let resizeTimer;
const resizeObserver = new ResizeObserver(() => {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(adjustTableAlignment, 150); // Debounced 150ms
});
resizeObserver.observe(document.body);

// Auto-build TOC when #toc-container is empty (new topic pages ship without a hand-written TOC)
(function buildTocIfEmpty() {
    const box = document.getElementById('toc-container');
    if (!box || box.querySelector('a')) return;
    const headings = document.querySelectorAll('.main-content h1, .main-content h2, .main-content h3');
    if (!headings.length) return;

    const used = {};
    headings.forEach(h => {
        if (h.id) return;
        let slug = (h.textContent || '').trim()
            .replace(/\s+/g, '-')
            .replace(/[^\w\u4e00-\u9fa5-]/g, '');
        if (!slug) slug = 'sec';
        used[slug] = (used[slug] || 0) + 1;
        h.id = used[slug] > 1 ? slug + '-' + used[slug] : slug;
    });

    const root = document.createElement('ul');
    const stack = [{ level: 0, ul: root }];
    headings.forEach(h => {
        const level = parseInt(h.tagName.substring(1), 10);
        while (stack.length > 1 && stack[stack.length - 1].level >= level) stack.pop();
        const li = document.createElement('li');
        const a = document.createElement('a');
        a.href = '#' + h.id;
        a.textContent = h.textContent;
        li.appendChild(a);
        stack[stack.length - 1].ul.appendChild(li);
        const child = document.createElement('ul');
        li.appendChild(child);
        stack.push({ level: level, ul: child });
    });
    root.querySelectorAll('ul').forEach(u => { if (!u.children.length) u.remove(); });

    const toc = document.createElement('div');
    toc.className = 'toc';
    toc.appendChild(root);
    box.appendChild(toc);
})();

// Scroll Spy for TOC
const observer = new IntersectionObserver(entries => {
    entries.forEach(entry => {
        const id = entry.target.getAttribute('id');
        const tocLink = document.querySelector(`.sidebar a[href="#${id}"]`);
        if (entry.isIntersecting && tocLink) {
            document.querySelectorAll('.sidebar a').forEach(a => a.classList.remove('active-toc'));
            tocLink.classList.add('active-toc');
            
            const sidebar = document.querySelector('.sidebar');
            const linkRect = tocLink.getBoundingClientRect();
            const sidebarRect = sidebar.getBoundingClientRect();
            
            if (linkRect.top < sidebarRect.top || linkRect.bottom > sidebarRect.bottom) {
                const offset = linkRect.top - sidebarRect.top - (sidebarRect.height / 2) + (linkRect.height / 2);
                sidebar.scrollBy({ top: offset, behavior: 'smooth' });
            }
        }
    });
}, { rootMargin: '-80px 0px -60% 0px' });

document.querySelectorAll('h1, h2, h3').forEach(heading => {
    if(heading.id) observer.observe(heading);
});

// Back to Top
const backToTop = document.getElementById('backToTop');
if (backToTop) {
window.addEventListener('scroll', () => {
    const scrollY = window.scrollY || document.documentElement.scrollTop;
    backToTop.classList.toggle('visible', scrollY > 600);
}, { passive: true });
backToTop.addEventListener('click', () => {
    window.scrollTo({ top: 0, behavior: 'smooth' });
});
}

// Lightbox for Images
const mainContentImages = document.querySelectorAll('.main-content img');
if (mainContentImages.length > 0) {
    const lightbox = document.createElement('div');
    lightbox.className = 'lightbox';
    lightbox.innerHTML = `
        <div class="lightbox-close">&times;</div>
        <img src="" alt="Zoomed image">
    `;
    document.body.appendChild(lightbox);
    
    const lightboxImg = lightbox.querySelector('img');
    
    mainContentImages.forEach(img => {
        img.addEventListener('click', () => {
            lightboxImg.src = img.src;
            lightbox.classList.add('active');
        });
    });
    
    lightbox.addEventListener('click', () => {
        lightbox.classList.remove('active');
    });
}

// Security & Anti-Scraping Measures
document.addEventListener('contextmenu', e => e.preventDefault());
document.addEventListener('copy', e => {
    e.preventDefault();
    e.clipboardData.setData('text/plain', '本文内容受版权保护，禁止复制。');
});
document.addEventListener('cut', e => e.preventDefault());
document.addEventListener('selectstart', e => e.preventDefault());
document.addEventListener('keydown', e => {
    // Disable F12, Ctrl+Shift+I, Ctrl+Shift+J, Ctrl+U
    if (e.keyCode === 123 || 
       (e.ctrlKey && e.shiftKey && (e.keyCode === 73 || e.keyCode === 74)) || 
       (e.ctrlKey && e.keyCode === 85) ||
       (e.metaKey && e.altKey && e.keyCode === 73)) {
        e.preventDefault();
    }
});

// Mobile TOC Toggle
const logo = document.querySelector('.logo');
const sidebar = document.querySelector('.sidebar');
const mobileOverlay = document.getElementById('mobileOverlay');

function toggleMobileToc() {
    if (window.innerWidth <= 860) {
        sidebar.classList.toggle('mobile-open');
        mobileOverlay.classList.toggle('active');
    }
}

function closeMobileToc() {
    if (window.innerWidth <= 860) {
        sidebar.classList.remove('mobile-open');
        mobileOverlay.classList.remove('active');
    }
}

if (logo && sidebar && mobileOverlay) {
    logo.addEventListener('click', toggleMobileToc);
    mobileOverlay.addEventListener('click', closeMobileToc);
    
    // Close when clicking a link
    sidebar.querySelectorAll('a').forEach(link => {
        link.addEventListener('click', closeMobileToc);
    });
    
    // Close on resize if switching to desktop
    window.addEventListener('resize', () => {
        if (window.innerWidth > 860) {
            closeMobileToc();
        }
    });
}

// Topic Switcher
const topicToggle = document.getElementById('topicToggle');
const topicDropdown = document.getElementById('topicDropdown');
if (topicToggle && topicDropdown) {
    const closeDropdown = () => topicDropdown.classList.remove('active');
    topicToggle.addEventListener('click', e => {
        e.stopPropagation();
        topicDropdown.classList.toggle('active');
    });
    document.addEventListener('click', e => {
        if (!topicDropdown.contains(e.target)) closeDropdown();
    });
    document.addEventListener('keydown', e => {
        if (e.key === 'Escape') closeDropdown();
    });
    topicDropdown.addEventListener('click', e => {
        if (e.target.closest('a')) closeDropdown();
    });
}
