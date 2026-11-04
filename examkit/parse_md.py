# -*- coding: utf-8 -*-
"""content/*.md → 문항 dict 리스트.

문법은 README.md 참고. 문항 dict 키:
  n, head, blocks[(kind, payload)...], ask, three, pb, cb, gap, bogi, set, opts, grid, answer
"""
import re

SETS = {
    "A": ["ㄱ", "ㄴ", "ㄱ, ㄴ", "ㄱ, ㄷ", "ㄴ, ㄷ"],
    "B": ["ㄱ", "ㄴ", "ㄱ, ㄷ", "ㄴ, ㄷ", "ㄱ, ㄴ, ㄷ"],
    "C": ["ㄱ", "ㄷ", "ㄱ, ㄴ", "ㄴ, ㄷ", "ㄱ, ㄴ, ㄷ"],
    "D": ["ㄴ", "ㄷ", "ㄱ, ㄴ", "ㄱ, ㄷ", "ㄱ, ㄴ, ㄷ"],
    "E": ["ㄱ", "ㄴ", "ㄷ", "ㄱ, ㄴ", "ㄱ, ㄷ"],
    "F": ["ㄱ", "ㄴ", "ㄷ", "ㄱ, ㄷ", "ㄴ, ㄷ"],
}
MARKS = "①②③④⑤"
_Q = re.compile(r"^##\s*(\d+)\.\s*(.*)$")


def parse_front_matter(text):
    meta = {}
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    if m:
        for ln in m.group(1).splitlines():
            if ":" in ln:
                k, v = ln.split(":", 1)
                meta[k.strip()] = v.strip()
        text = text[m.end():]
    return meta, text


def _kv_lines(lines):
    d = {}
    for ln in lines:
        if ":" in ln:
            k, v = ln.split(":", 1)
            d[k.strip()] = v.strip()
    return d


def _args(s):
    """'bar w=19000 file=x.png' → ('bar', {'w': '19000', 'file': 'x.png'})"""
    parts = s.split()
    kind = parts[0] if parts and "=" not in parts[0] else ""
    kv, pos = {}, []
    for p in parts[1 if kind else 0:]:
        if "=" in p:
            k, v = p.split("=", 1)
            kv[k] = v
        else:
            pos.append(p)
    kv["_pos"] = pos
    return kind, kv


def parse_question(n, header_rest, body_lines):
    q = dict(n=n, blocks=[], pb=0, cb=0, gap=0, three=False, head="", ask="", answer=None)
    rest = header_rest
    if "[3점]" in rest:
        q["three"] = True
    if "{page}" in rest:
        q["pb"] = 1
    if "{col}" in rest:
        q["cb"] = 1
    m = re.search(r"\{gap=(\d+)\}", rest)
    if m:
        q["gap"] = int(m.group(1))

    i = 0
    opts = []
    while i < len(body_lines):
        ln = body_lines[i]
        s = ln.strip()
        if not s:
            i += 1
            continue
        if s.startswith(":::"):
            kind, kv = _args(s[3:].strip())
            j = i + 1
            block = []
            while j < len(body_lines) and body_lines[j].strip() != ":::":
                block.append(body_lines[j].rstrip())
                j += 1
            i = j + 1
            _add_block(q, kind, kv, block)
            continue
        if s.startswith("? "):
            q["ask"] = s[2:].strip()
        elif s[0] in MARKS:
            opts.append(s[1:].strip())
        elif s.startswith("@set"):
            q["set"] = SETS[s.split()[1].strip()]
        elif s.startswith("@answer"):
            q["answer"] = int(s.split()[1])
        elif s.startswith("@status"):
            # 검토용 표시: keep(그대로) / mod(수정) / new(새 문제·발전)
            q["status"] = s.split()[1].strip()
        elif s.startswith("@inline"):
            # 선택지를 한 줄에 늘어놓는다(글자 수 기준 자동 판정을 넘어설 때)
            q["inline_opts"] = True
        elif s == '@choices' or s.startswith('@choices '):
            value = s.partition(' ')[2].strip()
            if value not in ('auto', '5', '3', '2', '1'):
                raise ValueError('@choices는 auto, 5, 3, 2, 1 중 하나여야 합니다.')
            q['choice_columns'] = None if value == 'auto' else int(value)
        elif not q["head"]:
            q["head"] = s
        else:
            q["blocks"].append(("text", s))
        i += 1
    if opts:
        q["opts"] = opts
    return q


