# mock-exam-kit

AI 작업 시작: [AGENTS.md](AGENTS.md)를 먼저 읽는다. 시각 자료의 유형별 실제 기출 예시와 선택 다운로드 방법은 [자료 참고 가이드](docs/visual-reference-guide.md)를 따른다. AI 공통 지침은 AGENTS.md에서 관리하고, 학교별 규칙은 [ishs/PROJECT.md](ishs/PROJECT.md)로 분리한다.

## 새 세션에서 시작하는 순서 — 필독

대화 기록을 알고 있다고 가정하지 않는다. 아래 순서로 파일을 읽고 **[재현 작업 절차](docs/reproduction-guide.md)**에 따라 작업한다.

1. `git status --short`, `git branch --show-current`로 브랜치·기존 변경을 확인한다.
2. 이 README → [AGENTS.md](AGENTS.md) → [재현 작업 절차](docs/reproduction-guide.md)를 읽는다.
3. 기존 인곽 시험을 이어 만들면 [ishs/PROJECT.md](ishs/PROJECT.md), [ishs/README.md](ishs/README.md), [prompt.md](prompt.md), [인수인계 상태](ishs/HANDOVER.md)를 읽는다. 다른 시험은 별도 프로젝트 지침을 만든다.
4. 아래 표에서 작업 대상의 **원본·빌더·상세 지침**을 확인하고 실제 파일을 연다. 문서만 읽고 새 양식을 다시 그리지 않는다.
5. 필요한 원문·그림·글꼴을 확인한 뒤 새 출력 폴더에 빌드하고, 검사·렌더링을 통과한 결과만 배포한다. 과거 PDF나 `--reuse`를 최신 결과로 간주하지 않는다.

### 어떤 양식이 어디에 있는가

| 대상 | 실제 원본/구현 | 수정할 곳과 실행기 | 반드시 함께 읽을 문서 |
|---|---|---|---|
| 문제 본문(2단) | `templates/kice-sci/`의 HWPX 구성 파일. `Contents/header.xml`은 글꼴/문단, `frags/p0.xml`은 첫 쪽 머리, `Contents/masterpage*.xml`은 바탕쪽 | 내용은 `content/N교시.md`. `examkit/parse_md.py` → `examkit/build.py`·`hwpx.py` → `convert.py` | [HWPX 배치 노트](docs/hwpx-layout-notes.md), 아래 MD 문법 |
| 각 교시 표지 | `templates/covers/csat-2017-v2-source.hwp/.hwpx/.pdf`. 받은 원본은 보존 | `tools/build_cover.py`; 제목·교시·과목은 문항 MD 메타데이터 | [표지 양식](docs/cover-format.md) |
| 정답 및 해설(3단) | 원본 PDF 실측값을 `tools/build_key.py`에 구현. 별도 HWP 원본은 없음 | 내용은 `content/N교시_해설.md`, 정답은 문항 MD. `tools/build_key.py` | [해설 양식](docs/explanation-format.md), [미리보기](docs/explanation-layout-preview.png) |
| 독립 정답표 | `tools/answer_key.py`에 그리는 코드. 해설 안의 작은 정답표와 별개 | 문항 MD에서 정답/배점 읽기 → `tools/answer_key.py` | [재현 작업 절차](docs/reproduction-guide.md) |
| 그림과 글상자 | 최종 PNG는 `assets/illust/`, 코드 도식은 `assets/illust/sources/`, 자료 렌더러는 `examkit/materials.py` | MD의 `figure file`·`textN`·`bubbleN`·`tableN`; 정확한 도식은 코드 | [HWPX 배치 노트](docs/hwpx-layout-notes.md), [기출 가이드](docs/visual-reference-guide.md) |
| 배포 합본 | 위 결과를 조립 | `tools/build_final.py`: 교시별 표지+본문 / 정답표 / 해설의 세 PDF | [재현 작업 절차](docs/reproduction-guide.md) |
| 문항 내용(출제·수정) | 노하우는 코드가 아니라 문서 | `content/N교시.md`; 대안 제시 → 작성 → 코드 검산 → 빌드·잘라 보기 | [출제 노하우](docs/authoring-style.md), [prompt.md](prompt.md), 프로젝트 지침 |
| 삽화 요청·납품(작업 AI가 이미지를 못 만들 때) | 외부 생성기에 zip으로 넘기는 요청 묶음(저장소 밖) | `PROMPT.md`+`layout.png`+`style_k.png` 작성 → 받은 PNG를 `assets/illust/`에 → `DELIVERY.md` 좌표로 글 얹기 | [삽화 요청서](docs/illustration-request.md) |
| 색 표시 검토본 | `examkit/review.py` | `python -m examkit review …`; 정답이 드러나는 검토 전용 | [재현 작업 절차](docs/reproduction-guide.md) |

