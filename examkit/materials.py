# -*- coding: utf-8 -*-
"""글자·수치가 들어가는 자료(안내문·메신저·게시물·기사·전광판·재생 목록·기록표·안내판)를
HTML로 짜서 headless Chrome으로 PNG를 만든다. 지면 폭(HWPUNIT)에 맞춘 CSS 폭으로 그리고 4배 해상도로 찍는다.

    ::: figure notice w=30557
    title: 체력단련실 이용 안내
    item1: …
    :::
"""
import html, os, shutil, subprocess, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHROME_CANDIDATES = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
]
SCALE = 4          # 4배로 찍으면 실제 크기에서 약 384dpi
MAX_H = 2400       # 캡처할 CSS 높이(넉넉히 찍고 여백을 잘라 낸다)

# 한컴 글꼴은 영문 이름으로 잡아야 Chrome이 확실히 찾는다(HY신명조 = HYSinMyeongJo-Medium 등)
SERIF = '"HYSinMyeongJo-Medium","HY신명조","HCR Batang","Batang","바탕",serif'
HEAD = '"HYGothic-Extra","HY견고딕","HYGothic-Medium","Malgun Gothic","맑은 고딕",sans-serif'
GOTHIC = '"Malgun Gothic","맑은 고딕",sans-serif'

BASE_CSS = """
*{box-sizing:border-box}
html{filter:grayscale(1)}
html,body{margin:0;padding:0;background:#fff;color:#111}
body{padding:3px;font-size:13.5px;line-height:1.5;-webkit-font-smoothing:antialiased}
.gothic{word-break:keep-all}
img{display:block;max-width:100%%}
.serif{font-family:%s}.head{font-family:%s}.gothic{font-family:%s}
table{border-collapse:collapse}
""" % (SERIF, HEAD, GOTHIC)


def _e(s):
    """HTML 이스케이프. 값 안의 \\n 은 줄바꿈."""
    return html.escape(str(s)).replace("\\n", "<br>")


def _items(params, prefix):
    keys = sorted((k for k in params if k.startswith(prefix) and k[len(prefix):].isdigit()), key=lambda k: int(k[len(prefix):]))
    return [params[k] for k in keys]


_WORK = [tempfile.gettempdir()]   # render() 가 지금 만드는 PNG의 폴더로 바꿔 둔다


def _img_url(path):
    """자료 안에 넣는 삽화: 둘레의 흰 여백을 잘라 낸 사본을 쓴다(삽화 원본은 말풍선 자리 때문에 여백이 넓다)."""
    from PIL import Image
    p = path if os.path.isabs(path) else os.path.join(ROOT, path)
    if not os.path.exists(p):
        raise FileNotFoundError("자료 그림을 찾을 수 없음: %s" % path)
    with Image.open(p) as src:
        im = src.convert("RGB")
    box = im.convert("L").point(lambda v: 255 if v < 238 else 0).getbbox()
    if box:
        pad = int(max(im.size) * 0.015)
        im = im.crop((max(0, box[0] - pad), max(0, box[1] - pad), min(im.width, box[2] + pad), min(im.height, box[3] + pad)))
    out = os.path.join(_WORK[0], "trim_" + os.path.splitext(os.path.basename(p))[0] + ".png")
    im.save(out)
    return "file:///" + os.path.abspath(out).replace("\\", "/")


def _rows(spec):
    return [[c.strip() for c in r.split("|")] for r in spec.split(";") if r.strip()]


def _table(rows, cls):
    if not rows:
        return ""
    head = "".join("<th>%s</th>" % _e(c) for c in rows[0])
    body = "".join("<tr>%s</tr>" % "".join("<td>%s</td>" % _e(c) for c in r) for r in rows[1:])
    return '<table class="%s"><thead><tr>%s</tr></thead><tbody>%s</tbody></table>' % (cls, head, body)


