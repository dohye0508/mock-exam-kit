"""평가원 양식 '정답 및 해설' PDF를 만든다(3단 편집, 첫 쪽에 제목 상자·정답 격자).
  python tools/build_key.py out.pdf content/1교시.md content/2교시.md ...      # 교시마다 content/N교시_해설.md를 읽는다
  python tools/build_key.py out.pdf --answers-only content/1교시.md ...        # 해설 없이 정답 격자만(= 정답표)

해설 파일 형식(content/N교시_해설.md):
  ## 1. [출제의도] 한 구절
  @answer 3            ← content md의 정답과 대조한다(다르면 경고)
  본문 문단(빈 줄로 구분). 서식: <b> <i> <sub> <sup> 와 유니코드 기호.
교시 md 머리의 year, exam, area, subject를 제목에 쓴다.
"""
import html, os, re, shutil, sys, tempfile
import pymupdf as fitz

FONTS = "C:/Windows/Fonts"
BODY, BOLD = "HANBatang.ttf", "HANBatangB.ttf"
CIRC = "①②③④⑤"
W, H = 595.0, 842.0
CSS = """
@font-face { font-family: hb; src: url(@BODY@); }
@font-face { font-family: hb; font-weight: bold; src: url(@BOLD@); }
body { font-family: hb; font-size: 7.6pt; line-height: 1.32; text-align: justify; }
p { margin: 0 0 2pt 0; }
h3 { font-size: 8.2pt; font-weight: bold; margin: 5pt 0 1.5pt 0; }
.sec { text-align: center; font-size: 12pt; font-weight: bold; margin: 8pt 0 4pt 0; }
.area { text-align: center; font-size: 11pt; font-weight: bold; margin: 4pt 0 3pt 0; border: 1.5pt solid black; padding: 3pt 0; }
table { border-collapse: collapse; margin: 0 0 4pt 0; width: 100%; }
td { border: 0.5pt solid black; font-size: 7.2pt; text-align: center; padding: 1.2pt 0; }
td.n { font-weight: bold; }
""".replace("@BODY@", BODY).replace("@BOLD@", BOLD)


def read_meta_answers(md):
    s = open(md, encoding="utf8").read()
    meta = dict(re.findall(r"^(\w+):\s*(.+)$", s.split("\n---", 1)[0], re.M))
    ans = {}
    for q in re.split(r"(?m)^(?=## \d+\.)", s)[1:]:
        ans[int(re.match(r"## (\d+)\.", q).group(1))] = int(re.search(r"^@answer (\d)", q, re.M).group(1))
    return meta, ans


def read_explanations(path):
    s = open(path, encoding="utf8").read().replace("\r\n", "\n")
    out = {}
    for q in re.split(r"(?m)^(?=## \d+\.)", s)[1:]:
        head, _, body = q.partition("\n")
        n = int(re.match(r"## (\d+)\.", head).group(1))
        title = re.sub(r"^## \d+\.\s*", "", head)
        m = re.match(r"\s*@answer (\d)\s*\n", body)
        a = int(m.group(1)) if m else None
        body = body[m.end():] if m else body
        paras = [p.strip().replace("\n", " ") for p in re.split(r"\n\s*\n", body.strip()) if p.strip()]
        out[n] = (title, a, paras)
    return out


def esc_keep_tags(t):
    t = html.escape(t, quote=False)
    return re.sub(r"&lt;(/?(?:b|i|sub|sup))&gt;", r"<\1>", t)


def grid_html(ans):
    rows = []
    for r in range(4):
        cells = "".join('<td class="n" style="width:11%%">%d</td><td style="width:9%%">%s</td>' % (r * 5 + c + 1, CIRC[ans[r * 5 + c + 1] - 1])
                        for c in range(5))
        rows.append("<tr>%s</tr>" % cells)
    return '<table style="width:100%%">%s</table>' % "".join(rows)


def section_html(period, meta, ans, expl):
    area = meta.get("area", "탐구")
    area = area if area.endswith("영역") else area + " 영역"
    parts = ['<div class="area">• %s %s •</div>' % (html.escape(meta.get("period", "").replace("제", "").strip() or period), html.escape(area)),
             '<div class="sec">[%s]</div>' % html.escape(meta.get("subject", "")), grid_html(ans)]
    for n in sorted(expl):
        title, _, paras = expl[n]
        parts.append("<h3>%d. %s</h3>" % (n, esc_keep_tags(title)))
        parts += ["<p>%s</p>" % esc_keep_tags(p) for p in paras]
    return "".join(parts)