수능(평가원) 탐구 영역의 원본 양식을 사용하는 **모의고사 문제지 생성 툴킷**.
Markdown으로 문항을 쓰면 2단 HWP/PDF가 나온다. 쪽수는 각 문항 파일의 설정을 따르며, 최종 합본에는 교시별 표지를 붙인다. 그림(그래프·배치도), 표, 수식, 분수, <보기> 상자, 짝짓기 선택지를 지원한다.

> 일반 예시는 `content/example.md`이며, 현재 `ishs` 브랜치에서는 `content/1교시.md`~`4교시.md`와 각 해설도 Git 추적 대상이다. `output/`과 생성 PDF/HWP는 기본적으로 무시된다. 실제 포함 여부는 `git ls-files`와 `.gitignore`로 확인한다. 참고 원본과 양식의 배포 범위를 확인하지 않고 저장소를 공개로 바꾸지 않는다.

## 요구 사항
- Windows + **한컴오피스 한글** (HWPX → HWP/PDF 변환을 COM 자동화로 수행)
- Python 3.10+ : `pip install -r requirements.txt` (pywin32, lxml, matplotlib)
- 선택: `skills/science-apparatus` 의 SVG 스케치를 쓰려면 `pip install cairosvg`

## 사용법
```bash
python -m examkit check content/1교시.md          # 문항 수·3점 개수·정답 분포 점검
python -m examkit build content/1교시.md -o output # output/<title>.hwpx, .hwp, .pdf
python -m examkit build "content/*교시.md"          # 여러 개
python -m examkit build content/example.md --no-convert   # 한글 없이 hwpx만
```
현재 인곽 프로젝트의 문항 작성 원칙은 [prompt.md](prompt.md)를 읽는다. 다른 시험에 학교 전용 규칙을 그대로 적용하지 않는다. 문법 예시는 [content/example.md](content/example.md).

### 교시별 표지

사용자가 제공한 HWP 원본을 그대로 사용하는 [표지 양식과 사용법](docs/cover-format.md)이 있다. 원본은 `templates/covers/`, 빌더는 `tools/build_cover.py`다. 글꼴이나 상자를 별도로 흉내 내지 않는다.

```powershell
python tools/build_cover.py output/covers                         # 네 교시 표지: HWPX/HWP/PDF
python tools/build_cover.py output/covers content/1교시.md         # 한 교시
python tools/build_cover.py output/covers --no-convert content/1교시.md # HWPX만
python tools/build_final.py out                                   # 교시마다 표지 1쪽을 붙인 최종 합본
```

가형·나형·홀수형과 단답형 안내는 제거하며, 필적 확인 문구는 **지혜를 모아 지혜를 모아**다. 시험명·교시·영역·과목은 문항 MD 메타데이터에서 읽는다. 다른 프로젝트의 필적 문구/발행 표시는 `handwriting:`/`issuer:`로 바꾼다. 표지는 본문 쪽수에 포함하지 않으며, `--no-cover`로 명시적으로 생략할 수 있다. 원본 크기 표지와 본문 용지에 균일 축소한 표지를 구분한다.

### 정답표와 정답 및 해설
```bash
python tools/answer_key.py 정답표.pdf content/1교시.md content/2교시.md      # 평가원 양식 정답표(교시마다 한 쪽)
python tools/build_key.py 해설.pdf content/1교시.md content/2교시.md         # 정답 및 해설(3단 편집). content/N교시_해설.md를 읽는다
python tools/build_final.py out                                              # 원본 문제 합본 + 정답표 + 정답 및 해설을 한 번에(한글 필요)
python tools/build_final.py out --reuse                                      # 이미 변환한 시험지 PDF를 재사용
```
해설 파일(`content/N교시_해설.md`)은 `## 1. [출제의도] …`로 시작하고 바로 아래 줄에 `@answer 3`을 적는다(문항 md와 번호·정답이 다르거나 해설이 없으면 빌드가 중단된다). 예시 PDF를 실측한 지면·글꼴·정답표 규격은 [해설 양식](docs/explanation-format.md)을 따른다. 본문은 문단으로 쓰며 `<b> <i> <sub> <sup>`와 유니코드 기호를 쓸 수 있다.

