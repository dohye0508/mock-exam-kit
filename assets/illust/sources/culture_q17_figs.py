# -*- coding: utf-8 -*-
"""2교시 폐부 토론 문항의 그림 높이를 줄인다.
토론 화면은 네 번째 글 자리를 잘라 내고, 사전은 아래위만 살짝 줄인다.
python culture_q17_figs.py <assets/illust 폴더>"""
import os
import sys

from PIL import Image

OUT = sys.argv[1] if len(sys.argv) > 1 else "."
a = Image.open(os.path.join(OUT, "culture_wiki_debate_01.png")).convert("RGB")
top, bottom = 946, 1196                 # 잘라 낼 세로 구간(px): 네 번째 글
out = Image.new("RGB", (a.width, a.height - (bottom - top)), "white")
out.paste(a.crop((0, 0, a.width, top)), (0, 0))
out.paste(a.crop((0, bottom, a.width, a.height)), (0, top))
bg = a.getpixel((60, 900))
out.paste(bg, (225, 860, 295, 946))     # 네 번째 글로 이어지던 연결선 지우기
out.save(os.path.join(OUT, "culture_wiki_debate_02.png"))
b = Image.open(os.path.join(OUT, "culture_dictionary_01.png")).convert("RGB").crop((0, 40, 1536, 975))
b.resize((1536, 790), Image.LANCZOS).save(os.path.join(OUT, "culture_dictionary_02.png"))
print(out.size)