# ---------------- 안내문 ----------------
def notice(p):
    items = _items(p, "item")
    lis = "".join("<li>%s</li>" % _e(t) for t in items)
    meta = " · ".join(_e(p[k]) for k in ("from", "date") if p.get(k))
    # image_w: 그림이 차지하는 너비(%%), 기본 36
    img = ('<div class="nimg" style="flex:0 0 %s%%%%"><img src="%s"></div>' % (p.get("image_w", "36"), _img_url(p["image"]))) if p.get("image") else ""
    table = _table(_rows(p["table"]), "nt") if p.get("table") else ""
    note = '<div class="nnote">※ %s</div>' % _e(p["note"].lstrip("※ ").strip()) if p.get("note") else ""
    css = """
.notice{border:1.6px solid #222;padding:9px 12px 10px}
.ntitle{font-size:16.5px;font-weight:700;text-align:center;letter-spacing:.5px;padding:1px 0 5px;border-bottom:3.5px double #222}
.nmeta{font-size:11.5px;text-align:right;color:#333;margin-top:4px}
.nbody{display:flex;gap:10px;align-items:center;margin-top:6px}
.nbody ul{flex:1;margin:0;padding:0;list-style:none}
.nbody li{position:relative;padding-left:13px;margin:2px 0}
.nbody li:before{content:"◦";position:absolute;left:0;top:0}
.nimg{flex:0 0 36%%}
.nimg img{width:100%%}
.nt{width:100%%;margin-top:7px;font-size:12.5px}
.nt th,.nt td{border:1px solid #444;padding:2px 5px;text-align:center}
.nt th{background:#e2e2e2;font-family:%s;font-weight:700;white-space:nowrap}
.nnote{font-size:12px;margin-top:6px}
""" % HEAD
    body = ('<div class="notice serif"><div class="ntitle head">%s</div>%s<div class="nbody"><ul>%s</ul>%s</div>%s%s</div>'
            % (_e(p.get("title", "")), '<div class="nmeta">%s</div>' % meta if meta else "", lis, img, table, note))
    return css, body


# ---------------- 메신저 ----------------
def chat(p):
    me = p.get("me", "")
    rows = []
    prev = None
    for m in _items(p, "msg"):
        parts = [x.strip() for x in m.split("|")]
        name, text = parts[0], parts[1] if len(parts) > 1 else ""
        t = parts[2] if len(parts) > 2 else ""
        if text.startswith("[사진]"):
            content = '<div class="bub photo"><img src="%s"></div>' % _img_url(text[len("[사진]"):].strip())
        else:
            content = '<div class="bub%s">%s</div>' % (" mine" if name == me else "", _e(text))
        tm = '<span class="tm">%s</span>' % _e(t) if t else ""
        if name == me:
            rows.append('<div class="row me">%s%s</div>' % (tm, content))
        elif name == prev:
            # 같은 사람이 이어서 보낸 말은 프로필·이름 없이 말풍선만
            rows.append('<div class="row cont"><div class="av blank"></div><div class="col"><div class="line">%s%s</div></div></div>'
                        % (content, tm))
        else:
            rows.append('<div class="row"><div class="av">%s</div><div class="col"><div class="nm">%s</div>'
                        '<div class="line">%s%s</div></div></div>' % (_e(name[:1]), _e(name), content, tm))
        prev = name
    css = """
.phone{border:1.6px solid #333;border-radius:14px;overflow:hidden}
.bar{background:#d9d9d9;padding:6px 12px;font-weight:700;font-size:13.5px;display:flex;align-items:center;gap:8px;border-bottom:1px solid #aaa}
.bar .back{font-size:18px;line-height:1;font-weight:400}
.bar .menu{margin-left:auto;font-weight:400;letter-spacing:1px}
.msgs{background:#f3f3f3;padding:8px 10px 10px}
.row{display:flex;gap:7px;margin:6px 0;align-items:flex-start}
.row.me{justify-content:flex-end;align-items:flex-end}
.row.cont{margin-top:-2px}
.av.blank{background:none}
.av{flex:0 0 26px;height:26px;border-radius:50%;background:#9a9a9a;color:#fff;font-size:12px;font-weight:700;display:flex;align-items:center;justify-content:center}
.col{max-width:78%}
.nm{font-size:11.5px;color:#333;margin:0 0 2px 2px}
.line{display:flex;align-items:flex-end;gap:5px}
.bub{background:#dcdcdc;border-radius:11px;padding:5px 10px;font-size:13px;line-height:1.45}
.bub.mine{background:#fff;border:1.2px solid #666;max-width:72%}
.bub.photo{padding:3px;background:#fff;border:1.2px solid #888;width:58%;flex:0 0 58%}
.bub.photo img{border-radius:8px;width:100%}
.line .bub.photo{width:auto;flex:0 0 72%}
.tm{font-size:10.5px;color:#555;white-space:nowrap}
"""
    body = ('<div class="phone gothic"><div class="bar"><span class="back">‹</span><span>%s</span><span class="menu">≡</span></div>'
            '<div class="msgs">%s</div></div>' % (_e(p.get("title", "")), "".join(rows)))
    return css, body


