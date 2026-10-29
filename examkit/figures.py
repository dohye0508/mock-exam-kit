# -*- coding: utf-8 -*-
"""흑백 시험지용 그림 생성 (matplotlib). 반환값은 (png_path, px_w, px_h).

figure 블록 예:
    ::: figure bar w=19000
    labels: 0교시, 8교시, 1차, 2차
    values: 35, 80, 120, 140
    ylabel: 시간(분)
    :::
유형: bar, barh, line, pie, timeline, table_grid(격자 퍼즐), sketch(skills/science-apparatus JSON)
"""
import os, json, subprocess, sys
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager, rcParams

_FONT_CANDIDATES = ["Malgun Gothic", "맑은 고딕", "HCR Batang", "함초롬바탕", "NanumGothic", "Gulim"]


def _setup_font():
    names = {f.name for f in font_manager.fontManager.ttflist}
    for c in _FONT_CANDIDATES:
        if c in names:
            rcParams["font.family"] = c
            break
    rcParams["axes.unicode_minus"] = False
    rcParams["font.size"] = 9
    rcParams["axes.linewidth"] = 0.8


_setup_font()
HATCHES = ["", "////", "....", "xxxx", "\\\\\\\\", "++++"]
GRAYS = ["#ffffff", "#bfbfbf", "#7f7f7f", "#404040", "#000000"]


def _nums(s):
    return [float(x) for x in str(s).replace("，", ",").split(",") if x.strip()]


def _strs(s):
    return [x.strip() for x in str(s).split(",")]


def _size(params, default_w=3.2):
    w = float(params.get("inch_w", default_w))
    h = float(params.get("inch_h", w * 0.55))
    return w, h


def _save(fig, out):
    fig.savefig(out, dpi=220, facecolor="white")
    plt.close(fig)
    from PIL import Image
    with Image.open(out) as im:
        return out, im.width, im.height


def bar(params, out):
    labels, values = _strs(params["labels"]), _nums(params.get("values", params.get("values1", "")))
    fig, ax = plt.subplots(figsize=_size(params))
    series = [k for k in params if k.startswith("values")]
    if len(series) > 1:
        n = len(series)
        wbar = 0.8 / n
        for i, k in enumerate(sorted(series)):
            vals = _nums(params[k])
            xs = [j + (i - (n - 1) / 2) * wbar for j in range(len(labels))]
            ax.bar(xs, vals, wbar, color=GRAYS[i % 5] if i else "white", edgecolor="black", hatch=HATCHES[i % 6],
                   label=params.get("legend", ",".join(series)).split(",")[i].strip())
        ax.legend(frameon=False, fontsize=8)
        ax.set_xticks(range(len(labels)))
    else:
        ax.bar(range(len(labels)), values, 0.6, color="white", edgecolor="black", hatch=params.get("hatch", ""))
        ax.set_xticks(range(len(labels)))
        if params.get("annotate", "1") == "1":
            for i, v in enumerate(values):
                ax.text(i, v, ("%g" % v), ha="center", va="bottom", fontsize=8)
    ax.set_xticklabels(labels)
    _axes(ax, params)
    return _save(fig, out)


def barh(params, out):
    labels, values = _strs(params["labels"]), _nums(params["values"])
    fig, ax = plt.subplots(figsize=_size(params))
    ax.barh(range(len(labels)), values, 0.6, color="white", edgecolor="black")
    ax.set_yticks(range(len(labels)))
    ax.set_yticklabels(labels)
    ax.invert_yaxis()
    for i, v in enumerate(values):
        ax.text(v, i, " %g" % v, va="center", fontsize=8)
    _axes(ax, params)
    return _save(fig, out)


def line(params, out):
    labels = _strs(params["labels"])
    fig, ax = plt.subplots(figsize=_size(params))
    series = sorted(k for k in params if k.startswith("values"))
    markers = ["o", "s", "^", "D"]
    legend = _strs(params.get("legend", ",".join(series)))
    for i, k in enumerate(series):
        vals = _nums(params[k])
        ax.plot(range(len(labels)), vals, marker=markers[i % 4], color="black", linestyle=["-", "--", ":", "-."][i % 4],
                markerfacecolor="white" if i else "black", label=legend[i] if i < len(legend) else k)
        if params.get("annotate", "1") == "1":
            for j, v in enumerate(vals):
                ax.text(j, v, " %g" % v, fontsize=7, va="bottom")
    if len(series) > 1:
        ax.legend(frameon=False, fontsize=8)
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels)
    _axes(ax, params)
    return _save(fig, out)


