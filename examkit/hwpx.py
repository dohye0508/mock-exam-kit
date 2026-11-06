# -*- coding: utf-8 -*-
"""HWPX 본문 조각 빌더.

평가원 양식(templates/kice-sci)의 header.xml에 정의된 문단/글자 모양 ID를 그대로 참조해
문항 요소(문항 번호 문단, 자료 상자, <보기> 표, 선택지 표, 짝짓기 표, 데이터 표, 그림, 수식)를
XML 문자열로 만든다. 서식 ID 상수는 STYLE 딕셔너리에 모아 두었으므로 다른 양식을 쓰려면 이 값만 바꾼다.
"""
import re
from xml.sax.saxutils import escape as esc

# 양식(kice-sci)의 서식 ID. (paraPr, style, charPr)
STYLE = dict(
    q_head=("70", "1", "9", "85", "107"),   # 번호 / 공백 / 발문
    q_line=("36", "3", "10", "42"),          # 들여쓰기 공백 / 질문
    box_para=("71", "2", "10"), box_heading_char="52",
    bogi_item=("59", "52", "137"), bogi_text_char="10",
    choice_line=("98", "4", "10"),
    blank=("98", "4", "119"),
    center=("64", "0", "10"),
    table_head=("25", "5", "16"), table_body=("3", "15", "83"),
    frac=("69", "1", "45"),
    underline_char="11",
    pic_para=("108", "3", "10"),
)
BF = dict(box_tbl="6", box_cell="8", bogi_tbl="22", bogi_top="23", bogi_label="13",
          bogi_l="24", bogi_r="25", bogi_body="26", choices="31", grid="17", table="3",
          frac_top="19", frac_bottom="20")
COL_W = 30557          # 자료 상자/표의 기본 너비(단 너비)
CELL_W = 31692         # 문항을 감싸는 칸의 실제 폭(= 단 폭). 이보다 넓으면 오른쪽 테두리가 잘린다
INDENT = 2260          # 상자·표·보기를 담는 문단(paraPr 36·92)의 왼쪽 들여쓰기
OVERLAY_PARA = {}      # build가 header.xml에 추가한 '어절 단위 줄바꿈' 문단 모양 {정렬: id}
LINE_H = 1420          # 11.5pt 한 줄 높이(대략)
PID = 'id="2147483648"'

_id = [1900000000]
_z = [600]


def nid():
    _id[0] += 1
    return str(_id[0])


def nz():
    _z[0] += 1
    return str(_z[0])


# ---------------- 인라인 마크업 ----------------
_INLINE = re.compile(r"(\$[^$]+\$|__[^_]+__|\{\{frac\|[^|}]+\|[^}]+\}\})")


_EQ_WORDS = re.compile(r"\b(?:over|times|rm|it|LEFT|RIGHT|cdot|le|ge)\b")


def _eq_len(script):
    """수식 폭 추정용 글자 수. 분수는 위·아래 중 긴 쪽, 첨자 붙은 sum/int는 기호 2칸으로 센다."""
    s = re.sub(r"\b(?:sum|int)\s*(?:[_^]\s*\{[^{}]*\}\s*)*", "xx", script)
    frac = re.compile(r"\{([^{}]*)\}\s*over\s*\{([^{}]*)\}")
    while frac.search(s):
        s = frac.sub(lambda m: "x" * max(len(m.group(1).replace(" ", "")), len(m.group(2).replace(" ", ""))), s)
    return len(re.sub(r"[{}_^ `~]", "", _EQ_WORDS.sub("", s)))


def _eq_size(script):
    """(height, baseLine). 양식의 실제 값: 보통 1125/85, 첨자 1350/71, 분수 2580/65."""
    if re.search(r"\b(?:sum|int)\b", script) and re.search(r"[_^]", script):
        return 2750, 62  # 위아래 첨자가 붙은 Σ·∫는 분수보다 조금 높다
    if re.search(r"\bover\b", script):
        return 2580, 65
    if re.search(r"[_^]", script):
        return 1350, 71
    return 1125, 85


_LATEX_SYM = {
    r"\le": " <= ", r"\leq": " <= ", r"\ge": " >= ", r"\geq": " >= ", r"\neq": " != ", r"\ne": " != ",
    r"\times": " times ", r"\cdot": " cdot ", r"\pm": " +- ", r"\infty": " inf ", r"\pi": " pi ",
    r"\alpha": " alpha ", r"\beta": " beta ", r"\theta": " theta ", r"\Delta": " DELTA ",
    r"\cdots": " cdots ", r"\ldots": " cdots ", r"\rightarrow": " -> ", r"\to": " -> ",
    r"\quad": " ~~ ", r"\,": " ` ", r"\;": " ` ", r"\{": " lbrace ", r"\}": " rbrace ", r"\%": "%",
}