# ---------------- 게시물 ----------------
_HEART = ('<svg width="17" height="17" viewBox="0 0 24 24"><path d="M12 20.5s-7.5-4.6-9.3-9.2C1.4 7.9 3.6 4.5 7 4.5c2.1 0 3.6 1.2 5 3 '
          '1.4-1.8 2.9-3 5-3 3.4 0 5.6 3.4 4.3 6.8-1.8 4.6-9.3 9.2-9.3 9.2z" fill="none" stroke="#222" stroke-width="1.8"/></svg>')
_TALK = ('<svg width="17" height="17" viewBox="0 0 24 24"><path d="M4 5h16v11H9l-4 3.5V16H4z" fill="none" stroke="#222" '
         'stroke-width="1.8" stroke-linejoin="round"/></svg>')
_SHARE = ('<svg width="17" height="17" viewBox="0 0 24 24"><path d="M3 11l18-7-7 18-2.5-7.5z" fill="none" stroke="#222" '
          'stroke-width="1.8" stroke-linejoin="round"/></svg>')


def post(p):
    acc = p.get("account", "")
    initial = acc.lstrip("@")[:1] or "·"
    lines = "".join("<div>%s</div>" % _e(t) for t in _items(p, "line"))
    title = '<div class="ptitle">%s</div>' % _e(p["title"]) if p.get("title") else ""
    img = '<img class="pimg" src="%s">' % _img_url(p["image"]) if p.get("image") else ""
    css = """
.post{border:1.4px solid #444;border-radius:10px;overflow:hidden}
.ph{display:flex;align-items:center;gap:8px;padding:7px 10px}
.pav{width:28px;height:28px;border-radius:50%;border:1.5px solid #222;display:flex;align-items:center;justify-content:center;font-weight:700;font-size:13px}
.pacc{font-weight:700;font-size:13px;line-height:1.2}
.ptime{font-size:11px;color:#555;line-height:1.2}
.pmore{margin-left:auto;letter-spacing:1px;font-weight:700}
.pimg{width:100%;max-height:60vw;object-fit:contain;background:#fff;border-top:1px solid #ccc;border-bottom:1px solid #ccc}
.ptext{padding:7px 11px 3px;font-size:13px;line-height:1.55}
.ptitle{font-weight:700;margin-bottom:2px}
.picons{display:flex;gap:12px;padding:4px 11px 8px}
"""
    body = ('<div class="post gothic"><div class="ph"><div class="pav">%s</div><div><div class="pacc">%s</div><div class="ptime">%s</div></div>'
            '<span class="pmore">···</span></div>%s<div class="ptext">%s%s</div><div class="picons">%s%s%s</div></div>'
            % (_e(initial), _e(acc), _e(p.get("time", "")), img, title, lines, _HEART, _TALK, _SHARE))
    return css, body


# ---------------- 신문 기사 ----------------
def news(p, css_w):
    paras = "".join("<p>%s</p>" % _e(t) for t in _items(p, "body"))
    fig = ""
    if p.get("image"):
        cap = '<figcaption>%s</figcaption>' % _e(p["caption"]) if p.get("caption") else ""
        fig = '<figure><img src="%s">%s</figure>' % (_img_url(p["image"]), cap)
    cols = 2 if css_w >= 300 else 1
    css = """
.news{border:1px solid #666;padding:8px 11px 9px}
.mast{display:flex;justify-content:space-between;align-items:baseline;border-top:3px solid #111;border-bottom:1px solid #111;padding:3px 0 2px}
.pname{font-size:15.5px;font-weight:700;letter-spacing:1px}
.issue{font-size:11px;color:#333}
.hl{font-size:16.5px;font-weight:700;line-height:1.35;margin:7px 0 2px}
.sub{font-size:12.5px;color:#333;margin-bottom:5px;padding-left:7px;border-left:3px solid #777}
.cols{column-count:%d;column-gap:14px;column-rule:1px solid #bbb;font-size:12.8px;line-height:1.55;text-align:justify}
.cols p{margin:0 0 3px;text-indent:.8em}
figure{margin:0 0 5px;break-inside:avoid}
figcaption{font-size:11px;color:#333;margin-top:2px;font-family:%s}
""" % (cols, GOTHIC)
    body = ('<div class="news serif"><div class="mast"><span class="pname head">%s</span><span class="issue">%s</span></div>'
            '<div class="hl head">%s</div>%s<div class="cols">%s%s</div></div>'
            % (_e(p.get("paper", "")), _e(p.get("issue", "")), _e(p.get("headline", "")),
               '<div class="sub">%s</div>' % _e(p["sub"]) if p.get("sub") else "", fig, paras))
    return css, body