def reg(page):
    page.insert_font(fontname="hb", fontfile=os.path.join(FONTS, BOLD))


def draw_title(page, meta):
    r = fitz.Rect(40, 40, W - 40, 118)
    page.draw_rect(r, width=1.5, radius=0.12)
    f = fitz.Font(fontfile=os.path.join(FONTS, BOLD))
    for y, t, sz in ((72, "%s %s" % (meta.get("year", ""), meta.get("exam", "")), 20), (104, "정답 및 해설", 26)):
        page.insert_text(((W - f.text_length(t, fontsize=sz)) / 2, y), t, fontname="hb", fontsize=sz)


def build(out_pdf, mds, answers_only=False):
    tmp = tempfile.mkdtemp()
    for f in (BODY, BOLD):
        shutil.copy(os.path.join(FONTS, f), tmp)
    arch = fitz.Archive(tmp)
    doc = fitz.open()
    problems = []
    for md in mds:
        meta, ans = read_meta_answers(md)
        period = re.search(r"(\d)교시", os.path.basename(md)).group(1) + "교시"
        meta["period"] = period
        expl = {}
        if not answers_only:
            ep = md.replace(".md", "_해설.md")
            expl = read_explanations(ep)
            for n, (_, a, _) in expl.items():
                if a is not None and a != ans.get(n):
                    problems.append("%s %d번: 해설 @answer %s ≠ 문항 @answer %s" % (period, n, a, ans.get(n)))
            miss = sorted(set(ans) - set(expl))
            if miss:
                problems.append("%s 해설이 없는 문항: %s" % (period, miss))
        story = fitz.Story(section_html(period, meta, ans, expl), user_css=CSS, archive=arch)
        tmp_pdf = os.path.join(tmp, "sec_%s.pdf" % period)
        cw = (W - 80 - 20) / 3
        mediabox = fitz.paper_rect("a4")

        writer = fitz.DocumentWriter(tmp_pdf)
        pg = 0
        while True:
            dev = writer.begin_page(mediabox)
            top = 138 if pg == 0 else 50
            more = 1
            for col in range(3):
                x0 = 40 + col * (cw + 10)
                more, _ = story.place(fitz.Rect(x0, top, x0 + cw, 790))
                story.draw(dev)
                if not more:
                    break
            writer.end_page()
            pg += 1
            if not more:
                break
        writer.close()
        sec = fitz.open(tmp_pdf)
        fnt = fitz.Font(fontfile=os.path.join(FONTS, BOLD))
        for k, page in enumerate(sec):
            reg(page)
            top = 138 if k == 0 else 50
            if k == 0:
                draw_title(page, meta)
            for c in (1, 2):
                x = 40 + c * (cw + 10) - 5
                page.draw_line((x, top), (x, 790), width=0.5)
            num = str(k + 1)
            page.insert_text(((W - fnt.text_length(num, fontsize=14)) / 2, 822), num, fontname="hb", fontsize=14)
        if sec.page_count % 2:                      # 교시마다 짝수 쪽으로(뒷면은 여백 쪽)
            pg = sec.new_page(width=W, height=H)
            reg(pg)
            t = "이 면은 여백입니다."
            pg.draw_rect(fitz.Rect(W / 2 - 115, 400, W / 2 + 115, 450), width=0.6, radius=0.3)
            pg.insert_text((W / 2 - fnt.text_length(t, fontsize=17) / 2, 432), t, fontname="hb", fontsize=17)
        doc.insert_pdf(sec)
        sec.close()
    shutil.rmtree(tmp, ignore_errors=True)
    return doc, problems


if __name__ == "__main__":
    args = sys.argv[1:]
    only = "--answers-only" in args
    args = [a for a in args if a != "--answers-only"]
    doc, problems = build(args[0], args[1:], only)
    doc.save(args[0])
    print(args[0], doc.page_count, "쪽")
    for p in problems:
        print("[경고]", p)