def latex_to_hwp(src):
    r"""LaTeX 수식을 한글 수식 스크립트로 바꾼다. \frac, \sqrt, \sum, \left|…\right|, ^ _, 자주 쓰는 기호만 다룬다."""
    s = src.strip()
    if "\\" not in s and not re.search(r"[_^](\w|\{)", s):
        return s                                    # 이미 한글 수식 문법이거나 단순 식
    if re.search(r"\b(over|sum|sqrt)\b", s) and "\\" not in s:
        return s                                    # 한글 수식 문법으로 쓴 옛 식

    def brace(i):                                   # s[i] == "{" → (안쪽, 닫는 괄호 다음 위치)
        depth = 0
        for j in range(i, len(s)):
            depth += (s[j] == "{") - (s[j] == "}")
            if depth == 0:
                return s[i + 1:j], j + 1
        return s[i + 1:], len(s)

    def arg(i):                                     # {…} 하나 또는 글자 하나
        while i < len(s) and s[i] == " ":
            i += 1
        if i < len(s) and s[i] == "{":
            return brace(i)
        return s[i:i + 1], i + 1

    out, i = [], 0
    while i < len(s):
        m = re.match(r"\\([A-Za-z]+|.)", s[i:])
        name = m.group(1) if m else ""
        if name in ("frac", "dfrac", "tfrac"):
            a, i = arg(i + len(name) + 1)
            b, i = arg(i)
            out.append(" {%s} over {%s} " % (latex_to_hwp(a), latex_to_hwp(b)))
        elif name == "sqrt":
            a, i = arg(i + 5)
            out.append(" sqrt {%s} " % latex_to_hwp(a))
        elif name in ("text", "mathrm"):
            a, i = arg(i + len(name) + 1)
            out.append(' "%s" ' % a)
        elif name in ("sum", "left", "right"):
            out.append(" %s " % name)
            i += len(name) + 1
        elif m:
            tok = m.group(0)
            out.append(_LATEX_SYM.get(tok, " %s " % name))
            i += len(tok)
        elif s[i] in "_^":
            op = s[i]
            a, i = arg(i + 1)
            out.append(" %s{%s} " % (op, latex_to_hwp(a)))
        else:
            out.append(s[i])
            i += 1
    return re.sub(r"\s+", " ", "".join(out)).strip()


def equation(script, size_hint=None):
    script = latex_to_hwp(script)
    n = size_hint or max(2, _eq_len(script))
    w = 520 * n
    h, base = _eq_size(script)
    return ('<hp:equation id="%s" zOrder="%s" numberingType="EQUATION" textWrap="TOP_AND_BOTTOM" textFlow="BOTH_SIDES" lock="0" dropcapstyle="None" version="Equation Version 60" baseLine="%d" textColor="#000000" baseUnit="1100" lineMode="CHAR" font="HYhwpEQ">'
            '<hp:sz width="%d" widthRelTo="ABSOLUTE" height="%d" heightRelTo="ABSOLUTE" protect="0"/>'
            '<hp:pos treatAsChar="1" affectLSpacing="0" flowWithText="1" allowOverlap="0" holdAnchorAndSO="0" vertRelTo="PARA" horzRelTo="PARA" vertAlign="TOP" horzAlign="LEFT" vertOffset="0" horzOffset="0"/>'
            '<hp:outMargin left="56" right="56" top="0" bottom="0"/><hp:shapeComment>수식입니다.</hp:shapeComment><hp:script>%s</hp:script></hp:equation>') % (nid(), nz(), base, w, h, esc(script))


def fraction(top, bottom, width=None):
    """보기/질문 안의 세로 분수(2×1 표)."""
    pp, st, cp = STYLE["frac"]
    width = width or max(3000, 1050 * max(len(top), len(bottom)) + 1100)
    cells = []
    for i, (txt, bf) in enumerate(((top, BF["frac_top"]), (bottom, BF["frac_bottom"]))):
        p = '<hp:p %s paraPrIDRef="%s" styleIDRef="%s" pageBreak="0" columnBreak="0" merged="0">%s</hp:p>' % (PID, pp, st, runs(txt, cp))
        cells.append(tc(p, 0, i, width, 1082, bf, (510, 510, 141, 141)))
    return tbl([[cells[0]], [cells[1]]], 2, 1, width, 2864, BF["table"], (0, 0, 141, 141), (0, 170, 0, 0), page_break="CELL")


def runs(text, charpr):
    """텍스트를 run XML로. $수식$, __밑줄__, {{frac|위|아래}} 지원."""
    out = []
    for part in _INLINE.split(text):
        if not part:
            continue
        if part.startswith("$"):
            out.append('<hp:run charPrIDRef="%s">%s</hp:run>' % (charpr, equation(part[1:-1].strip())))
        elif part.startswith("__"):
            out.append('<hp:run charPrIDRef="%s"><hp:t>%s</hp:t></hp:run>' % (STYLE["underline_char"], esc(part[2:-2])))
        elif part.startswith("{{frac|"):
            top, bottom = part[7:-2].split("|", 1)
            out.append('<hp:run charPrIDRef="%s">%s</hp:run>' % (charpr, fraction(top, bottom)))
        else:
            # <br> 은 문단 안 강제 줄바꿈
            t = "<hp:lineBreak/>".join(esc(x) for x in part.split("<br>"))
            out.append('<hp:run charPrIDRef="%s"><hp:t>%s</hp:t></hp:run>' % (charpr, t))
    return "".join(out)


