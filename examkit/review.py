# -*- coding: utf-8 -*-
"""검토본: 교시별로 정답 선택지를 @status 색으로 칠해 빌드하고, 표지 한 장과 함께 PDF 하나로 이어 붙인다.

python -m examkit review "content/*교시.md" -o output/review
  → output/review/<title>_검토.hwp/.pdf, output/review/검토본.pdf
PDF 병합과 표지에는 PyMuPDF(pip install pymupdf)가 필요하다.
"""
import datetime, os
from .parse_md import parse, check
from .build import build, REVIEW_COLORS
from .convert import convert

STATUS_LABEL = {"keep": "그대로 둔 문제", "mod": "수정한 문제", "new": "새로 만들거나 발전시킨 문제"}
MARKS = "①②③④⑤"
FONT_CANDIDATES = [r"C:\Windows\Fonts\malgun.ttf", r"C:\Windows\Fonts\malgunbd.ttf", "/System/Library/Fonts/AppleSDGothicNeo.ttc"]


def _rgb(hex_color):
    h = hex_color.lstrip("#")
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))


def _cover(doc, summary, page_size):
    import pymupdf
    font = next((f for f in FONT_CANDIDATES if os.path.exists(f)), None)
    page = doc.new_page(0, width=page_size[0], height=page_size[1])
    kw = dict(fontname="kr", fontfile=font) if font else {}
    x, y = 60, 90
    page.insert_text((x, y), "검토본 · 1~4교시 (%s)" % datetime.date.today().isoformat(), fontsize=24, **kw)
    y += 40
    page.insert_text((x, y), "각 문제의 정답 선택지를 아래 색으로 칠했습니다.", fontsize=13, **kw)
    y += 34
    for status, color in REVIEW_COLORS.items():
        page.draw_rect(pymupdf.Rect(x, y - 12, x + 26, y + 2), color=_rgb(color), fill=_rgb(color))
        page.insert_text((x + 36, y), STATUS_LABEL[status], fontsize=13, color=_rgb(color), **kw)
        y += 26
    y += 18
    for title, rows, problems in summary:
        page.insert_text((x, y), title, fontsize=15, **kw)
        y += 24
        for status in REVIEW_COLORS:
            nums = [str(n) for n, s, _ in rows if s == status]
            line = "%s (%d): %s" % (STATUS_LABEL[status], len(nums), ", ".join(nums) or "-")
            page.insert_text((x + 12, y), line, fontsize=11.5, color=_rgb(REVIEW_COLORS[status]), **kw)
            y += 19
        keys = ["%d%s" % (n, MARKS[a - 1] if a else "?") for n, _, a in rows]
        for k in range(0, len(keys), 10):
            label = "정답: " if k == 0 else "         "
            page.insert_text((x + 12, y), label + "  ".join(keys[k:k + 10]), fontsize=11.5, **kw)
            y += 19
        if problems:
            page.insert_text((x + 12, y), "점검: " + "; ".join(problems), fontsize=10.5, color=(0.7, 0.1, 0.1), **kw)
            y += 18
        y += 16


def _question_starts(doc):
    """PDF에서 문항 번호 줄의 위치 {번호: (쪽, 단, y)}. 단 왼쪽 끝에서 'N.'으로 시작하는 줄을 찾는다."""
    import re
    starts = {}
    for pi, p in enumerate(doc):
        W, H = p.rect.width, p.rect.height
        for b in p.get_text("dict")["blocks"]:
            for l in b.get("lines", []):
                t = "".join(s["text"] for s in l["spans"]).strip()
                x0, y0, x1, y1 = l["bbox"]
                if y0 < 60 or y1 > H - 45:
                    continue
                col = 0 if x0 < W / 2 else 1
                m = re.match(r"^(\d{1,2})\.\s", t + " ")
                if m and x0 - col * W / 2 < 60:
                    starts.setdefault(int(m.group(1)), (pi, col, y0))
    return starts