def pie(params, out):
    labels, values = _strs(params["labels"]), _nums(params["values"])
    fig, ax = plt.subplots(figsize=_size(params, 2.6))
    wedges, _ = ax.pie(values, startangle=90, counterclock=False, colors=["white"] * len(values),
                       wedgeprops=dict(edgecolor="black", linewidth=0.8))
    for w, h in zip(wedges, HATCHES):
        w.set_hatch(h)
    total = sum(values)
    for w, l, v in zip(wedges, labels, values):
        ang = (w.theta2 + w.theta1) / 2
        import math
        x, y = 0.65 * math.cos(math.radians(ang)), 0.65 * math.sin(math.radians(ang))
        txt = l if params.get("percent", "0") != "1" else "%s\n%d%%" % (l, round(100 * v / total))
        ax.text(x, y, txt, ha="center", va="center", fontsize=8,
                bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="none"))
    ax.set_aspect("equal")
    if params.get("title"):
        ax.set_title(params["title"], fontsize=9)
    return _save(fig, out)


def timeline(params, out):
    """events: 19:59|사감부장 통화, 20:03|이동 지시 ... (시각|문구)"""
    import textwrap
    events = [e.split("|", 1) for e in params["events"].split(";") if e.strip()]
    n = len(events)
    fig, ax = plt.subplots(figsize=(float(params.get("inch_w", 0.9 * n + 0.6)), float(params.get("inch_h", 1.5))))
    ax.plot([0, n - 1], [0, 0], color="black", lw=1)
    for i, (t, txt) in enumerate(events):
        ax.plot(i, 0, "o", color="black", ms=4)
        ax.text(i, 0.12, t.strip(), ha="center", fontsize=8)
        wrapped = "\n".join(textwrap.wrap(txt.strip(), int(params.get("wrap", 7))))
        y = -0.12 if i % 2 == 0 else -0.55
        ax.text(i, y, wrapped, ha="center", va="top", fontsize=7)
    ax.set_xlim(-0.6, n - 0.4)
    ax.set_ylim(-1.1, 0.4)
    ax.axis("off")
    fig.tight_layout(pad=0.2)
    return _save(fig, out)


def table_grid(params, out):
    """rows: 'A,B,C;D,E,F' 형태의 격자(좌석표·배치도 퍼즐)."""
    rows = [r.split(",") for r in params["rows"].split(";")]
    nr, nc = len(rows), max(len(r) for r in rows)
    cw, ch = float(params.get("cell_w", 0.55)), float(params.get("cell_h", 0.4))
    fig, ax = plt.subplots(figsize=(nc * cw + 0.2, nr * ch + 0.2))
    for i, r in enumerate(rows):
        for j, v in enumerate(r):
            v = v.strip()
            if v == "-":
                continue
            fill = "#d9d9d9" if v.startswith("#") else "white"
            v = v.lstrip("#")
            ax.add_patch(plt.Rectangle((j, nr - 1 - i), 1, 1, fc=fill, ec="black", lw=0.8))
            ax.text(j + 0.5, nr - 0.5 - i, v, ha="center", va="center", fontsize=8)
    ax.set_xlim(0, nc)
    ax.set_ylim(0, nr)
    ax.set_aspect("equal")
    ax.axis("off")
    if params.get("title"):
        ax.set_title(params["title"], fontsize=9, pad=4)
    fig.tight_layout(pad=0.3)
    return _save(fig, out)


def sketch(params, out):
    """skills/science-apparatus/render_apparatus.py 로 JSON 스케치 → SVG → PNG (cairosvg 필요)."""
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    script = os.path.join(root, "skills", "science-apparatus", "render_apparatus.py")
    if not os.path.exists(script):
        raise RuntimeError("skills/science-apparatus/render_apparatus.py 가 없습니다. SKILL.md에서 추출하세요.")
    svg = out[:-4] + ".svg"
    subprocess.run([sys.executable, script, params["json"], svg], check=True)
    import cairosvg
    cairosvg.svg2png(url=svg, write_to=out, dpi=220)
    from PIL import Image
    with Image.open(out) as im:
        return out, im.width, im.height


def _axes(ax, params):
    if params.get("ylabel"):
        # 평가원 그래프처럼 y축 이름을 축 위에 가로로 쓴다
        ax.text(-0.02, 1.03, params["ylabel"], transform=ax.transAxes, ha="left", va="bottom", fontsize=8)
    if params.get("xlabel"):
        ax.set_xlabel(params["xlabel"])
    if params.get("title"):
        ax.set_title(params["title"], fontsize=9)
    if params.get("ylim"):
        lo, hi = _nums(params["ylim"])
        ax.set_ylim(lo, hi)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.tick_params(labelsize=8)
    ax.figure.tight_layout(pad=0.3)


RENDERERS = dict(bar=bar, barh=barh, line=line, pie=pie, timeline=timeline, table_grid=table_grid, sketch=sketch)


def render(kind, params, out_png):
    os.makedirs(os.path.dirname(out_png) or ".", exist_ok=True)
    return RENDERERS[kind](params, out_png)