# ---------------- 문단 ----------------
def para(body_xml, parapr, style, pb=0, cb=0):
    return '<hp:p %s paraPrIDRef="%s" styleIDRef="%s" pageBreak="%d" columnBreak="%d" merged="0">%s</hp:p>' % (PID, parapr, style, pb, cb, body_xml)


def text_para(text, parapr, style, charpr, pb=0, cb=0):
    return para(runs(text, charpr), parapr, style, pb, cb)


def q_head(n, text, pb=0, cb=0):
    pp, st, c_num, c_sp, c_txt = STYLE["q_head"]
    body = ('<hp:run charPrIDRef="%s"><hp:t>%d.</hp:t></hp:run><hp:run charPrIDRef="%s"><hp:t> </hp:t></hp:run>' % (c_num, n, c_sp)) + runs(text, c_txt)
    return para(body, pp, st, pb, cb)


def q_line(text):
    pp, st, c_sp, c_txt = STYLE["q_line"]
    return para('<hp:run charPrIDRef="%s"><hp:t>  </hp:t></hp:run>' % c_sp + runs(text, c_txt), pp, st)


def blank():
    pp, st, cp = STYLE["blank"]
    return '<hp:p %s paraPrIDRef="%s" styleIDRef="%s" pageBreak="0" columnBreak="0" merged="0"><hp:run charPrIDRef="%s"/></hp:p>' % (PID, pp, st, cp)


def _cp(i, cp, mark):
    """mark=(정답 위치, 색 글자 모양 ID)이면 정답 선택지만 그 글자 모양으로."""
    return mark[1] if mark and i == mark[0] else cp


def choice_lines(opts, mark=None):
    pp, st, cp = STYLE["choice_line"]
    marks = "①②③④⑤"
    return "".join(text_para("%s %s" % (marks[i], o), pp, st, _cp(i, cp, mark)) for i, o in enumerate(opts))


# ---------------- 표 ----------------
def tc(paras, col, row, w, h, bf, margin=(141, 141, 141, 141), colspan=1, rowspan=1, valign="CENTER", has_margin=0):
    return ('<hp:tc name="" header="0" hasMargin="%d" protect="0" editable="0" dirty="0" borderFillIDRef="%s">'
            '<hp:subList id="" textDirection="HORIZONTAL" lineWrap="BREAK" vertAlign="%s" linkListIDRef="0" linkListNextIDRef="0" textWidth="0" textHeight="0" hasTextRef="0" hasNumRef="0">%s</hp:subList>'
            '<hp:cellAddr colAddr="%d" rowAddr="%d"/><hp:cellSpan colSpan="%d" rowSpan="%d"/><hp:cellSz width="%d" height="%d"/>'
            '<hp:cellMargin left="%d" right="%d" top="%d" bottom="%d"/></hp:tc>') % (
        has_margin, bf, valign, paras, col, row, colspan, rowspan, w, h, *margin)


def tbl(rows, rowcnt, colcnt, width, height, bf, inmargin=(0, 0, 0, 0), outmargin=(0, 0, 0, 0), protect=0, page_break="NONE"):
    trs = "".join("<hp:tr>%s</hp:tr>" % "".join(r) for r in rows)
    return ('<hp:tbl id="%s" zOrder="%s" numberingType="TABLE" textWrap="TOP_AND_BOTTOM" textFlow="BOTH_SIDES" lock="0" dropcapstyle="None" pageBreak="%s" repeatHeader="1" rowCnt="%d" colCnt="%d" cellSpacing="0" borderFillIDRef="%s" noAdjust="0">'
            '<hp:sz width="%d" widthRelTo="ABSOLUTE" height="%d" heightRelTo="ABSOLUTE" protect="%d"/>'
            '<hp:pos treatAsChar="1" affectLSpacing="0" flowWithText="1" allowOverlap="0" holdAnchorAndSO="0" vertRelTo="PARA" horzRelTo="PARA" vertAlign="TOP" horzAlign="LEFT" vertOffset="0" horzOffset="0"/>'
            '<hp:outMargin left="%d" right="%d" top="%d" bottom="%d"/><hp:inMargin left="%d" right="%d" top="%d" bottom="%d"/>%s</hp:tbl>') % (
        nid(), nz(), page_break, rowcnt, colcnt, bf, width, height, protect, *outmargin, *inmargin, trs)


def tbl_para(tblxml, parapr, style, charpr, tail=""):
    return '<hp:p %s paraPrIDRef="%s" styleIDRef="%s" pageBreak="0" columnBreak="0" merged="0"><hp:run charPrIDRef="%s">%s<hp:t/></hp:run>%s</hp:p>' % (PID, parapr, style, charpr, tblxml, tail)


