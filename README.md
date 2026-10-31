# mock-exam-kit

수능(평가원) 탐구 영역 문제지 양식을 그대로 흉내 내는 **모의고사 문제지 생성 툴킷**.
Markdown으로 문항을 쓰면 8절 2단·4쪽 HWP/PDF가 나온다. 그림(그래프·배치도), 표, 수식, 분수, <보기> 상자, 짝짓기 선택지를 지원한다.

> 실제 문항·정답·산출물(`content/*.md`, `output/`)은 저장소에 올리지 않는다(`.gitignore`). 양식(`templates/`)은 실제 평가원 지면을 바탕으로 하므로 저장소를 공개로 돌리지 말 것.

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
문항 작성 원칙은 [prompt.md](prompt.md)를 먼저 읽는다. 문법 전체 예시는 [content/example.md](content/example.md).

## 문항 Markdown 문법
```markdown
---
title: 1교시            # 출력 파일 이름
year: 2026학년도         # 머리글 "2025학년도 대학수학능력시험 문제지" 자리
exam: 인곽수학능력시험
period: 제1교시          # 둥근 상자 "제4교시" 자리
area: 인곽탐구           # "과학탐구" 자리
subject: 인곽 지리       # "(화학Ⅰ)" 자리 → "(인곽 지리)"
pages: 4                 # 쪽수(쪽번호 분모, 쪽수 검사)
count: 20
three: 10
---

## 3. [3점] {page}        # [3점], {page}=새 쪽에서 시작, {col}=새 단, {gap=N}=문항 뒤 빈 줄 수(기본 3)
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
인라인 마크업: `$ {a} over {b} $` 한글 수식 스크립트, `__밑줄__`, `{{frac|분자|분모}}` 세로 분수.

그림 블록 파라미터: `values1:, values2:, legend:`(복수 계열), `ylim:`, `title:`, `inch_w:/inch_h:`(그림 원본 크기), timeline은 `events: 시각|문구; 시각|문구`, table_grid는 `rows: A,B;C,D`(`-` 빈칸, `#`은 음영).

## 구조
```
examkit/    parse_md.py(문법) build.py(조립) hwpx.py(XML 조각) figures.py(그림) convert.py(한글 변환) cli.py
templates/kice-sci/   평가원 과탐 양식을 HWPX로 풀어 둔 것 + frags/(첫 문단 등 조각)
skills/science-apparatus/   실험 기구·배치 도식 SVG 스케치 스킬(gist 기반), figures.sketch 가 호출
content/    example.md 만 커밋. 실제 교시 파일과 answers/ 는 로컬 보관
assets/reference/tongsarang/   한국사·사탐·통합사회 기출 문항 이미지 (Git LFS)
```

## 기출 문항 이미지 참고 자료

`assets/reference/tongsarang/<과목>/<학년도>/<원본 파일명>.jpg`에 [통사랑](https://tongsarang.kr/)에서 2026-10-31에 내려받은 문항 이미지 13,985개를 보관한다. 한국사 1,340문항, 통합사회 805문항, 사회탐구 9과목 11,840문항이다. 사이트에 등록된 전체 분량이며 역대 모든 시험을 빠짐없이 포함하지는 않는다.

이미지는 삽화만 잘라낸 파일이 아니라 지문·선택지를 포함한 문항 전체이다. 원본 파일명과 학년도 표기를 유지했다. ZIP, PDF, 검색용 HTML, 정답 목록은 포함하지 않는다. 출제용 `content/` 및 문제지 양식 `templates/`와 분리된 참고 자료이며, 공개 자료라는 사실이 자유로운 수정·재배포 허락을 의미하지 않는다.

이미지 파일은 Git LFS로 관리한다. Git LFS를 설치한 환경에서 저장소를 복제하고 `git lfs pull`을 실행하면 실제 이미지가 내려받아진다.

## 다른 양식 쓰기
1. 양식 HWP를 한글에서 HWPX로 저장 → 압축 해제해 `templates/<이름>/` 에 둔다.
2. 첫 문단(구역 설정+머리글)을 `frags/p0.xml` 로 뽑고, `hwpx.STYLE`/`BF` 의 서식 ID와 `build._header_rules` 의 치환 규칙을 그 양식에 맞게 고친다.
