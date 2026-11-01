# 인곽 모의고사 (ishs 브랜치)

인천과학고 학교 생활 소재 모의고사 1~4교시(인곽 지리·생활·문화·역사)의 최종본이다. 제작기 코드와 양식은 master 브랜치와 같고, 이 브랜치에는 문항 원문과 그림, 완성 PDF가 더해져 있다.

프로젝트 전용 지침은 [PROJECT.md](PROJECT.md), 공통 작업 지침은 [AGENTS.md](../AGENTS.md)를 따른다.
새 세션은 [인수인계 상태](HANDOVER.md)와 [재현 작업 절차](../docs/reproduction-guide.md)를 읽는다. 로컬 미커밋 변경, 현재 쪽수, 저장소에 없는 과거 요청서도 구분해 기록되어 있다.

## 구조
```
content/
  1교시.md ~ 4교시.md          문항 원문(이 파일로 시험지를 다시 빌드한다)
  1교시_해설.md ~ 4교시_해설.md  정답 및 해설 원문
assets/illust/                  시험지에 쓴 그림(PNG)
  sources/                      코드로 그린 그림의 파이썬 소스
docs/plans/                     3·4교시 기획 기록
ishs/pdf/
  교시별/                       교시마다 문제지·정답표·정답 및 해설 PDF
  원본 문제.pdf                 1~4교시 시험지 합본(정답 표시 없음, 교시별 표지 포함)
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
- 각 교시 앞에 원본 HWP 양식 표지 1쪽을 붙인다. 필적 문구는 '지혜를 모아 지혜를 모아', 가형·나형·홀수형·주관식 안내는 없으며 과목을 표시한다. [표지 사용법](../docs/cover-format.md)을 따른다. `build_final.py`는 자동 적용하지만 단일 `examkit build`는 본문만 만든다.
- 해설 md는 `## N. [출제의도] …` 바로 아래에 `@answer N`을 적는다. 문항 md와 번호·정답이 다르거나 해설이 없으면 `build_key.py`가 중단된다.
- 문항 순서를 바꿀 때는 `python tools/reorder.py content/N교시.md <옛 번호 순서>`를 문항 md와 해설 md에 같은 순서로 돌린다.
- 쪽 배치와 여백은 `tools/qpos.py`, `colfill.py`, `balance.py`, `widows.py`로 점검한다(docs/hwpx-layout-notes.md).

작업 원칙과 그림 다루는 법은 AGENTS.md에 있다.