def _nlines(s, per=30):
    # 한글·전각은 1, 숫자·영문·기호·띄어쓰기는 약 0.55칸으로 센다(숫자가 많은 줄을 두 줄로 잘못 어림하지 않게)
    w = sum(1 if ord(ch) >= 0x2E80 else 0.55 for ch in s)
    return max(1, int(-(-w // per)))


def _box_lines(text, width):
    """자료 상자 한 항목이 차지할 줄 수: <br>로 나뉜 조각마다 따로 센다(한 줄 약 33칸, 실제 상자에서 잰 값)."""
    per = int(33 * (width - 1700) / (CELL_W - INDENT - 1700))   # 적게 어림해도 칸은 글에 맞춰 늘어난다
    plain = re.sub(r"\$[^$]*\$", "가가가", text)  # 수식은 대략 세 글자 폭
    return sum(_nlines(seg, per) for seg in plain.split("<br>"))


def databox(lines, width=COL_W):
    """자료 상자. 줄이 '['로 시작하면 소제목 서체, 그 외는 그대로."""
    width = min(width, CELL_W - INDENT)
    pp, st, cp = STYLE["box_para"]
    paras = []
    for ln in lines:
        if ln.startswith(("@center ", "@c ")):   # 가운데 정렬 줄: @center는 제목 서체(시 제목 등), @c는 본문 서체((중략) 등)
            cpp, cst, _ = STYLE["center"]
            head = ln.startswith("@center ")
            paras.append(text_para(ln.split(" ", 1)[1], cpp, cst, STYLE["box_heading_char"] if head else cp))
            continue
        if ln.startswith("@p "):                  # 내어쓰기 없는 줄글(소설 지문 등)
            paras.append(text_para(ln[3:], OVERLAY_PARA["justify"], "0", cp))
            continue
        c = STYLE["box_heading_char"] if ln.startswith("[") else cp
        paras.append(text_para(ln, pp, st, c))
    h = int(sum(_box_lines(l, width) for l in lines) * LINE_H * 0.85) + 700   # 칸은 글에 맞춰 늘어나므로 적게 어림
    cell = tc("".join(paras), 0, 0, width, h, BF["box_cell"], (850, 850, 600, 600), valign="TOP", has_margin=1)
    return tbl_para(tbl([[cell]], 1, 1, width, h, BF["box_tbl"]), "36", "3", "10")


def bogi(items):
    assert len(items) == 3, "보기는 ㄱ, ㄴ, ㄷ 세 개"
    pp, st, cp = STYLE["bogi_item"]
    labels = "ㄱㄴㄷ"
    ps = "".join(para('<hp:run charPrIDRef="%s"><hp:t>%s. </hp:t></hp:run>' % (cp, labels[i]) + runs(it, STYLE["bogi_text_char"]), pp, st) for i, it in enumerate(items))
    # 칸 높이는 최소값이라 넉넉히 잡으면 빈 줄이 생긴다. 수식은 몇 글자 폭으로 보고 줄 수를 적게 어림한다
    plain = [re.sub(r"\$[^$]*\$", "가가", it) for it in items]
    h3 = sum(_nlines(seg, 31) for it in plain for seg in it.split("<br>")) * LINE_H + 1300
    empty = lambda c: '<hp:p %s paraPrIDRef="23" styleIDRef="0" pageBreak="0" columnBreak="0" merged="0"><hp:run charPrIDRef="%s"/></hp:p>' % (PID, c)
    label = '<hp:p %s paraPrIDRef="94" styleIDRef="0" pageBreak="0" columnBreak="0" merged="0"><hp:run charPrIDRef="115"><hp:t>&lt;보 기&gt;</hp:t></hp:run></hp:p>' % PID
    total = CELL_W - INDENT - 282          # 들여쓴 문단 안에서 오른쪽이 잘리지 않는 폭
    wl = (total - 4463) // 2
    wr = total - 4463 - wl
    row0 = [tc(empty("114"), 0, 0, wl, 699, BF["bogi_top"]),
            tc(label, 1, 0, 4463, 1354, BF["bogi_label"], (0, 0, 0, 0), rowspan=2, has_margin=1),
            tc(empty("114"), 2, 0, wr, 699, BF["bogi_top"])]
    row1 = [tc(empty("116"), 0, 1, wl, 655, BF["bogi_l"]), tc(empty("114"), 2, 1, wr, 655, BF["bogi_r"])]
    row2 = [tc(ps, 0, 2, total, h3, BF["bogi_body"], (850, 850, 400, 600), colspan=3, has_margin=1)]
    t = tbl([row0, row1, row2], 3, 3, total, 699 + 655 + h3, BF["bogi_tbl"], (141, 141, 0, 0), (0, 0, 0, 566))
    return tbl_para(t, "92", "54", "112", '<hp:run charPrIDRef="38"><hp:t> </hp:t></hp:run>')


def choices10(opts, mark=None):
    """한 줄 선택지 표(① ㄱ ② ㄴ …). opts에 $수식$ 가능."""
    pp, st, cp = STYLE["choice_line"]
    marks = "①②③④⑤"
    h = 2600 if any(r"\frac" in o for o in opts) else 1431   # 분수는 두 층이라 칸을 높인다
    cells = []
    for i in range(5):
        c = _cp(i, cp, mark)
        cells.append(tc(text_para(marks[i], pp, st, c), 2 * i, 0, 1391, h, BF["choices"], (0, 0, 0, 0)))
        cells.append(tc(text_para(opts[i], pp, st, c), 2 * i + 1, 0, 4787, h, BF["choices"], (184, 0, 0, 0), has_margin=1))
    return tbl_para(tbl([cells], 1, 10, 30890, h, BF["box_tbl"], protect=1), "93", "69", "109")


def grid(headers, rows, width=COL_W, mark=None):
    """짝짓기 선택지 표: 머리행 (가)(나)(다), 행마다 ①~⑤."""
    pp, st, cp = STYLE["choice_line"]
    cpp, cst, ccp = STYLE["center"]
    marks = "①②③④⑤"
    n = len(headers)
    w0, m = 1549, (283, 283, 283, 283)
    wi = (width - w0) // n
    out = [[tc(text_para("", pp, st, cp), 0, 0, w0, 1716, BF["grid"], m)] +
           [tc(text_para(h, cpp, cst, ccp), j + 1, 0, wi, 1716, BF["grid"], m) for j, h in enumerate(headers)]]
    for i, r in enumerate(rows):
        out.append([tc(text_para(marks[i], pp, st, _cp(i, cp, mark)), 0, i + 1, w0, 1716, BF["grid"], m)] +
                   [tc(text_para(v, cpp, cst, _cp(i, ccp, mark)), j + 1, i + 1, wi, 1716, BF["grid"], m) for j, v in enumerate(r)])
    t = tbl(out, len(rows) + 1, n + 1, width, 1716 * (len(rows) + 1), BF["table"], (510, 510, 141, 141))
    return tbl_para(t, "93", "69", "109")


def datatable(headers, rows, widths=None, width=COL_W, hdr_h=1466, row_h=1600, charpr=None, margin=None,
              outmargin=(510, 510, 141, 141), para_style=("92", "54", "108")):
    """테두리 있는 자료 표. charpr·margin을 주면 그림 위에 얹는 작은 표처럼 글자·칸 여백을 줄인다.
    문항 안 표는 들여쓴 문단(92)에 들어가므로 단 끝을 넘지 않게 칸 너비를 비례로 줄인다."""
    hp, hs, hc = STYLE["table_head"]
    bp, bs, bc = STYLE["table_body"]
    if charpr:
        hp, hs, hc = bp, bs, charpr   # 작은 표는 머리 칸도 본문 문단 모양을 써야 짧은 머리말이 줄바꿈되지 않는다
        bc = charpr
    n = len(headers)
    widths = widths or [width // n] * n
    if para_style[0] == "92":
        room = CELL_W - INDENT - outmargin[0] - outmargin[1]
        if sum(widths) > room:
            widths = [w * room // sum(widths) for w in widths]
    m = margin or (283, 283, 283, 283)
    out = [[tc(text_para(h, hp, hs, hc), j, 0, widths[j], hdr_h, BF["table"], m) for j, h in enumerate(headers)]]
    # 칸에 '^'만 쓰면 바로 위 칸과 합친다(같은 날짜의 여러 행을 왼쪽 칸만 묶을 때)
    span = lambda i, j: 1 + next((k for k in range(i + 1, len(rows)) if rows[k][j].strip() != "^"), len(rows)) - (i + 1)
    for i, r in enumerate(rows):
        out.append([tc(text_para(v, bp, bs, bc), j, i + 1, widths[j], row_h * span(i, j), BF["table"], m, rowspan=span(i, j))
                    for j, v in enumerate(r) if v.strip() != "^"])
    t = tbl(out, len(rows) + 1, n, sum(widths), hdr_h + row_h * len(rows), BF["table"], outmargin)
    return tbl_para(t, *para_style)


# ---------------- 그림 ----------------
MM = 7200 / 25.4          # 1 mm = 283.46 HWPUNIT
_RENDER = ('<hp:renderingInfo><hc:transMatrix e1="1" e2="0" e3="0" e4="0" e5="1" e6="0"/>'
           '<hc:scaMatrix e1="1" e2="0" e3="0" e4="0" e5="1" e6="0"/><hc:rotMatrix e1="1" e2="0" e3="0" e4="0" e5="1" e6="0"/></hp:renderingInfo>')


def _line(width):
    return ('<hp:lineShape color="#000000" width="%d" style="%s" endCap="FLAT" headStyle="NORMAL" tailStyle="NORMAL" headfill="1" '
            'tailfill="1" headSz="MEDIUM_MEDIUM" tailSz="MEDIUM_MEDIUM" outlineStyle="NORMAL" alpha="0"/>') % (width, "SOLID" if width else "NONE")


_WHITE = '<hc:fillBrush><hc:winBrush faceColor="#FFFFFF" hatchColor="#000000" alpha="0"/></hc:fillBrush>'
_SHADOW = '<hp:shadow type="NONE" color="#B2B2B2" offsetX="0" offsetY="0" alpha="0"/>'


def _float_pos(x, y, w, h):
    """문단 기준 위치에 글 앞으로 띄운 개체의 크기·위치 XML."""
    return ('<hp:sz width="%d" widthRelTo="ABSOLUTE" height="%d" heightRelTo="ABSOLUTE" protect="0"/>'
            '<hp:pos treatAsChar="0" affectLSpacing="0" flowWithText="1" allowOverlap="1" holdAnchorAndSO="0" vertRelTo="PARA" '
            'horzRelTo="PARA" vertAlign="TOP" horzAlign="LEFT" vertOffset="%d" horzOffset="%d"/>'
            '<hp:outMargin left="0" right="0" top="0" bottom="0"/>') % (w, h, y, x)


# ---------------- 미리 줄바꿈 ----------------
# 글상자 안에서 한글이 글자 단위로 끊기지 않도록, 폭을 어림해 어절 사이에 <br>을 미리 넣는다.
# 한글 한 글자의 실제 폭(mm, 8절 실제 크기): 한글에서 직접 재서 맞춘 값. 나머지 글자는 한글 폭에 대한 비율로 어림한다.
HANGUL_MM = {"39": 3.19, "44": 3.03, "56": 2.86, "29": 3.03, "14": 3.66, "63": 3.36, "95": 3.84, "5": 3.47,
             "16": 3.19, "10": 3.66, "13": 3.35, "47": 2.86, "83": 3.19, "52": 3.66, "59": 3.66}
CHAR_PT = {"10": 11.5, "13": 10.5, "39": 10, "44": 9.5, "56": 9, "29": 9, "47": 9, "16": 10, "83": 10,
           "14": 11.5, "63": 10, "5": 10.7, "6": 10.7, "95": 11.5, "134": 16, "20": 14, "52": 11.5, "59": 11.5}


def _char_ratio(ch):
    o = ord(ch)
    if 0xAC00 <= o <= 0xD7A3 or 0x3130 <= o <= 0x318F or 0x3200 <= o <= 0x32FF or 0x4E00 <= o <= 0x9FFF:
        return 1.0
    if ch == " ":
        return 0.5
    if ch.isdigit():
        return 0.5
    if ch.isupper():
        return 0.62
    if ch.isalpha():
        return 0.47
    if ch in ".,:;'!|":
        return 0.3
    if ch in "()[]·":
        return 0.36
    return 0.7


def text_mm(text, font):
    han = HANGUL_MM.get(font, CHAR_PT.get(font, 10) * 0.3528 * 0.9)
    return sum(_char_ratio(c) for c in text) * han


def prewrap(text, width_mm, font, indent_mm=0.0):
    """어절 단위로 줄을 나눠 <br>로 잇는다. 줄 수는 최소로, 줄 길이는 고르게(마지막 줄에 한두 글자만 남지 않게)."""
    if "<br>" in text or "$" in text:
        return text
    words = text.split(" ")

    def lines_for(limit):
        out, cur = [], ""
        for w in words:
            cand = (cur + " " + w) if cur else w
            lim = limit - (indent_mm if out else 0)
            if cur and text_mm(cand, font) > lim:
                out.append(cur)
                cur = w
            else:
                cur = cand
        out.append(cur)
        return out

    full = width_mm * 0.97
    best = lines_for(full)
    n = len(best)
    if n > 1:
        lo = full * 0.72
        for k in range(28):                    # 같은 줄 수를 유지하는 가장 좁은 폭 = 고른 줄 길이
            mid = full - (full - lo) * (k + 1) / 28
            cand = lines_for(mid)
            if len(cand) == n:
                best = cand
            else:
                break
    return "<br>".join(best)


def float_rect(x, y, w, h, inner="", line=34, fill=True, ratio=0, margin=(283, 283, 170, 170), valign="CENTER"):
    """단 위에 떠 있는 사각형(글상자). x, y, w, h는 HWPUNIT, 문단 왼쪽 위 기준. ratio는 모서리 둥글기(%)."""
    x, y, w, h = (int(round(v)) for v in (x, y, w, h))
    text = ""
    if inner:
        text = ('<hp:drawText lastWidth="%d" name="" editable="0"><hp:subList id="" textDirection="HORIZONTAL" lineWrap="BREAK" '
                'vertAlign="%s" linkListIDRef="0" linkListNextIDRef="0" textWidth="0" textHeight="0" hasTextRef="0" hasNumRef="0">%s'
                '</hp:subList><hp:textMargin left="%d" right="%d" top="%d" bottom="%d"/></hp:drawText>') % (w, valign, inner, *margin)
    return ('<hp:rect id="%s" zOrder="%s" numberingType="PICTURE" textWrap="IN_FRONT_OF_TEXT" textFlow="BOTH_SIDES" lock="0" '
            'dropcapstyle="None" href="" groupLevel="0" instid="%s" ratio="%d"><hp:offset x="0" y="0"/>'
            '<hp:orgSz width="%d" height="%d"/><hp:curSz width="%d" height="%d"/><hp:flip horizontal="0" vertical="0"/>'
            '<hp:rotationInfo angle="0" centerX="%d" centerY="%d" rotateimage="1"/>%s%s%s%s%s'
            '<hc:pt0 x="0" y="0"/><hc:pt1 x="%d" y="0"/><hc:pt2 x="%d" y="%d"/><hc:pt3 x="0" y="%d"/>%s</hp:rect>') % (
        nid(), nz(), nid(), ratio, w, h, w, h, w // 2, h // 2, _RENDER, _line(line), _WHITE if fill else "", _SHADOW, text,
        w, w, h, h, _float_pos(x, y, w, h))


def float_polygon(points, line=34, fill=True):
    """단 위에 떠 있는 다각형. points는 문단 왼쪽 위 기준 HWPUNIT 좌표 목록."""
    xs, ys = [p[0] for p in points], [p[1] for p in points]
    x0, y0 = min(xs), min(ys)
    w, h = max(1, int(max(xs) - x0)), max(1, int(max(ys) - y0))
    pts = "".join('<hc:pt x="%d" y="%d"/>' % (px - x0, py - y0) for px, py in points)
    return ('<hp:polygon id="%s" zOrder="%s" numberingType="PICTURE" textWrap="IN_FRONT_OF_TEXT" textFlow="BOTH_SIDES" lock="0" '
            'dropcapstyle="None" href="" groupLevel="0" instid="%s"><hp:offset x="0" y="0"/>'
            '<hp:orgSz width="%d" height="%d"/><hp:curSz width="%d" height="%d"/><hp:flip horizontal="0" vertical="0"/>'
            '<hp:rotationInfo angle="0" centerX="%d" centerY="%d" rotateimage="1"/>%s%s%s%s%s%s</hp:polygon>') % (
        nid(), nz(), nid(), w, h, w, h, w // 2, h // 2, _RENDER, _line(line), _WHITE if fill else "", _SHADOW, pts,
        _float_pos(int(x0), int(y0), w, h))


def bubble(x, y, w, h, tip, text, charpr="39", line=34, align="left"):
    """말풍선: 둥근 사각형 + 꼬리. 모두 mm 단위(그림 왼쪽 위 기준이 아니라 이미 문단 기준으로 바꾼 값)이고 tip은 꼬리 끝."""
    tx, ty = tip
    hw = 1.3  # 꼬리 뿌리 반폭(mm)
    if ty > y + h or ty < y:                       # 아래·위로 나가는 꼬리
        rx = min(max(tx, x + w * 0.15), x + w * 0.85)
        ry, inside = (y + h, -0.8) if ty > y + h else (y, 0.8)
        base = [(rx - hw, ry + inside), (rx - hw, ry), (tx, ty), (rx + hw, ry), (rx + hw, ry + inside)]
        cover = (rx - hw + 0.15, ry - 0.3, 2 * hw - 0.3, 0.6)
    else:                                          # 옆으로 나가는 꼬리
        ry = min(max(ty, y + h * 0.25), y + h * 0.75)
        rx, inside = (x + w, -0.8) if tx > x + w else (x, 0.8)
        base = [(rx + inside, ry - hw), (rx, ry - hw), (tx, ty), (rx, ry + hw), (rx + inside, ry + hw)]
        cover = (rx - 0.3, ry - hw + 0.15, 0.6, 2 * hw - 0.3)
    text = prewrap(text, w - 2 * 450 / MM, charpr)
    paras = text_para(text, OVERLAY_PARA.get(align, "46"), "0", charpr)
    return (float_polygon([(px * MM, py * MM) for px, py in base], line=line)
            + float_rect(x * MM, y * MM, w * MM, h * MM, paras, line=line, ratio=20, margin=(450, 450, 300, 300))
            + float_rect(cover[0] * MM, cover[1] * MM, cover[2] * MM, cover[3] * MM, line=0))


def label(x, y, text, w=6, h=5, charpr="10"):
    """인물 옆 이름표(갑·을 등): 테두리 없는 글상자, mm 단위."""
    return float_rect(x * MM, y * MM, w * MM, h * MM, text_para(text, "64", "0", charpr), line=0, fill=False, margin=(0, 0, 0, 0))


def board(x, y, w, h, table_xml, line=60):
    """칠판·자료판: 테두리 있는 글상자 안에 표를 넣는다. mm 단위."""
    return float_rect(x * MM, y * MM, w * MM, h * MM, table_xml, line=line, margin=(425, 425, 340, 340))


def pic(image_id, px_w, px_h, width_hwp, caption=None, overlay=""):
    """BinData 이미지(image_id)를 단 안에 가운데 놓는 문단. 높이는 가로세로비로 계산.
    overlay는 같은 문단에 띄워 얹을 개체(말풍선·이름표 등) XML."""
    height_hwp = int(width_hwp * px_h / px_w)
    pp, st, cp = STYLE["pic_para"]
    x = ('<hp:pic id="%s" zOrder="%s" numberingType="PICTURE" textWrap="TOP_AND_BOTTOM" textFlow="BOTH_SIDES" lock="0" dropcapstyle="None" href="" groupLevel="0" instid="%s" reverse="0">'
         '<hp:offset x="0" y="0"/><hp:orgSz width="%d" height="%d"/><hp:curSz width="%d" height="%d"/><hp:flip horizontal="0" vertical="0"/>'
         '<hp:rotationInfo angle="0" centerX="%d" centerY="%d" rotateimage="1"/>'
         '<hp:renderingInfo><hc:transMatrix e1="1" e2="0" e3="0" e4="0" e5="1" e6="0"/><hc:scaMatrix e1="1" e2="0" e3="0" e4="0" e5="1" e6="0"/><hc:rotMatrix e1="1" e2="0" e3="0" e4="0" e5="1" e6="0"/></hp:renderingInfo>'
         '<hc:img binaryItemIDRef="%s" bright="0" contrast="0" effect="REAL_PIC" alpha="0"/>'
         '<hp:imgRect><hc:pt0 x="0" y="0"/><hc:pt1 x="%d" y="0"/><hc:pt2 x="%d" y="%d"/><hc:pt3 x="0" y="%d"/></hp:imgRect>'
         '<hp:imgClip left="0" right="%d" top="0" bottom="%d"/><hp:inMargin left="0" right="0" top="0" bottom="0"/><hp:imgDim dimwidth="%d" dimheight="%d"/><hp:effects/>'
         '<hp:sz width="%d" widthRelTo="ABSOLUTE" height="%d" heightRelTo="ABSOLUTE" protect="0"/>'
         '<hp:pos treatAsChar="1" affectLSpacing="0" flowWithText="1" allowOverlap="0" holdAnchorAndSO="0" vertRelTo="PARA" horzRelTo="PARA" vertAlign="TOP" horzAlign="LEFT" vertOffset="0" horzOffset="0"/>'
         '<hp:outMargin left="0" right="0" top="0" bottom="0"/><hp:shapeComment>그림입니다.</hp:shapeComment></hp:pic>') % (
        nid(), nz(), nid(), width_hwp, height_hwp, width_hwp, height_hwp, width_hwp // 2, height_hwp // 2,
        image_id, width_hwp, width_hwp, height_hwp, height_hwp, px_w, px_h, px_w, px_h, width_hwp, height_hwp)
    cpp, cst, ccp = STYLE["center"]
    out = para('<hp:run charPrIDRef="%s">%s%s<hp:t/></hp:run>' % (cp, x, overlay), cpp, cst)
    if caption:
        out += text_para(caption, cpp, cst, ccp)
    return out


def side_by_side(left_xml, right_xml, lw, rw):
    """테두리 없는 1×2 표: 왼쪽에 자료, 오른쪽에 삽화."""
    c1 = tc(left_xml, 0, 0, lw, 1000, "4", (0, 0, 0, 0), valign="CENTER", has_margin=1)
    c2 = tc(right_xml, 1, 0, rw, 1000, "4", (0, 0, 0, 0), valign="CENTER", has_margin=1)
    return tbl_para(tbl([[c1, c2]], 1, 2, lw + rw, 1000, "4"), "36", "3", "10")


def keep_together(inner_xml, pb=0, cb=0, width=31692):
    """문항 전체를 테두리 없는 1×1 표(쪽 나눔 불가)에 넣어 한 문항이 단을 넘어 쪼개지지 않게 한다."""
    cell = tc(inner_xml, 0, 0, width, 1000, "4", (0, 0, 0, 0), valign="TOP", has_margin=1)
    t = tbl([[cell]], 1, 1, width, 1000, "4")
    return '<hp:p %s paraPrIDRef="23" styleIDRef="0" pageBreak="%d" columnBreak="%d" merged="0"><hp:run charPrIDRef="32">%s<hp:t/></hp:run></hp:p>' % (PID, pb, cb, t)


def dialog(speakers_lines, width=COL_W):
    """사탐형 대화 자료: [(화자, 발언), ...] → 2열 표(테두리 없음) 안에 넣은 자료 상자."""
    pp, st, cp = STYLE["box_para"]
    lines = ["%s: %s" % (s, t) if s else "@c " + t for s, t in speakers_lines]
    return databox(lines, width)
