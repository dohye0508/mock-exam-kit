# -*- coding: utf-8 -*-
"""흑백 시험지용 그림 생성 (matplotlib). 반환값은 (png_path, px_w, px_h).

figure 블록 예:
    ::: figure bar w=19000
    labels: 0교시, 8교시, 1차, 2차
    values: 35, 80, 120, 140
    ylabel: 시간(분)
    :::
유형: bar, barh, line, pie, timeline, table_grid(격자 퍼즐), sketch(skills/science-apparatus JSON)

크기: build 가 지면 폭(w)의 1.25배를 inch_w 로 넘겨 주므로 보통은 inch_w 를 적지 않는다.
글자 크기(FS_*)는 그 배율로 줄었을 때 지면에서 약 7.5~8pt 가 되도록 잡았다.
"""
import os, json, subprocess, sys, math, textwrap
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager, rcParams

_FONT_CANDIDATES = ["Malgun Gothic", "맑은 고딕", "HCR Batang", "함초롬바탕", "NanumGothic", "Gulim"]
FS = 10        # 축 이름·범례·제목
FS_TICK = 9.5  # 눈금 이름
FS_NOTE = 9    # 막대·점 위의 값


def _setup_font():
    names = {f.name for f in font_manager.fontManager.ttflist}
    for c in _FONT_CANDIDATES:
        if c in names:
            rcParams["font.family"] = c
            break
    rcParams["axes.unicode_minus"] = False
    rcParams["font.size"] = FS
    rcParams["axes.linewidth"] = 0.8


_setup_font()
HATCHES = ["", "////", "....", "xxxx", "\\\\\\\\", "++++"]
GRAYS = ["#ffffff", "#bfbfbf", "#7f7f7f", "#404040", "#000000"]


def _nums(s):
    return [float(x) for x in str(s).replace("，", ",").split(",") if x.strip()]


def _strs(s):
    return [x.strip() for x in str(s).split(",")]


def _size(params, default_w=3.2, ratio=0.5):
    w = float(params.get("inch_w", default_w))
    h = float(params.get("inch_h", w * ratio))
    return w, h


def _save(fig, out):
    fig.savefig(out, dpi=220, facecolor="white")
    plt.close(fig)
    from PIL import Image
    with Image.open(out) as im:
        return out, im.width, im.height


def _wrap_labels(labels, width):
    return ["\n".join(textwrap.wrap(l, width)) or l for l in labels]


def bar(params, out):
    labels = _wrap_labels(_strs(params["labels"]), int(params.get("wrap", 6)))
    fig, ax = plt.subplots(figsize=_size(params))
    series = sorted(k for k in params if k.startswith("values"))
    annotate = params.get("annotate", "1") == "1"
    if len(series) > 1:
        n = len(series)
        wbar = 0.8 / n
        legend = _strs(params.get("legend", ",".join(series)))
        for i, k in enumerate(series):
            vals = _nums(params[k])
            xs = [j + (i - (n - 1) / 2) * wbar for j in range(len(labels))]
            ax.bar(xs, vals, wbar, color=GRAYS[i % 5] if i else "white", edgecolor="black", hatch=HATCHES[i % 6],
                   label=legend[i] if i < len(legend) else k)
            if annotate:
                for x, v in zip(xs, vals):
                    ax.text(x, v, "%g" % v, ha="center", va="bottom", fontsize=FS_NOTE)
        # 범례는 막대·세로축 이름과 겹치지 않게 그림 영역 오른쪽 바깥에 세로로 둔다
        ax.legend(frameon=False, fontsize=FS, loc="upper left", bbox_to_anchor=(1.0, 1.0),
                  handlelength=1.2, borderaxespad=0.3)
    else:
        values = _nums(params["values"])
        ax.bar(range(len(labels)), values, 0.6, color="white", edgecolor="black", hatch=params.get("hatch", ""))
        if annotate:
            for i, v in enumerate(values):
                ax.text(i, v, "%g" % v, ha="center", va="bottom", fontsize=FS_NOTE)
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels)
    ax.margins(y=0.12)
    _axes(ax, params)
    return _save(fig, out)


def barh(params, out):
    labels, values = _strs(params["labels"]), _nums(params["values"])
    fig, ax = plt.subplots(figsize=_size(params, ratio=max(0.45, 0.13 * len(labels))))
    ax.barh(range(len(labels)), values, 0.6, color="white", edgecolor="black")
    ax.set_yticks(range(len(labels)))
    ax.set_yticklabels(labels)
    ax.invert_yaxis()
    for i, v in enumerate(values):
        ax.text(v, i, " %g" % v, va="center", fontsize=FS_NOTE)
    ax.margins(x=0.12)
    _axes(ax, params)
    return _save(fig, out)


