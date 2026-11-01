# 인곽 모의고사 (ishs 브랜치)

인천과학고 학교 생활 소재 모의고사 1~4교시(인곽 지리·생활·문화·역사)의 최종본이다. 제작기 코드와 양식은 master 브랜치와 같고, 이 브랜치에는 문항 원문과 그림, 완성 PDF가 더해져 있다.

## 구조
```
content/
  1교시.md ~ 4교시.md          문항 원문(이 파일로 시험지를 다시 빌드한다)
  1교시_해설.md ~ 4교시_해설.md  정답 및 해설 원문
assets/illust/                  시험지에 쓴 그림(PNG)
  sources/                      코드로 그린 그림의 파이썬 소스
docs/plans/                     3·4교시 기획 기록
ishs/pdf/
  원본 문제.pdf                 1~4교시 시험지 합본(정답 표시 없음, 20쪽)
  정답표.pdf                    평가원 양식 정답표(교시마다 한 쪽)
  정답 및 해설.pdf              평가원 양식 정답 및 해설(3단 편집)
examkit/, tools/, templates/    제작기(master와 동일)
```

## 다시 빌드하기
한글(한컴오피스)과 `pip install -r requirements.txt`가 필요하다.
```bash
python -m examkit check content/3교시.md                       # 문항 수·3점 개수·정답 분포 점검
python -m examkit build content/3교시.md -o output/f3          # 교시 하나를 HWPX·HWP·PDF로
python tools/build_final.py ishs/pdf                           # 원본 문제 + 정답표 + 정답 및 해설을 한 번에
python tools/answer_key.py 정답표.pdf content/1교시.md …        # 정답표만
python tools/build_key.py 해설.pdf content/1교시.md …           # 정답 및 해설만(한글 없이도 된다)
```
- 정답은 문항 md의 `@answer`, 배점은 `[3점]` 표시에서 읽는다. 정답표와 해설 빌드는 한글이 필요 없다.
- 해설 md는 `## N. [출제의도] …` 바로 아래에 `@answer N`을 적는다. 문항 md와 정답이 다르면 `build_key.py`가 경고한다.
- 문항 순서를 바꿀 때는 `python tools/reorder.py content/N교시.md <옛 번호 순서>`를 문항 md와 해설 md에 같은 순서로 돌린다.
- 쪽 배치와 여백은 `tools/qpos.py`, `colfill.py`, `balance.py`, `widows.py`로 점검한다(AGENTS.md 7장).

작업 원칙과 그림 다루는 법은 AGENTS.md에 있다.