## 문항 Markdown 문법
```markdown
---
title: 1교시            # 출력 파일 이름
year: 2026학년도         # 머리글 "2025학년도 대학수학능력시험 문제지" 자리
exam: 모의평가
period: 제1교시          # 둥근 상자 "제4교시" 자리
area: 사회탐구           # "과학탐구" 자리
subject: 한국지리       # "(화학Ⅰ)" 자리에 들어갈 과목
pages: 4                 # 본문 쪽수(쪽번호 분모, 쪽수 검사). 4 초과(예: 6)면 바탕쪽을 자동으로 늘리고 '확인 사항'을 마지막 쪽에 둔다
count: 20
three: 10
---

## 3. [3점] {page}        # [3점], {page}=새 쪽, {col}=새 단, {gap=N}=문항 뒤 빈 줄 수(현재 기본 1)
표는 … 나타낸 것이다.       # 첫 줄 = 발문
::: box                   # 자료 상자. '['로 시작하는 줄은 소제목
◦ 항목
[규칙]
◦ __밑줄__ 과 $수식$ 사용 가능
:::
::: table widths=12000,18557   # 테두리 표. 첫 행이 머리행. widths 는 HWPUNIT(단 너비 30557)
| 시간 | 활동 |
| 08:00 | 0교시 |
:::
::: figure bar w=17000          # 그림. 종류: bar barh line pie timeline table_grid sketch / file=경로.png
labels: 아침, 8교시, 1차, 2차
values: 18, 7, 4, 11
ylabel: 학생 수(명)
:::
::: dialog                      # 갑/을/병 대화 자료
갑: …
을: …
:::
? 이에 대한 설명으로 옳은 것만을 <보기>에서 있는 대로 고른 것은?   # '? ' 줄 = 질문
::: bogi
ㄱ. …
ㄴ. …
ㄷ. …
:::
@set A                          # ㄱㄴㄷ 조합 세트 A~F (parse_md.SETS)
@answer 3
```
선택지는 세 가지 중 하나만 쓴다: `::: bogi` + `@set`, 문장형 `① …`~`⑤ …`(짧으면 한 줄 표로 배치), 짝짓기 `::: grid headers=(가),(나),(다)` + `값 | 값 | 값` 5줄.
인라인 마크업: 수식은 `$…$` 안에 LaTeX(`$rac{2}{5}$`, `\sqrt`, `\sum`, `^`, `_`, `\le` 등 → `hwpx.latex_to_hwp`가 한글 수식으로 변환) 또는 한글 수식 스크립트(`$ {a} over {b} $`) 둘 다 된다. `__밑줄__`(본문 전용, 그림 위 글상자에서는 쓰지 않음), `{{frac|분자|분모}}` 세로 분수. `~`는 빌드 때 `∼`로 바뀐다. 표 칸에 `^`만 쓰면 위 칸과 세로 합치기. 선택지를 한 줄로 강제하려면 문항 안에 `@inline`.

그림 블록 파라미터: `values1:, values2:, legend:`(복수 계열), `ylim:`, `title:`, `inch_w:/inch_h:`(그림 원본 크기), timeline은 `events: 시각|문구; 시각|문구`, table_grid는 `rows: A,B;C,D`(`-` 빈칸, `#`은 음영).

외부 그림(삽화 등): `::: figure file path=assets/illust/<id>.png w=25512 h=17008` 다음 줄에 `:::`.
- `w`·`h`는 HWPUNIT이다(1 mm ≈ 283.5). 예시 값은 90 × 60 mm.
- 투명한 부분은 흰색으로 채운다.
- `h`를 주면 그 가로세로비가 되도록 흰 여백을 덧댄다. 잘라 내지는 않는다.
- 삽화 요청서 묶음(`assets/illust/handoffN/`)은 작업 흔적이라 저장소에 두지 않는다. 양식은 [삽화 요청서](docs/illustration-request.md).

글자·수치가 든 자료(안내문·메신저·게시물·기사 등)는 `examkit/materials.py`가 HTML로 짜서 Chrome(또는 Edge) headless로 찍는다.
- 쓰는 법: `::: figure <종류> w=<HWPUNIT>` 다음 줄부터 `키: 값`을 쓴다. 지면에서 실제 폭 그대로 그리며 약 384dpi이고, 흑백이다.
- 값 안의 `\n`은 줄바꿈이다.
- `image:`에 넣은 삽화는 둘레의 흰 여백을 잘라 쓴다.

