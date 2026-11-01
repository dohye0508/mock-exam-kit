"""md의 한 문항에 있는 그림(::: figure file …)의 폭을 바꾸고, 얹은 글·표·말풍선 좌표를 같은 비율로 맞춘다.
  python tools/figscale.py content/3교시.md 10 72          # 10번 첫 그림을 폭 72mm로
  python tools/figscale.py content/3교시.md 8 85 --nth 2   # 8번 두 번째 그림
글자 크기(font)는 그대로이므로, 줄인 뒤에는 꼭 렌더해서 글이 판 밖으로 넘치지 않는지 본다.
"""
import argparse, re

MM = 283.46
ap = argparse.ArgumentParser()
ap.add_argument("md"); ap.add_argument("q", type=int); ap.add_argument("w_mm", type=float)
ap.add_argument("--nth", type=int, default=1)
a = ap.parse_args()

raw = open(a.md, encoding="utf8", newline="").read()
nl = "\r\n" if "\r\n" in raw else "\n"
lines = raw.replace("\r\n", "\n").split("\n")
qi = next(i for i, l in enumerate(lines) if re.match(r"## %d\.(\s|$)" % a.q, l))
qend = next((i for i in range(qi + 1, len(lines)) if lines[i].startswith("## ")), len(lines))
figs = [i for i in range(qi, qend) if lines[i].startswith("::: figure") and "w=" in lines[i]]
fi = figs[a.nth - 1]
m = re.search(r"\bw=(\d+)", lines[fi]); old_w = int(m.group(1)); new_w = round(a.w_mm * MM)
f = new_w / old_w
lines[fi] = re.sub(r"\bw=\d+", "w=%d" % new_w, lines[fi])
lines[fi] = re.sub(r"\bh=(\d+)", lambda m: "h=%d" % round(int(m.group(1)) * f), lines[fi])
fmt = lambda v: ("%.2f" % (float(v) * f)).rstrip("0").rstrip(".")
for i in range(fi + 1, qend):
    l = lines[i]
    if l.startswith(":::"):
        break
    m = re.match(r"((?:text|table|bubble|label)\d+): ([^|]*?)(\s*\|.*)?$", l)
    if m:
        parts = m.group(2).split(",")
        out = []
        for p in parts:
            p = p.strip()
            n = re.match(r"^-?\d+(?:\.\d+)?", p)
            out.append(fmt(n.group(0)) + p[n.end():] if n else p)
        lines[i] = "%s: %s%s" % (m.group(1), ",".join(out), m.group(3) or "")
    m = re.match(r"(table\d+_rowh): ([\d.]+)$", l)
    if m:
        lines[i] = "%s: %s" % (m.group(1), fmt(m.group(2)))
open(a.md, "w", encoding="utf8", newline="").write(nl.join(lines))
print("q%d 그림%d: %.1fmm → %.1fmm (×%.3f)" % (a.q, a.nth, old_w / MM, new_w / MM, f))
