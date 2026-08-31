#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
校验共享品牌图标 assets/brand.png 是「真的看得见」的图。

为什么要单独一个脚本：
    上游曾用一张 PNG 替换掉图标，那张图 alpha 通道最大值只有 5（合法范围 0–255），
    不透明像素占比 0.0%，RGB 里 94.7% 是纯黑噪点 —— 页面能正常加载、不报任何错，
    但 logo 在浏览器里就是一片空白。这类「静默失效」问题 HTML/DOM 层检查抓不到，
    只有把像素真正解码出来才看得见。

用法：
    python3 tools/verify_brand.py [图片路径]     # 默认 assets/brand.png
退出码：0 = 通过，1 = 有问题
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)

path = sys.argv[1] if len(sys.argv) > 1 else "assets/brand.png"
if not os.path.exists(path):
    sys.exit(f"找不到图标文件：{path}")

try:
    from PIL import Image
except ImportError:
    print("跳过：未安装 Pillow，无法做像素级校验")
    sys.exit(0)

fails = []


def check(cond, msg):
    print(("  ✓ " if cond else "  ✗ ") + msg)
    if not cond:
        fails.append(msg)


im = Image.open(path)
im.load()
print(f"校验 {path}")
print(f"  格式={im.format} 模式={im.mode} 尺寸={im.size[0]}×{im.size[1]} "
      f"体积={os.path.getsize(path)} B\n")

check(im.size[0] == im.size[1], f"正方形（{im.size[0]}×{im.size[1]}）")
check(64 <= im.size[0] <= 512, f"尺寸在 64–512 之间（实际 {im.size[0]}）")
check(os.path.getsize(path) < 120 * 1024, f"体积 < 120KB（实际 {os.path.getsize(path) / 1024:.1f}KB）")

rgba = im.convert("RGBA")
# getdata() 在 Pillow 14 会移除，优先用 get_flattened_data()
px = list(rgba.get_flattened_data()) if hasattr(rgba, "get_flattened_data") else list(rgba.getdata())
n = len(px)
alphas = [p[3] for p in px]
amax = max(alphas)
opaque = [p for p in px if p[3] > 128]

# 下面三条就是「图标全透明不可见」这个坑的具体判据
check(amax >= 200, f"alpha 最大值 {amax} ≥ 200（能看到东西；曾出现 max=5 的空白图）")
ratio = 100 * len(opaque) / n
check(3 <= ratio <= 98, f"不透明像素占比 {ratio:.1f}% 落在 3%–98%（不是全空也不是铺满）")

if opaque:
    from collections import Counter
    top_color, top_cnt = Counter((p[0], p[1], p[2]) for p in opaque).most_common(1)[0]
    share = 100 * top_cnt / len(opaque)
    check(share < 90,
          f"主色 #{top_color[0]:02X}{top_color[1]:02X}{top_color[2]:02X} 占比 {share:.1f}% < 90%（不是纯色噪点块）")
    uniq = len(set((p[0], p[1], p[2]) for p in opaque))
    check(uniq > 50, f"颜色种类 {uniq} > 50（有真实图像细节，非纯色块）")
else:
    check(False, "存在不透明像素")

print()
if fails:
    sys.exit(f"图标校验失败 {len(fails)} 项：\n  - " + "\n  - ".join(fails))
print("图标校验通过 ✓")