| 종류 | 무엇 | 키 |
|---|---|---|
| `notice` | 안내문·공지 | `title` `from` `date` `item1..` `table: 머리\|머리 ; 칸\|칸` `note` `image`(오른쪽 약 36%) |
| `chat` | 메신저 화면 | `title` `me`(오른쪽에 보일 사람) `msg1..: 이름\|내용\|시각`. 내용이 `[사진] 경로`이면 사진 말풍선. 같은 사람이 이어서 보내면 이름·프로필 생략 |
| `post` | SNS·봇 게시물 | `account` `time` `title` `line1..` `image` |
| `news` | 신문 기사 | `paper` `issue` `headline` `sub` `body1..` `image` `caption`(폭이 넓으면 2단) |
| `board` | 출발 전광판 등 | `title` `header: a\|b` `row1..: a\|b` |
| `playlist` | 재생 목록 | `title` `row1..: 번호\|곡명\|길이` `now`(재생 중인 행 번호) |
| `form` | 기록표·명단 | `title` `header` `row1..` `note` |
| `sign` | 층별 안내판 | `title` `floor1..: 5F\|내용` |

## 구조
```
examkit/    parse_md.py(문법) build.py(조립) hwpx.py(XML 조각) figures.py(그림) convert.py(한글 변환) cli.py
templates/kice-sci/   평가원 과탐 양식을 HWPX로 풀어 둔 것 + frags/(첫 문단 등 조각)
skills/science-apparatus/   실험 기구·배치 도식 SVG 스케치 스킬(gist 기반), figures.sketch 가 호출
templates/covers/    수정하지 않는 원본 표지 HWP/HWPX/PDF
tools/      build_cover.py(표지), build_key.py(해설), answer_key.py(정답표), build_final.py(합본)
content/    example.md + 현재 프로젝트의 문항 MD와 해설 MD (추적 여부는 브랜치별 확인)
assets/reference/tongsarang/   한국사·사탐·통합사회 기출 문항 이미지 (Git LFS)
assets/reference/pdf/           과탐·직탐 기출 문제지 PDF (Git LFS)
assets/reference/catalog/       참고 PDF 목록·출처·해시·수집 범위
docs/       재현 절차·서식 수치·삽화 배치·참고 자료 안내
ishs/       현재 학교 프로젝트 전용 규칙·인수인계 (다른 시험에 자동 적용 금지)
```

## 기출 문항 이미지 참고 자료

`assets/reference/tongsarang/<과목>/<학년도>/<원본 파일명>.jpg`에 [통사랑](https://tongsarang.kr/)에서 2026-10-31에 내려받은 문항 이미지 13,985개를 보관한다. 한국사 1,340문항, 통합사회 805문항, 사회탐구 9과목 11,840문항이다. 사이트에 등록된 전체 분량이며 역대 모든 시험을 빠짐없이 포함하지는 않는다.

이미지는 삽화만 잘라낸 파일이 아니라 지문·선택지를 포함한 문항 전체이다. 원본 파일명과 학년도 표기를 유지했다. ZIP, PDF, 검색용 HTML, 정답 목록은 포함하지 않는다. 출제용 `content/` 및 문제지 양식 `templates/`와 분리된 참고 자료이며, 공개 자료라는 사실이 자유로운 수정·재배포 허락을 의미하지 않는다.

사탐·한국사·통합사회 이미지 원본 약 2.90GB와 추가 과학탐구·직업탐구 기출 문제지 고유 PDF 3,159개(4.256GB)를 Git LFS로 관리한다. 과탐·직탐은 [전체 목록](assets/reference/catalog/archive.jsonl)에서 찾고 [PDF 안내](assets/reference/pdf/README.md)에 따라 필요한 파일만 받는다. 새 작업 환경에서 전체 다운로드를 기본으로 하지 않는다. 새로 복제할 때는 `GIT_LFS_SKIP_SMUDGE=1`로 자동 다운로드를 생략하고, 기존 저장소에서는 `git lfs install --local --skip-smudge`를 설정한 뒤 `git lfs pull --include="필요한 원본 경로" --exclude=""`로 선택한 파일만 받는다. 경로가 존재하더라도 작은 텍스트 형태의 LFS 포인터일 수 있다. [과목별 예시와 PowerShell 명령](docs/visual-reference-guide.md)을 참고한다.

## 다른 양식 쓰기
1. 양식 HWP를 한글에서 HWPX로 저장 → 압축 해제해 `templates/<이름>/` 에 둔다.
2. 첫 문단(구역 설정+머리글)을 `frags/p0.xml` 로 뽑고, `hwpx.STYLE`/`BF` 의 서식 ID와 `build._header_rules` 의 치환 규칙을 그 양식에 맞게 고친다.
