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


def equation(script, size_hint=None):
    n = size_hint or max(2, len(re.sub(r"[{}_^ ]", "", script)))
    w = 520 * n
    return ('<hp:equation id="%s" zOrder="%s" numberingType="EQUATION" textWrap="TOP_AND_BOTTOM" textFlow="BOTH_SIDES" lock="0" dropcapstyle="None" version="Equation Version 60" baseLine="85" textColor="#000000" baseUnit="1100" lineMode="CHAR" font="HYhwpEQ">'
            '<hp:sz width="%d" widthRelTo="ABSOLUTE" height="1125" heightRelTo="ABSOLUTE" protect="0"/>'
            '<hp:pos treatAsChar="1" affectLSpacing="0" flowWithText="1" allowOverlap="0" holdAnchorAndSO="0" vertRelTo="PARA" horzRelTo="PARA" vertAlign="TOP" horzAlign="LEFT" vertOffset="0" horzOffset="0"/>'
            '<hp:outMargin left="56" right="56" top="0" bottom="0"/><hp:shapeComment>수식입니다.</hp:shapeComment><hp:script>%s</hp:script></hp:equation>') % (nid(), nz(), w, esc(script))


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
            out.append('<hp:run charPrIDRef="%s"><hp:t>%s</hp:t></hp:run>' % (charpr, esc(part)))
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


