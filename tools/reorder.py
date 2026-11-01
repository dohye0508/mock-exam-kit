"""md의 문항 순서를 바꾸고 번호를 다시 매긴다. 쪽 맞추기에서 큰 문항과 작은 문항을 한 단에 짝지을 때 쓴다.
  python tools/reorder.py content/4교시.md 1,7,2,10,3,4,...   # 새 순서를 옛 번호로
번호만 바뀌므로, 발문 안에서 다른 문항 번호를 가리키는 말이 있으면 직접 고친다.
"""
import re, sys

path, order = sys.argv[1], [int(x) for x in sys.argv[2].split(",")]
raw = open(path, encoding="utf8", newline="").read()
nl = "\r\n" if "\r\n" in raw else "\n"
text = raw.replace("\r\n", "\n")
parts = re.split(r"(?m)^(?=## \d+\.)", text)
head, qs = parts[0], {int(re.match(r"## (\d+)\.", p).group(1)): p for p in parts[1:]}
assert sorted(order) == sorted(qs), "순서에 모든 문항 번호가 한 번씩 있어야 한다"
out = head + "".join(re.sub(r"^## \d+\.", "## %d." % (i + 1), qs[o].rstrip("\n") + "\n\n", count=1)
                     for i, o in enumerate(order))
open(path, "w", encoding="utf8", newline="").write(out.rstrip("\n").replace("\n", nl) + nl)
print("새 순서:", " ".join("%d←%d" % (i + 1, o) for i, o in enumerate(order) if i + 1 != o) or "변화 없음")