# ---------------- 전광판 ----------------
_PLANE = ('<svg width="16" height="16" viewBox="0 0 24 24"><path d="M21 15.5v-2l-8-5V3.5a1.5 1.5 0 0 0-3 0V8.5l-8 5v2l8-2.5V18l-2 1.5V21'
          'l3.5-1 3.5 1v-1.5L13 18v-5z" fill="#fff"/></svg>')


def board(p):
    header = [c.strip() for c in p.get("header", "").split("|")] if p.get("header") else []
    rows = [[c.strip() for c in r.split("|")] for r in _items(p, "row")]
    th = "".join("<th>%s</th>" % _e(c) for c in header)
    trs = "".join("<tr>%s</tr>" % "".join("<td>%s</td>" % _e(c) for c in r) for r in rows)
    css = """
.board{border:2px solid #222;border-radius:6px;overflow:hidden}
.btitle{background:#222;color:#fff;font-weight:700;font-size:14px;padding:5px 10px;display:flex;align-items:center;gap:7px;letter-spacing:.5px}
.bt{width:100%;font-size:13px}
.bt th{background:#555;color:#fff;font-weight:700;padding:3px 6px;font-size:12px}
.bt td{padding:3px 6px;text-align:center;border-top:1px solid #bbb;font-variant-numeric:tabular-nums}
.bt tr:nth-child(even) td{background:#ececec}
"""
    body = ('<div class="board gothic"><div class="btitle">%s<span>%s</span></div><table class="bt"><thead><tr>%s</tr></thead>'
            '<tbody>%s</tbody></table></div>' % (_PLANE, _e(p.get("title", "")), th, trs))
    return css, body


# ---------------- 재생 목록 ----------------
def playlist(p):
    now = int(p["now"]) if str(p.get("now", "")).strip().isdigit() else None
    rows = []
    for i, r in enumerate(_items(p, "row"), 1):
        c = [x.strip() for x in r.split("|")] + ["", "", ""]
        playing = (i == now)
        mark = "▶" if playing else _e(c[0])
        bar = '<div class="prog"><div></div></div>' if playing else ""
        rows.append('<div class="pr%s"><span class="no">%s</span><span class="nmc"><span>%s</span>%s</span><span class="len">%s</span></div>'
                    % (" now" if playing else "", mark, _e(c[1]), bar, _e(c[2])))
    css = """
.pl{border:1.5px solid #333;border-radius:10px;overflow:hidden}
.pltitle{background:#e0e0e0;font-weight:700;font-size:13.5px;padding:6px 11px;border-bottom:1px solid #999}
.pr{display:flex;align-items:center;gap:9px;padding:4px 11px;border-bottom:1px solid #ddd;font-size:13px}
.pr:last-child{border-bottom:none}
.no{flex:0 0 18px;text-align:center;color:#444}
.nmc{flex:1}
.len{font-variant-numeric:tabular-nums;color:#333}
.pr.now{font-weight:700;background:#f0f0f0}
.pr.now .no{color:#111}
.prog{height:3px;background:#ccc;border-radius:2px;margin-top:3px}
.prog div{width:40%;height:3px;background:#222;border-radius:2px}
"""
    body = '<div class="pl gothic"><div class="pltitle">%s</div>%s</div>' % (_e(p.get("title", "")), "".join(rows))
    return css, body


