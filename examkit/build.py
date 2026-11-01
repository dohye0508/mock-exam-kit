# -*- coding: utf-8 -*-
"""문항 dict → HWPX 패키지.

양식 폴더(templates/<name>/)는 원본 HWP를 HWPX로 풀어 둔 것이며,
  Contents/section0.xml 의 첫 문단(p0: 구역 설정 + 머리글 + 제목 표)을 그대로 쓰고 뒤에 문항 본문을 붙인다.
  frags/p0.xml 은 그 첫 문단만 따로 저장한 것. 제목 글자는 HEADER_RULES 로 치환한다.
"""
import os, re, shutil, zipfile
from . import hwpx, materials
from .figures import render

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATES = os.path.join(ROOT, "templates")


def _header_rules(meta):
    """kice-sci 양식의 제목 글자 치환 규칙. (원본 → 새 글자)"""
    subj = meta.get("subject", "")
    area = re.sub(r"\s*영역$", "", meta.get("area", "과학탐구"))   # "○○ 영역"으로 적어도 "영역 영역"이 되지 않게
    box_w = max(15941, (len(subj) + 2) * 2700)   # 과목명 길이에 맞춘 글상자 폭(원본 "(화학Ⅰ)"은 15941)
    return [
        # 짝수 쪽 머리글의 과목명 글상자: 원본은 "(화학Ⅰ)" 폭(15941)으로 고정이라 긴 과목명이 두 줄로 꺾여 본문을 덮친다
        (re.compile(r'(<hp:curSz width=")15941(" height="3685"/>)'), r"\g<1>%d\g<2>" % box_w),
        (re.compile(r'(<hp:drawText lastWidth=")15941(")'), r"\g<1>%d\g<2>" % box_w),
        (re.compile(r'(<hp:sz width=")15941(" widthRelTo="ABSOLUTE" height="3685")'), r"\g<1>%d\g<2>" % box_w),
        (re.compile(r'(<hp:rotationInfo angle="0" centerX=")7970(" centerY="1842")'), r"\g<1>%d\g<2>" % (box_w // 2)),
        ("2025학년도 대학수학능력시험 문제지", "%s %s 문제지" % (meta.get("year", "2025학년도"), meta.get("exam", "대학수학능력시험"))),
        ("과학탐구", area),
        # 둥근 상자의 "제 4 교시"는 전각 공백(fwSpace)으로 띄워져 있다
        ("<hp:t>제<hp:fwSpace/>4<hp:fwSpace/>교시</hp:t>",
         "<hp:t>제<hp:fwSpace/>%s<hp:fwSpace/>교시</hp:t>" % (re.sub(r"\D", "", meta.get("period", "")) or "4")),
        # 과목명 "(화학Ⅰ)" 은 '(화' '학' 'Ⅰ' ')' 네 run 으로 쪼개져 있음
        (re.compile(r'(<hp:run charPrIDRef="(?:30|31)"><hp:t>)\(화(</hp:t>)'), r"\1(" + subj[:1] + r"\2"),
        (re.compile(r'(<hp:run charPrIDRef="(?:30|49)"><hp:t>)학(</hp:t>)'), r"\1" + subj[1:] + r"\2"),
        ('<hp:t charStyleIDRef="20">학<hp:fwSpace/></hp:t>', '<hp:t charStyleIDRef="20">%s</hp:t>' % subj[1:]),
        (re.compile(r'(<hp:run charPrIDRef="(?:82|81)"><hp:t>)[IⅠ](</hp:t>)'), r"\1\2"),
    ]


# 검토본에서 정답 선택지를 칠하는 색: 그대로 / 수정 / 새 문제·발전
REVIEW_COLORS = {"keep": "#D62718", "mod": "#12884A", "new": "#1E5BD8"}
REVIEW_BASE_CHAR = "10"   # 선택지 글자 모양을 복제해 색과 굵기만 바꾼다


def _add_review_chars(header_xml):
    """header.xml 끝에 색 입힌 선택지 글자 모양을 추가하고 {status: charPr id}를 돌려준다."""
    m = re.search(r'<hh:charProperties itemCnt="(\d+)">', header_xml)
    count = int(m.group(1))
    base = re.search(r'<hh:charPr id="%s".*?</hh:charPr>' % REVIEW_BASE_CHAR, header_xml, re.S).group(0)
    ids, added = {}, ""
    for i, (status, color) in enumerate(REVIEW_COLORS.items()):
        new_id = str(count + i)
        c = re.sub(r'id="\d+"', 'id="%s"' % new_id, base, count=1)
        c = re.sub(r'textColor="#[0-9A-Fa-f]{6}"', 'textColor="%s"' % color, c, count=1)
        c = c.replace("<hh:underline", "<hh:bold/><hh:underline", 1)
        added += c
        ids[status] = new_id
    header_xml = header_xml.replace(m.group(0), '<hh:charProperties itemCnt="%d">' % (count + len(ids)), 1)
    header_xml = header_xml.replace("</hh:charProperties>", added + "</hh:charProperties>", 1)
    return header_xml, ids


def build_question(q, img_sink, review_ids=None):
    mark = None
    if review_ids and q.get("answer"):
        mark = (q["answer"] - 1, review_ids.get(q.get("status", "keep"), review_ids["keep"]))
    parts = [hwpx.q_head(q["n"], q["head"])]
    blocks = list(q["blocks"])
    for i, (kind, payload) in enumerate(blocks):
        if kind == "skip":
            continue
        nxt = blocks[i + 1] if i + 1 < len(blocks) else None
        if kind in ("box", "table") and nxt and nxt[0] == "figure" and nxt[1]["kv"].get("side"):
            # 자료 상자·표 오른쪽에 삽화를 나란히 놓는다: ::: figure file … side=right
            parts.append(_side_by_side(q, kind, payload, nxt[1], img_sink))
            blocks[i + 1] = ("skip", None)
            continue
        if kind == "box":
            parts.append(hwpx.databox(payload))
        elif kind == "table":
            parts.append(hwpx.datatable(payload["headers"], payload["rows"], payload["widths"], row_h=payload["row_h"]))
        elif kind == "figure":
            parts.append(_figure(q, payload, img_sink))
        elif kind == "dialog":
            parts.append(hwpx.dialog(payload))
        elif kind == "text":
            parts.append(hwpx.q_line(payload))
    ask = q["ask"] + (" [3점]" if q["three"] else "")
    parts.append(hwpx.q_line(ask))
    if "bogi" in q:
        parts.append(hwpx.bogi(q["bogi"]))
        parts.append(hwpx.choices10(q["set"], mark=mark))
    elif "grid" in q:
        parts.append(hwpx.grid(*q["grid"], mark=mark))
    elif "opts" in q:
        # 한 줄 선택지 칸(약 16.9mm)에 넉넉히 들어갈 때만 한 줄로 늘어놓는다(영문 단어는 글자 수보다 넓다)
        if q.get("inline_opts") or all(len(o) <= 6 and hwpx.text_mm(o, "10") <= 12.5 for o in q["opts"]):
            parts.append(hwpx.choices10(q["opts"], mark=mark))
        else:
            parts.append(hwpx.choice_lines(q["opts"], mark=mark))
    body = hwpx.keep_together("".join(parts), pb=q["pb"], cb=q["cb"])
    return body + "".join(hwpx.blank() for _ in range(q["gap"]))


def _side_by_side(q, kind, payload, fig, img_sink):
    fw = int(fig["kv"].get("w", 11000))
    gap = 600
    lw = hwpx.COL_W - fw - gap
    if kind == "box":
        # 상자 문단(paraPr 36)의 왼쪽 들여쓰기만큼 좁혀야 칸 밖으로 잘리지 않는다
        left = hwpx.databox(payload, width=lw - 1135)
    else:
        widths = payload["widths"] or [hwpx.COL_W // len(payload["headers"])] * len(payload["headers"])
        widths = [int(w * lw / sum(widths)) for w in widths]
        widths = [int(w * (lw - 1135) / lw) for w in widths]
        left = hwpx.datatable(payload["headers"], payload["rows"], widths, width=lw - 1135, row_h=payload["row_h"])
    right = _figure(q, fig, img_sink, para_w=fw + gap)
    return hwpx.side_by_side(left, right, lw, fw + gap)


def _figure(q, payload, img_sink, para_w=None):
    kv, params = payload["kv"], payload["params"]
    width = int(kv.get("w", 19000))
    if payload["kind"] == "file" or "file" in kv:
        # 외부에서 만든 그림(삽화 등)을 그대로 넣는다: ::: figure file path=assets/illust/x.png w=25512 [h=17008]
        # cx=<px>: 원본의 이 x(px)가 그림 가운데에 오도록 한쪽에 흰 여백을 덧댄다(옆에 펜 등이 붙은 틀의 판을 가운데로)
        png, pw, ph, pad = _external_png(kv.get("path") or kv["file"], width, kv.get("h"),
                                         os.path.join(img_sink.workdir, "fig_q%02d_%d.png" % (q["n"], len(img_sink.items))),
                                         cx=kv.get("cx"), crop=kv.get("crop"))
        # 얹는 글의 좌표는 덧댄 여백을 뺀 원본 그림의 왼쪽 위 기준(_pad_x·_pad_y: 여백 HWPUNIT)
        params = dict(params, _pad_x=pad[0] * width / pw, _pad_y=pad[1] * width / pw)
    elif payload["kind"] in materials.KINDS:
        # 안내문·메신저·기사 등 글자가 든 자료는 HTML로 지면 실제 폭에 맞춰 그린다
        png, pw, ph = materials.render(payload["kind"], params, os.path.join(
            img_sink.workdir, "fig_q%02d_%d.png" % (q["n"], len(img_sink.items))), width)
    else:
        # 그림 원본을 지면 폭의 1.25배로 그려 줄여 넣는다. 글씨가 지면에서 약 8pt가 되도록 figures 쪽 글자 크기를 맞춰 둠
        params = dict(params)
        params.setdefault("inch_w", "%.2f" % (width / 7200 * 1.25))
        png, pw, ph = render(payload["kind"], params, os.path.join(img_sink.workdir, "fig_q%02d_%d.png" % (q["n"], len(img_sink.items))))
    image_id = img_sink.add(png)
    overlay = _overlay(params, width, para_w or PARA_W) if payload["kind"] == "file" or "file" in kv else ""
    return hwpx.pic(image_id, pw, ph, width, caption=kv.get("caption"), overlay=overlay)


PARA_W = 31692  # 문항을 감싸는 표 칸의 글 너비(keep_together). 그림은 이 안에서 가운데 정렬된다.


def _overlay(params, width, para_w=None):
    """삽화 위에 얹는 말풍선·이름표·자료판. 좌표는 그림 왼쪽 위 기준 mm.
    bubbleN: x,y,w,h,꼬리x,꼬리y | 대사 (bubble_align: center면 가운데 정렬)     labelN: x,y[,w] | 갑     board: x,y,w,h + board_table: 머리|머리 ; 칸|칸"""
    ox = ((para_w or PARA_W) - width) / 2 / hwpx.MM + float(params.get("_pad_x", 0)) / hwpx.MM
    oy = float(params.get("oy", 0)) + float(params.get("_pad_y", 0)) / hwpx.MM
    out = []
    if "board" in params:
        x, y, w, h = (float(v) for v in params["board"].split(","))
        rows = [[c.strip() for c in r.split("|")] for r in params.get("board_table", "").split(";") if r.strip()]
        widths = [int(v) for v in params["board_widths"].split(",")] if "board_widths" in params else None
        inner = hwpx.datatable(rows[0], rows[1:], widths=widths, width=int((w - 3) * hwpx.MM), row_h=1300) if rows else ""
        out.append(hwpx.board(x + ox, y + oy, w, h, inner))
    for key in sorted((k for k in params if re.fullmatch(r"bubble\d+", k)), key=lambda k: int(k[6:])):
        geo, text = params[key].split("|", 1)
        x, y, w, h, tx, ty = (float(v) for v in geo.split(","))
        out.append(hwpx.bubble(x + ox, y + oy, w, h, (tx + ox, ty + oy), text.strip(), charpr=params.get("font", "39"),
                               align=params.get("bubble_align", "left")))
    for key in sorted(k for k in params if re.fullmatch(r"label\d+", k)):
        geo, text = params[key].split("|", 1)
        g = [float(v) for v in geo.split(",")]
        out.append(hwpx.label(g[0] + ox, g[1] + oy, text.strip(), *g[2:3]))
    # 틀 그림(ChatGPT)의 빈 판에 얹는 글과 표
    #   textN: x,y,w,h[,정렬] | 문단1 / 문단2   정렬: left·center·right·justify·item(◦ 내어쓰기), 뒤에 @170·@200을 붙이면 줄 간격
    #   textN_font: charPr id(기본 39=10pt), textN_valign: TOP·CENTER·BOTTOM, textN_wrap: 0이면 미리 줄바꿈 끔(<br>로 직접),
    #   textN_box: 1이면 흰 바탕·테두리 상자(그림에 빈 판이 없거나 너무 작을 때 이름표 상자로)
    #   tableN: x,y,w,h  + tableN_rows: 머리|머리 ; 칸|칸   + tableN_widths: 3000,8000 (생략하면 균등), tableN_rowh: 줄 높이 mm
    for key in sorted(k for k in params if re.fullmatch(r"text\d+", k)):
        geo, text = params[key].split("|", 1)
        g = [v.strip() for v in geo.split(",")]
        x, y, w, h = (float(v) for v in g[:4])
        align = g[4] if len(g) > 4 else "left"
        font = params.get(key + "_font", "39")
        wrap = params.get(key + "_wrap", "1") == "1"
        paras = "".join(hwpx.text_para(hwpx.prewrap(t.strip(), w, font, 3.2 if align.startswith("item") else 0) if wrap else t.strip(),
                                       hwpx.OVERLAY_PARA[align], "0", font) for t in text.split(" / "))
        boxed = params.get(key + "_box", "0") == "1"
        out.append(hwpx.float_rect((x + ox) * hwpx.MM, (y + oy) * hwpx.MM, w * hwpx.MM, h * hwpx.MM, paras,
                                   line=34 if boxed else 0, fill=boxed, margin=(0, 0, 0, 0),
                                   valign=params.get(key + "_valign", "TOP")))
    for key in sorted(k for k in params if re.fullmatch(r"table\d+", k)):
        x, y, w, h = (float(v) for v in params[key].split(","))
        rows = [[c.strip() for c in r.split("|")] for r in params.get(key + "_rows", "").split(";") if r.strip()]
        n = len(rows[0])
        tw = int((w - 2) * hwpx.MM)
        widths = [int(v) for v in params[key + "_widths"].split(",")] if key + "_widths" in params else [tw // n] * n
        rh = int(float(params.get(key + "_rowh", 0)) * hwpx.MM) or 1000
        inner = hwpx.datatable(rows[0], rows[1:], widths=widths, width=sum(widths), hdr_h=rh, row_h=rh,
                               charpr=params.get(key + "_font", "56"), margin=(170, 170, 60, 60),
                               para_style=(hwpx.OVERLAY_PARA["center"], "0", "10"))
        out.append(hwpx.float_rect((x + ox) * hwpx.MM, (y + oy) * hwpx.MM, w * hwpx.MM, h * hwpx.MM, inner,
                                   line=0, fill=False, margin=(0, 0, 0, 0), valign=params.get(key + "_valign", "CENTER")))
    return "".join(out)


def _extend_masterpages(cdir, n):
    """양식의 바탕쪽은 4쪽짜리(1~3쪽 머리글, 4쪽에 '확인 사항')다. n쪽이면 짝수쪽·홀수쪽 바탕쪽을 늘리고 '확인 사항'은 마지막 쪽으로 옮긴다."""
    read = lambda i: open(os.path.join(cdir, "masterpage%d.xml" % i), encoding="utf-8").read()
    even, odd, last = read(2), read(3), read(4)
    for i in range(4, n + 1):
        src = last if i == n else (even if i % 2 == 0 else odd)
        s = re.sub(r'id="masterpage\d+"', 'id="masterpage%d"' % i, src, count=1)
        s = re.sub(r'pageNumber="\d+"', 'pageNumber="%d"' % i, s, count=1)
        open(os.path.join(cdir, "masterpage%d.xml" % i), "w", encoding="utf-8").write(s)
    sec = os.path.join(cdir, "section0.xml")
    s = open(sec, encoding="utf-8").read()
    s = re.sub(r'masterPageCnt="\d+"', 'masterPageCnt="%d"' % (n + 1), s, count=1)
    s = s.replace('<hp:masterPage idRef="masterpage4"/>',
                  "".join('<hp:masterPage idRef="masterpage%d"/>' % i for i in range(4, n + 1)), 1)
    open(sec, "w", encoding="utf-8").write(s)
    hpf = os.path.join(cdir, "content.hpf")
    s = open(hpf, encoding="utf-8").read()
    item = re.search(r'<opf:item id="masterpage4"[^>]*/>', s).group(0)
    s = s.replace(item, "".join(item.replace("masterpage4", "masterpage%d" % i) for i in range(4, n + 1)), 1)
    open(hpf, "w", encoding="utf-8").write(s)


def _external_png(path, width, height, out_png, cx=None, crop=None):
    """투명 부분은 흰색으로 채우고, h를 주면 그 가로세로비가 되도록 흰 여백을 덧댄다(잘라 내지 않음).
    cx를 주면 원본의 그 x(px)가 가운데에 오도록 먼저 한쪽에 여백을 덧댄다. 원본이 놓인 왼쪽 위 위치(px)도 돌려준다."""
    from PIL import Image
    if not os.path.isabs(path) and not os.path.exists(path):
        path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), path)
    with Image.open(path) as src:
        im = src.convert("RGBA")
    flat = Image.new("RGB", im.size, "white")
    flat.paste(im, mask=im.getchannel("A"))
    ox = oy = 0
    if crop:
        # crop=x0,y0,x1,y1(원본 px): 삽화의 빈 바닥·하늘을 잘라 높이를 줄인다. 얹는 글 좌표는 그대로 원본 왼쪽 위 기준
        x0, y0, x1, y1 = (int(float(v)) for v in crop.split(","))
        flat = flat.crop((x0, y0, x1, y1))
        ox, oy = -x0, -y0
    if cx:
        w, h = flat.size
        cx = float(cx)
        W = round(2 * max(cx, w - cx))
        dx = W - w if cx < w / 2 else 0
        canvas = Image.new("RGB", (W, h), "white")
        canvas.paste(flat, (dx, 0))
        ox += dx
        flat = canvas
    if height:
        want = width / float(height)
        w, h = flat.size
        if abs(w / h - want) > 0.005:
            W, H = (round(h * want), h) if w / h < want else (w, round(w / want))
            canvas = Image.new("RGB", (W, H), "white")
            canvas.paste(flat, ((W - w) // 2, (H - h) // 2))
            ox, oy = ox + (W - w) // 2, oy + (H - h) // 2
            flat = canvas
    os.makedirs(os.path.dirname(out_png), exist_ok=True)
    flat.save(out_png)
    return (out_png,) + flat.size + ((ox, oy),)


class ImageSink:
    def __init__(self, workdir):
        self.workdir = workdir
        self.items = []  # (id, src_path)

    def add(self, path):
        iid = "fig%d" % (len(self.items) + 1)
        self.items.append((iid, path))
        return iid


def _add_overlay_paras(header_xml):
    """그림 위 글상자용 문단 모양: 원본을 복제해 정렬·줄 간격을 바꾸고 내어쓰기 항목은 왼쪽 정렬로(어절 단위 줄바꿈은 build에서 일괄)."""
    m = re.search(r'<hh:paraProperties itemCnt="(\d+)">', header_xml)
    count = int(m.group(1))
    added, ids = "", {}
    i = 0
    # 정렬별로 줄 간격 기본(140%)·100%·170%·200%를 만든다. 이름은 left, left@100, left@170, left@200 …
    for name, base_id, align in (("left", "46", "LEFT"), ("center", "64", "CENTER"), ("right", "8", "RIGHT"),
                                 ("justify", "10", "LEFT"), ("item", "71", "LEFT")):
        base = re.search(r'<hh:paraPr id="%s".*?</hh:paraPr>' % base_id, header_xml, re.S).group(0)
        for spacing in (None, 100, 170, 200):
            c = re.sub(r'id="\d+"', 'id="%d"' % (count + i), base, count=1)
            c = re.sub(r'<hh:align horizontal="\w+"', '<hh:align horizontal="%s"' % align, c, count=1)
            if spacing:
                c = re.sub(r'(lineSpacing type="PERCENT" value=")\d+', r'\g<1>%d' % spacing, c)
            added += c
            ids[name + ("@%d" % spacing if spacing else "")] = str(count + i)
            i += 1
    header_xml = header_xml.replace(m.group(0), '<hh:paraProperties itemCnt="%d">' % (count + len(ids)), 1)
    header_xml = header_xml.replace("</hh:paraProperties>", added + "</hh:paraProperties>", 1)
    return header_xml, ids


def build(meta, questions, out_hwpx, template="kice-sci", workdir=None, review=False):
    """review=True 이면 각 문항의 정답 선택지를 @status 색(REVIEW_COLORS)으로 칠한 검토본을 만든다."""
    tpl = os.path.join(TEMPLATES, template)
    workdir = workdir or (os.path.splitext(out_hwpx)[0] + "_build")
    if os.path.exists(workdir):
        shutil.rmtree(workdir)
    shutil.copytree(tpl, workdir, ignore=shutil.ignore_patterns("frags", "Preview"))
    sink = ImageSink(workdir)

    review_ids = None
    hp = os.path.join(workdir, "Contents", "header.xml")
    header_xml, para_ids = _add_overlay_paras(open(hp, encoding="utf-8").read())
    hwpx.OVERLAY_PARA.clear()
    hwpx.OVERLAY_PARA.update(para_ids)
    if review:
        header_xml, review_ids = _add_review_chars(header_xml)
    # 한글 낱말이 줄 끝에서 쪼개지지 않게('처음으/로') 모든 문단을 어절 단위 줄바꿈으로.
    # 한글(2022) 실측: breakNonLatinWord="BREAK_WORD"가 어절 단위, "KEEP_WORD"가 글자 단위로 끊는다(이름과 반대)
    header_xml = header_xml.replace('breakNonLatinWord="KEEP_WORD"', 'breakNonLatinWord="BREAK_WORD"')
    open(hp, "w", encoding="utf-8").write(header_xml)

    src_sec = open(os.path.join(tpl, "Contents", "section0.xml"), encoding="utf-8").read()
    prefix = src_sec[:src_sec.index("<hp:p ")]
    p0 = open(os.path.join(tpl, "frags", "p0.xml"), encoding="utf-8").read()
    for old, new in _header_rules(meta):
        p0 = old.sub(new, p0) if hasattr(old, "sub") else p0.replace(old, new)

    body = "".join(build_question(q, sink, review_ids) for q in questions)
    # '~'는 한글 글꼴에서 위로 떠 보이므로 본문 글자(<hp:t>)만 가운데 높이의 '∼'(U+223C)로 바꾼다. 수식 스크립트의 '~'(띄어쓰기)는 그대로 둔다
    body = re.sub(r"(<hp:t(?: [^>]*)?>)(.*?)(</hp:t>)", lambda m: m.group(1) + m.group(2).replace("~", "∼") + m.group(3), body, flags=re.S)
    open(os.path.join(workdir, "Contents", "section0.xml"), "w", encoding="utf-8").write(prefix + p0 + body + "</hs:sec>")

    pages = meta.get("pages", "4")
    if int(pages) > 4:
        _extend_masterpages(os.path.join(workdir, "Contents"), int(pages))
    for i in range(1, 13):
        mp = os.path.join(workdir, "Contents", "masterpage%d.xml" % i)
        if not os.path.exists(mp):
            break
        s = open(mp, encoding="utf-8").read()
        nums = iter([str(i), pages])
        s = re.sub(r"<hp:t>\d+</hp:t>", lambda m: "<hp:t>%s</hp:t>" % next(nums), s, count=2)
        open(mp, "w", encoding="utf-8").write(s)

    # 그림 → BinData + manifest
    if sink.items:
        hpf = os.path.join(workdir, "Contents", "content.hpf")
        s = open(hpf, encoding="utf-8").read()
        items = ""
        for iid, path in sink.items:
            dst = os.path.join(workdir, "BinData", iid + ".png")
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy(path, dst)
            items += '<opf:item id="%s" href="BinData/%s.png" media-type="image/png" isEmbeded="1"/>' % (iid, iid)
        s = s.replace("</opf:manifest>", items + "</opf:manifest>")
        open(hpf, "w", encoding="utf-8").write(s)

    if os.path.exists(out_hwpx):
        os.remove(out_hwpx)
    with zipfile.ZipFile(out_hwpx, "w") as z:
        z.write(os.path.join(workdir, "mimetype"), "mimetype", compress_type=zipfile.ZIP_STORED)
        for root, _, files in os.walk(workdir):
            for f in files:
                full = os.path.join(root, f)
                arc = os.path.relpath(full, workdir).replace("\\", "/")
                if arc == "mimetype" or f.startswith("fig_q"):
                    continue
                z.write(full, arc, compress_type=zipfile.ZIP_DEFLATED)
    return out_hwpx
