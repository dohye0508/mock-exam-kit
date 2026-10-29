# -*- coding: utf-8 -*-
"""문항 dict → HWPX 패키지.

양식 폴더(templates/<name>/)는 원본 HWP를 HWPX로 풀어 둔 것이며,
  Contents/section0.xml 의 첫 문단(p0: 구역 설정 + 머리글 + 제목 표)을 그대로 쓰고 뒤에 문항 본문을 붙인다.
  frags/p0.xml 은 그 첫 문단만 따로 저장한 것. 제목 글자는 HEADER_RULES 로 치환한다.
"""
import os, re, shutil, zipfile
from . import hwpx
from .figures import render

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATES = os.path.join(ROOT, "templates")


def _header_rules(meta):
    """kice-sci 양식의 제목 글자 치환 규칙. (원본 → 새 글자)"""
    subj = meta.get("subject", "")
    return [
        ("2025학년도 대학수학능력시험 문제지", "%s %s 문제지" % (meta.get("year", "2025학년도"), meta.get("exam", "대학수학능력시험"))),
        ("과학탐구", meta.get("area", "과학탐구")),
        # 둥근 상자의 "제 4 교시"는 전각 공백(fwSpace)으로 띄워져 있다
        ("<hp:t>제<hp:fwSpace/>4<hp:fwSpace/>교시</hp:t>",
         "<hp:t>제<hp:fwSpace/>%s<hp:fwSpace/>교시</hp:t>" % (re.sub(r"\D", "", meta.get("period", "")) or "4")),
        # 과목명 "(화학Ⅰ)" 은 '(화' '학' 'Ⅰ' ')' 네 run 으로 쪼개져 있음
        (re.compile(r'(<hp:run charPrIDRef="(?:30|31)"><hp:t>)\(화(</hp:t>)'), r"\1(" + subj[:1] + r"\2"),
        (re.compile(r'(<hp:run charPrIDRef="(?:30|49)"><hp:t>)학(</hp:t>)'), r"\1" + subj[1:] + r"\2"),
        ('<hp:t charStyleIDRef="20">학<hp:fwSpace/></hp:t>', '<hp:t charStyleIDRef="20">%s</hp:t>' % subj[1:]),
        (re.compile(r'(<hp:run charPrIDRef="(?:82|81)"><hp:t>)[IⅠ](</hp:t>)'), r"\1\2"),
    ]


def build_question(q, img_sink):
    parts = [hwpx.q_head(q["n"], q["head"])]
    for kind, payload in q["blocks"]:
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
        parts.append(hwpx.choices10(q["set"]))
    elif "grid" in q:
        parts.append(hwpx.grid(*q["grid"]))
    elif "opts" in q:
        if q.get("inline_opts") or all(len(o) <= 6 for o in q["opts"]):
            parts.append(hwpx.choices10(q["opts"]))
        else:
            parts.append(hwpx.choice_lines(q["opts"]))
    body = hwpx.keep_together("".join(parts), pb=q["pb"], cb=q["cb"])
    return body + "".join(hwpx.blank() for _ in range(q["gap"]))


def _figure(q, payload, img_sink):
    kv, params = payload["kv"], payload["params"]
    width = int(kv.get("w", 19000))
    if "file" in kv:
        png = kv["file"]
        from PIL import Image
        with Image.open(png) as im:
            pw, ph = im.size
    else:
        png, pw, ph = render(payload["kind"], params, os.path.join(img_sink.workdir, "fig_q%02d.png" % q["n"]))
    image_id = img_sink.add(png)
    return hwpx.pic(image_id, pw, ph, width, caption=kv.get("caption"))


class ImageSink:
    def __init__(self, workdir):
        self.workdir = workdir
        self.items = []  # (id, src_path)

    def add(self, path):
        iid = "fig%d" % (len(self.items) + 1)
        self.items.append((iid, path))
        return iid


def build(meta, questions, out_hwpx, template="kice-sci", workdir=None):
    tpl = os.path.join(TEMPLATES, template)
    workdir = workdir or (os.path.splitext(out_hwpx)[0] + "_build")
    if os.path.exists(workdir):
        shutil.rmtree(workdir)
    shutil.copytree(tpl, workdir, ignore=shutil.ignore_patterns("frags", "Preview"))
    sink = ImageSink(workdir)

    src_sec = open(os.path.join(tpl, "Contents", "section0.xml"), encoding="utf-8").read()
    prefix = src_sec[:src_sec.index("<hp:p ")]
    p0 = open(os.path.join(tpl, "frags", "p0.xml"), encoding="utf-8").read()
    for old, new in _header_rules(meta):
        p0 = old.sub(new, p0) if hasattr(old, "sub") else p0.replace(old, new)

    body = "".join(build_question(q, sink) for q in questions)
    open(os.path.join(workdir, "Contents", "section0.xml"), "w", encoding="utf-8").write(prefix + p0 + body + "</hs:sec>")

    pages = meta.get("pages", "4")
    for i in range(1, 9):
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