# ---------------- 기록표 ----------------
def form(p):
    header = [c.strip() for c in p.get("header", "").split("|")] if p.get("header") else []
    rows = [[c.strip() for c in r.split("|")] for r in _items(p, "row")]
    table = _table([header] + rows if header else rows, "ft")
    note = '<div class="fnote">%s</div>' % _e(p["note"]) if p.get("note") else ""
    css = """
.form{padding:2px}
.ftitle{font-size:15px;font-weight:700;text-align:center;margin-bottom:5px;letter-spacing:1px}
.ft{width:100%%;border:2px solid #222;font-size:13px}
.ft th,.ft td{border:1px solid #555;padding:3px 6px;text-align:center}
.ft th{background:#dcdcdc;font-family:%s;font-weight:700;font-size:12.5px;white-space:nowrap}
.fnote{font-size:11.5px;text-align:right;margin-top:3px;color:#333}
""" % HEAD
    body = '<div class="form serif"><div class="ftitle head">%s</div>%s%s</div>' % (_e(p.get("title", "")), table, note)
    return css, body


# ---------------- 층별 안내판 ----------------
def sign(p):
    rows = []
    for r in _items(p, "floor"):
        c = [x.strip() for x in r.split("|")] + [""]
        rows.append('<div class="sr"><span class="chip">%s</span><span class="sv">%s</span></div>' % (_e(c[0]), _e(c[1])))
    css = """
.sign{border:2.2px solid #222;border-radius:9px;overflow:hidden;background:#fafafa}
.stitle{background:#2a2a2a;color:#fff;font-weight:700;text-align:center;font-size:14px;padding:5px 0;letter-spacing:2px}
.sr{display:flex;align-items:center;gap:10px;padding:5px 10px;border-top:1px solid #bbb;font-size:13.5px}
.sr:first-of-type{border-top:none}
.chip{flex:0 0 34px;text-align:center;background:#3a3a3a;color:#fff;font-weight:700;border-radius:4px;padding:1px 0;font-size:13px}
.sv{flex:1}
"""
    body = '<div class="sign gothic"><div class="stitle">%s</div>%s</div>' % (_e(p.get("title", "")), "".join(rows))
    return css, body


KINDS = dict(notice=notice, chat=chat, post=post, news=news, board=board, playlist=playlist, form=form, sign=sign)


def _chrome():
    for c in CHROME_CANDIDATES:
        if os.path.exists(c):
            return c
    found = shutil.which("chrome") or shutil.which("msedge")
    if found:
        return found
    raise RuntimeError("자료 그림을 만들 Chrome/Edge를 찾지 못했습니다.")


def render(kind, params, out_png, width_hwp):
    """width_hwp(HWPUNIT) 폭의 자료 PNG를 만든다. (경로, 픽셀 폭, 픽셀 높이)를 돌려준다."""
    from PIL import Image, ImageOps
    css_w = int(round(width_hwp / 7200 * 96))
    fn = KINDS[kind]
    os.makedirs(os.path.dirname(out_png) or ".", exist_ok=True)
    _WORK[0] = os.path.dirname(os.path.abspath(out_png))
    css, body = fn(params, css_w) if kind == "news" else fn(params)
    page = ('<!doctype html><html><head><meta charset="utf-8"><style>%s%s body{width:%dpx}</style></head><body>%s</body></html>'
            % (BASE_CSS, css, css_w, body))
    html_path = os.path.splitext(out_png)[0] + ".html"
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(page)
    profile = tempfile.mkdtemp(prefix="examkit_chrome_")
    try:
        cmd = [_chrome(), "--headless=new", "--disable-gpu", "--hide-scrollbars", "--no-first-run", "--no-default-browser-check",
               "--user-data-dir=" + profile, "--force-device-scale-factor=%d" % SCALE,
               "--window-size=%d,%d" % (css_w + 8, MAX_H), "--screenshot=" + os.path.abspath(out_png),
               "file:///" + os.path.abspath(html_path).replace("\\", "/")]
        subprocess.run(cmd, capture_output=True, timeout=90)
    finally:
        shutil.rmtree(profile, ignore_errors=True)
    if not os.path.exists(out_png):
        raise RuntimeError("자료 그림 캡처 실패: %s" % kind)
    with Image.open(out_png) as im:
        im = im.convert("RGB")
    box = ImageOps.invert(im.convert("L")).point(lambda v: 255 if v > 8 else 0).getbbox()
    if box:
        m = 2 * SCALE
        box = (max(0, box[0] - m), max(0, box[1] - m), min(im.width, box[2] + m), min(im.height, box[3] + m))
        im = im.crop(box)
    im.save(out_png)
    return out_png, im.width, im.height