def choice_lines(opts):
    pp, st, cp = STYLE["choice_line"]
    marks = "①②③④⑤"
    return "".join(text_para("%s %s" % (marks[i], o), pp, st, cp) for i, o in enumerate(opts))


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
    return max(1, -(-len(s) // per))


def databox(lines, width=COL_W):
    """자료 상자. 줄이 '['로 시작하면 소제목 서체, 그 외는 그대로."""
    pp, st, cp = STYLE["box_para"]
    paras = []
    for ln in lines:
        c = STYLE["box_heading_char"] if ln.startswith("[") else cp
        paras.append(text_para(ln, pp, st, c))
    h = sum(_nlines(l, 33) for l in lines) * LINE_H + 1200
    cell = tc("".join(paras), 0, 0, width, h, BF["box_cell"], (850, 850, 850, 850), valign="TOP", has_margin=1)
    return tbl_para(tbl([[cell]], 1, 1, width, h, BF["box_tbl"]), "36", "3", "10")


def bogi(items):
    assert len(items) == 3, "보기는 ㄱ, ㄴ, ㄷ 세 개"
    pp, st, cp = STYLE["bogi_item"]
    labels = "ㄱㄴㄷ"
    ps = "".join(para('<hp:run charPrIDRef="%s"><hp:t>%s. </hp:t></hp:run>' % (cp, labels[i]) + runs(it, STYLE["bogi_text_char"]), pp, st) for i, it in enumerate(items))
    h3 = sum(_nlines(it, 30) for it in items) * LINE_H + 1300
    empty = lambda c: '<hp:p %s paraPrIDRef="23" styleIDRef="0" pageBreak="0" columnBreak="0" merged="0"><hp:run charPrIDRef="%s"/></hp:p>' % (PID, c)
    label = '<hp:p %s paraPrIDRef="94" styleIDRef="0" pageBreak="0" columnBreak="0" merged="0"><hp:run charPrIDRef="115"><hp:t>&lt;보 기&gt;</hp:t></hp:run></hp:p>' % PID
    row0 = [tc(empty("114"), 0, 0, 13575, 699, BF["bogi_top"]),
            tc(label, 1, 0, 4463, 1354, BF["bogi_label"], (0, 0, 0, 0), rowspan=2, has_margin=1),
            tc(empty("114"), 2, 0, 13140, 699, BF["bogi_top"])]
    row1 = [tc(empty("116"), 0, 1, 13575, 655, BF["bogi_l"]), tc(empty("114"), 2, 1, 13140, 655, BF["bogi_r"])]
    row2 = [tc(ps, 0, 2, 31178, h3, BF["bogi_body"], (850, 850, 566, 850), colspan=3, has_margin=1)]
    t = tbl([row0, row1, row2], 3, 3, 31178, 699 + 655 + h3, BF["bogi_tbl"], (141, 141, 0, 0), (0, 0, 0, 566))
    return tbl_para(t, "92", "54", "112", '<hp:run charPrIDRef="38"><hp:t> </hp:t></hp:run>')


def choices10(opts):
    """한 줄 선택지 표(① ㄱ ② ㄴ …). opts에 $수식$ 가능."""
    pp, st, cp = STYLE["choice_line"]
    marks = "①②③④⑤"
    cells = []
    for i in range(5):
        cells.append(tc(text_para(marks[i], pp, st, cp), 2 * i, 0, 1391, 1431, BF["choices"], (0, 0, 0, 0)))
        cells.append(tc(text_para(opts[i], pp, st, cp), 2 * i + 1, 0, 4787, 1431, BF["choices"], (184, 0, 0, 0), has_margin=1))
    return tbl_para(tbl([cells], 1, 10, 30890, 1431, BF["box_tbl"], protect=1), "93", "69", "109")


def grid(headers, rows, width=COL_W):
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
        out.append([tc(text_para(marks[i], pp, st, cp), 0, i + 1, w0, 1716, BF["grid"], m)] +
                   [tc(text_para(v, cpp, cst, ccp), j + 1, i + 1, wi, 1716, BF["grid"], m) for j, v in enumerate(r)])
    t = tbl(out, len(rows) + 1, n + 1, width, 1716 * (len(rows) + 1), BF["table"], (510, 510, 141, 141))
    return tbl_para(t, "93", "69", "109")


def datatable(headers, rows, widths=None, width=COL_W, hdr_h=1466, row_h=1600):
    """테두리 있는 자료 표."""
    hp, hs, hc = STYLE["table_head"]
    bp, bs, bc = STYLE["table_body"]
    n = len(headers)
    widths = widths or [width // n] * n
    m = (283, 283, 283, 283)
    out = [[tc(text_para(h, hp, hs, hc), j, 0, widths[j], hdr_h, BF["table"], m) for j, h in enumerate(headers)]]
    for i, r in enumerate(rows):
        out.append([tc(text_para(v, bp, bs, bc), j, i + 1, widths[j], row_h, BF["table"], m) for j, v in enumerate(r)])
    t = tbl(out, len(rows) + 1, n, sum(widths), hdr_h + row_h * len(rows), BF["table"], (510, 510, 141, 141))
    return tbl_para(t, "92", "54", "108")


# ---------------- 그림 ----------------
def pic(image_id, px_w, px_h, width_hwp, caption=None):
    """BinData 이미지(image_id)를 단 안에 가운데 놓는 문단. 높이는 가로세로비로 계산."""
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
    out = para('<hp:run charPrIDRef="%s">%s<hp:t/></hp:run>' % (cp, x), cpp, cst)
    if caption:
        out += text_para(caption, cpp, cst, ccp)
    return out


def keep_together(inner_xml, pb=0, cb=0, width=31692):
    """문항 전체를 테두리 없는 1×1 표(쪽 나눔 불가)에 넣어 한 문항이 단을 넘어 쪼개지지 않게 한다."""
    cell = tc(inner_xml, 0, 0, width, 1000, "4", (0, 0, 0, 0), valign="TOP", has_margin=1)
    t = tbl([[cell]], 1, 1, width, 1000, "4")
    return '<hp:p %s paraPrIDRef="23" styleIDRef="0" pageBreak="%d" columnBreak="%d" merged="0"><hp:run charPrIDRef="32">%s<hp:t/></hp:run></hp:p>' % (PID, pb, cb, t)


def dialog(speakers_lines, width=COL_W):
    """사탐형 대화 자료: [(화자, 발언), ...] → 2열 표(테두리 없음) 안에 넣은 자료 상자."""
    pp, st, cp = STYLE["box_para"]
    lines = ["%s: %s" % (s, t) for s, t in speakers_lines]
    return databox(lines, width)