def line(params, out):
    labels = _strs(params["labels"])
    fig, ax = plt.subplots(figsize=_size(params))
    series = sorted(k for k in params if k.startswith("values"))
    markers = ["o", "s", "^", "D"]
    legend = _strs(params.get("legend", ",".join(series)))
    for i, k in enumerate(series):
        # 빈 값(쉼표 사이 공란)은 그리지 않는다: 아직 없는 자료
        raw = [x.strip() for x in str(params[k]).split(",")]
        pts = [(j, float(v)) for j, v in enumerate(raw) if v]
        xs, vals = [p[0] for p in pts], [p[1] for p in pts]
        ax.plot(xs, vals, marker=markers[i % 4], color="black", linestyle=["-", "--", ":", "-."][i % 4],
                markerfacecolor="white" if i else "black", label=legend[i] if i < len(legend) else k)
        if params.get("annotate", "1") == "1":
            for x, v in zip(xs, vals):
                ax.text(x, v, " %g" % v, fontsize=FS_NOTE, va="bottom")
    if len(series) > 1:
        ax.legend(frameon=False, fontsize=FS)
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels)
    ax.margins(x=0.08, y=0.15)
    _axes(ax, params)
    return _save(fig, out)


def pie(params, out):
    labels, values = _strs(params["labels"]), _nums(params["values"])
    fig, ax = plt.subplots(figsize=_size(params, 2.6, ratio=1.0))
    wedges, _ = ax.pie(values, startangle=90, counterclock=False, colors=["white"] * len(values),
                       wedgeprops=dict(edgecolor="black", linewidth=0.8))
    for w, h in zip(wedges, HATCHES):
        w.set_hatch(h)
    total = sum(values)
    for w, l, v in zip(wedges, labels, values):
        ang = (w.theta2 + w.theta1) / 2
        x, y = 0.65 * math.cos(math.radians(ang)), 0.65 * math.sin(math.radians(ang))
        txt = l if params.get("percent", "0") != "1" else "%s\n%d%%" % (l, round(100 * v / total))
        ax.text(x, y, txt, ha="center", va="center", fontsize=FS_NOTE,
                bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="none"))
    ax.set_aspect("equal")
    if params.get("title"):
        ax.set_title(params["title"], fontsize=FS)
    return _save(fig, out)


def timeline(params, out):
    """events: 19:59|사감부장 통화; 20:03|이동 지시 ... (시각|문구)"""
    events = [e.split("|", 1) for e in params["events"].split(";") if e.strip()]
    n = len(events)
    w = float(params.get("inch_w", 0.9 * n + 0.6))
    wrap = int(params.get("wrap", max(4, int(w / n * 7.5))))
    fig, ax = plt.subplots(figsize=(w, float(params.get("inch_h", 1.45))))
    ax.plot([0, n - 1], [0, 0], color="black", lw=1)
    for i, (t, txt) in enumerate(events):
        ax.plot(i, 0, "o", color="black", ms=4)
        ax.text(i, 0.12, t.strip(), ha="center", fontsize=FS_TICK)
        wrapped = "\n".join(textwrap.wrap(txt.strip(), wrap))
        y = -0.12 if i % 2 == 0 else -0.62
        ax.text(i, y, wrapped, ha="center", va="top", fontsize=FS_NOTE)
    ax.set_xlim(-0.6, n - 0.4)
    ax.set_ylim(-1.25, 0.4)
    ax.axis("off")
    fig.tight_layout(pad=0.2)
    return _save(fig, out)


def table_grid(params, out):
    """rows: 'A,B,C;D,E,F' 형태의 격자(좌석표·배치도 퍼즐). '-' 빈칸, '#' 음영."""
    rows = [r.split(",") for r in params["rows"].split(";")]
    nr, nc = len(rows), max(len(r) for r in rows)
    if "cell_w" in params:
        cw = float(params["cell_w"])
    else:
        cw = min(0.85, (float(params.get("inch_w", 2.4)) - 0.2) / nc)
    ch = float(params.get("cell_h", min(0.38, cw * 0.65)))
    fig, ax = plt.subplots(figsize=(nc * cw + 0.2, nr * ch + (0.45 if params.get("title") else 0.2)))
    for i, r in enumerate(rows):
        for j, v in enumerate(r):
            v = v.strip()
            if v == "-":
                continue
            fill = "#d9d9d9" if v.startswith("#") else "white"
            v = v.lstrip("#")
            ax.add_patch(plt.Rectangle((j, nr - 1 - i), 1, 1, fc=fill, ec="black", lw=0.8))
            ax.text(j + 0.5, nr - 0.5 - i, v, ha="center", va="center", fontsize=FS_TICK)
    ax.set_xlim(0, nc)
    ax.set_ylim(0, nr)
    ax.set_aspect("auto")
    ax.axis("off")
    if params.get("title"):
        ax.set_title(params["title"], fontsize=FS, pad=4)
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
        ax.text(-0.02, 1.04, params["ylabel"], transform=ax.transAxes, ha="left", va="bottom", fontsize=FS)
    if params.get("xlabel"):
        ax.set_xlabel(params["xlabel"], fontsize=FS)
    if params.get("title"):
        ax.set_title(params["title"], fontsize=FS)
    if params.get("ylim"):
        lo, hi = _nums(params["ylim"])
        ax.set_ylim(lo, hi)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.tick_params(labelsize=FS_TICK)
    ax.figure.tight_layout(pad=0.3)


RENDERERS = dict(bar=bar, barh=barh, line=line, pie=pie, timeline=timeline, table_grid=table_grid, sketch=sketch)


def render(kind, params, out_png):
    os.makedirs(os.path.dirname(out_png) or ".", exist_ok=True)
    return RENDERERS[kind](params, out_png)