def _mark_answers(doc, qs):
    """색 없이 만든 PDF에서 정답 선택지를 찾아 @status 색 상자를 그린다. 못 찾은 문항 번호를 돌려준다."""
    import pymupdf
    pos = _question_starts(doc)
    order = sorted(pos.items(), key=lambda kv: kv[1])
    byn = {q["n"]: q for q in qs}
    missing = []
    for i, (n, (pi, col, y)) in enumerate(order):
        q = byn.get(n)
        if not q or not q.get("answer"):
            continue
        p = doc[pi]
        W, H = p.rect.width, p.rect.height
        nxt = order[i + 1][1] if i + 1 < len(order) else None
        yend = nxt[2] if nxt and nxt[:2] == (pi, col) else H - 45
        cx0, cx1 = col * W / 2, (col + 1) * W / 2
        spans = [s for b in p.get_text("dict")["blocks"] for l in b.get("lines", []) for s in l["spans"]
                 if cx0 - 2 <= s["bbox"][0] < cx1 and y <= s["bbox"][1] < yend and s["text"].strip()]
        mk = MARKS[q["answer"] - 1]
        color = _rgb(REVIEW_COLORS[q.get("status", "keep")])
        heads = [s for s in spans if s["text"].strip().startswith(mk)]
        if heads:
            m0 = heads[-1]
            my = (m0["bbox"][1] + m0["bbox"][3]) / 2
            same = lambda s: abs((s["bbox"][1] + s["bbox"][3]) / 2 - my) < 3
            nexts = [s["bbox"][0] for s in spans if same(s) and s["text"].strip()[:1] in MARKS and s["bbox"][0] > m0["bbox"][0] + 1]
            xlim = min(nexts) - 2 if nexts else cx1
            r = pymupdf.Rect(m0["bbox"])
            for s in spans:
                if same(s) and m0["bbox"][0] - 1 <= s["bbox"][0] < xlim:
                    r |= pymupdf.Rect(s["bbox"])
            r = pymupdf.Rect(r.x0 - 1.5, r.y0 - 1, r.x1 + 1.5, r.y1 + 1)
        else:
            # 한 줄짜리 선택지 표에서 '④RABBBT⑤RABBIT'처럼 여러 선택지가 한 span에 붙어 나오는 경우
            inner = [s for s in spans if mk in s["text"]]
            if not inner:
                missing.append(n)
                continue
            s0 = inner[-1]
            t = s0["text"]
            k = t.index(mk)
            ends = [t.index(c, k + 1) for c in MARKS if c in t[k + 1:]]
            e = min(ends) if ends else len(t)
            x0, y0, x1, y1 = s0["bbox"]
            wd = (x1 - x0) / len(t)
            r = pymupdf.Rect(x0 + wd * k - 1.5, y0 - 1, x0 + wd * e + 1.5, y1 + 1)
        p.draw_rect(r, color=color, fill=color, fill_opacity=0.22, width=0.9, overlay=True)
    return missing


def _overlay_paper(meta, qs, base, template):
    """색 없이 빌드·변환한 뒤 PDF 위에 정답 색 상자를 그려 <base>.pdf 로 저장한다."""
    import pymupdf
    plain = base + "_plain"  # 멈춘 한글이 잡고 있을 수 있는 _검토.hwpx 와 겹치지 않게 따로 만든다
    build(meta, qs, plain + ".hwpx", template=template)
    r = convert(plain + ".hwpx", None, plain + ".pdf")
    with pymupdf.open(plain + ".pdf") as d:
        missing = _mark_answers(d, qs)
        d.save(base + ".pdf", garbage=3, deflate=True)
    return r, missing


def review(files, out_dir, template="kice-sci", reuse=False, overlay=False):
    """reuse=True 이면 이미 만든 <title>_검토.pdf 를 그대로 쓰고 표지와 병합만 다시 한다.
    overlay=True 이면 글자색 대신 PDF 위에 색 상자를 그린다(한글 변환이 멈출 때의 대체 경로).
    글자색 방식에서 변환이 시간 초과로 실패하면 그 교시만 자동으로 색 상자 방식으로 바꾼다."""
    import pymupdf
    os.makedirs(out_dir, exist_ok=True)
    summary, pdfs = [], []
    for f in files:
        meta, qs = parse(open(f, encoding="utf-8").read())
        problems = check(meta, qs)
        if problems:
            raise ValueError("%s: %s" % (f, "; ".join(problems)))
        missing = [str(q["n"]) for q in qs if q.get("status") not in REVIEW_COLORS]
        if missing:
            problems.append("@status 없음: " + ", ".join(missing))
        title = meta.get("title", os.path.splitext(os.path.basename(f))[0])
        base = os.path.join(out_dir, title + "_검토")
        unmarked = []
        if reuse and os.path.exists(base + ".pdf"):
            with pymupdf.open(base + ".pdf") as d:
                r = {"pages": d.page_count}
        elif overlay:
            r, unmarked = _overlay_paper(meta, qs, base, template)
        else:
            try:
                build(meta, qs, base + ".hwpx", template=template, review=True)
                r = convert(base + ".hwpx", base + ".hwp", base + ".pdf")
            except (RuntimeError, PermissionError) as e:
                print("[알림] %s: 글자색 검토본 변환 실패 → 색 상자 방식으로 다시 만듭니다. (%s)" % (title, str(e).splitlines()[0]))
                r, unmarked = _overlay_paper(meta, qs, base, template)
        if unmarked:
            problems.append("색 표시 못 찾음: " + ", ".join(map(str, unmarked)))
        print("%s: pages=%s %s" % (title, r.get("pages"), "; ".join(problems) or "OK"))
        if str(r.get("pages")) != str(meta.get("pages", "4")):
            problems.append("쪽수 %s (기대 %s)" % (r.get("pages"), meta.get("pages", "4")))
        summary.append((title, [(q["n"], q.get("status", "keep"), q["answer"]) for q in qs], problems))
        pdfs.append(base + ".pdf")

    merged = pymupdf.open()
    for p in pdfs:
        with pymupdf.open(p) as d:
            merged.insert_pdf(d)
    first = merged[0].rect
    _cover(merged, summary, (first.width, first.height))
    out = os.path.join(out_dir, "검토본.pdf")
    merged.subset_fonts()  # 표지에 넣은 한글 글꼴 전체가 들어가지 않도록
    merged.save(out, garbage=4, deflate=True)
    print("merged", out, "pages=%d" % merged.page_count)
    return 0