def _add_block(q, kind, kv, block):
    block = [b for b in block]
    if kind == "box":
        q["blocks"].append(("box", [b for b in block if b.strip() or True]))
    elif kind == "code":
        q["blocks"].append(("box", ["[코드]"] + block if kv.get("title", "1") == "1" else block))
    elif kind == "table":
        rows = [[c.strip() for c in r.strip().strip("|").split("|")] for r in block if r.strip().startswith("|")]
        rows = [r for r in rows if not all(set(c) <= set("-: ") for c in r)]
        widths = [int(x) for x in kv["widths"].split(",")] if "widths" in kv else None
        q["blocks"].append(("table", dict(headers=rows[0], rows=rows[1:], widths=widths,
                                          row_h=int(kv.get("row_h", 0)))))
    elif kind == "figure":
        params = _kv_lines(block)
        q["blocks"].append(("figure", dict(kind=kind_of(kv, params), params=params, kv=kv)))
    elif kind == "bogi":
        items = [re.sub(r"^[ㄱㄴㄷ]\.\s*", "", b.strip()) for b in block if b.strip()]
        q["bogi"] = items
    elif kind == "grid":
        headers = [h.strip() for h in kv.get("headers", "").split(",")] if kv.get("headers") else None
        rows = [[c.strip() for c in r.split("|")] for r in block if r.strip()]
        if headers is None:
            headers, rows = rows[0], rows[1:]
        q["grid"] = (headers, rows)
    elif kind == "dialog":
        # "화자: 발언" 줄과, 화자 없는 줄((중략) 등은 가운데 정렬)
        pairs = [tuple(x.strip() for x in b.split(":", 1)) if ":" in b else ("", b.strip()) for b in block if b.strip()]
        q["blocks"].append(("dialog", pairs))
    else:
        raise ValueError("알 수 없는 블록: %s" % kind)


def kind_of(kv, params):
    return (kv["_pos"][0] if kv.get("_pos") else None) or kv.get("type") or params.get("type") or "bar"


def parse(text):
    meta, body = parse_front_matter(text)
    lines = body.splitlines()
    questions = []
    cur = None
    for ln in lines:
        m = _Q.match(ln)
        if m:
            if cur:
                questions.append(parse_question(*cur))
            cur = (int(m.group(1)), m.group(2), [])
        elif cur:
            cur[2].append(ln)
    if cur:
        questions.append(parse_question(*cur))
    return meta, questions


def check(meta, questions):
    """문항 수·배점·정답 분포·보기 세트 정합성 점검. 문제 목록 반환(없으면 빈 리스트)."""
    from collections import Counter
    problems = []
    n = len(questions)
    if n != int(meta.get("count", 20)):
        problems.append("문항 수 %d (기대 %s)" % (n, meta.get("count", 20)))
    if sorted(q["n"] for q in questions) != list(range(1, n + 1)):
        problems.append("문항 번호는 중복 없이 1부터 연속해야 함")
    three = sum(q["three"] for q in questions)
    if three != int(meta.get("three", 10)):
        problems.append("3점 문항 %d개 (기대 %s)" % (three, meta.get("three", 10)))
    dist = Counter(q["answer"] for q in questions)
    for k in range(1, 6) if n >= 10 else ():
        if abs(dist.get(k, 0) - n / 5) > 1:
            problems.append("정답 %s 분포 치우침: %s" % (MARKS[k - 1], dict(dist)))
            break
    for q in questions:
        if q["answer"] is None:
            problems.append("%d번 정답 없음" % q["n"])
        elif q["answer"] not in range(1, 6):
            problems.append("%d번 정답은 1~5여야 함" % q["n"])
        if "bogi" in q and "set" not in q:
            problems.append("%d번 보기형인데 @set 없음" % q["n"])
        if "bogi" in q and len(q["bogi"]) != 3:
            problems.append("%d번 보기 항목이 3개가 아님" % q["n"])
        if "opts" in q and len(q["opts"]) != 5:
            problems.append("%d번 선택지가 5개가 아님" % q["n"])
        if "grid" in q:
            headers, rows = q["grid"]
            if len(rows) != 5:
                problems.append("%d번 짝짓기 선택지가 5개가 아님" % q["n"])
            if not headers or any(len(row) != len(headers) for row in rows):
                problems.append("%d번 짝짓기 선택지의 열 수가 일치하지 않음" % q["n"])
        if not q["ask"]:
            problems.append("%d번 질문(? 줄) 없음" % q["n"])
        kinds = ("bogi" in q) + ("opts" in q) + ("grid" in q)
        if kinds != 1:
            problems.append("%d번 선택지 유형이 %d개" % (q["n"], kinds))
    return problems
