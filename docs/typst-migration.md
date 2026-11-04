# Typst 출력 연결

**원본 동일성은 완료되지 않았다.** 원본에서 읽는 서식과 자체 추가 배치값의 구분은 [서식 점검 기록](source-fidelity-audit.md)을 따른다. 아래 실행 성공과 지원 기능 목록은 원본 렌더링 동일성을 뜻하지 않는다.

`codex/typst-backend`의 기본 `build`, `review`, 표지와 최종 합본을 Typst 경로에 연결했다. 본문·표지는 편집 가능한 텍스트/도형 명령으로 생성하며 완성 문제지 이미지를 배경으로 쓰지 않는다. 정답표·해설·PDF 병합은 기존 PyMuPDF 빌더를 사용한다. 한글 실행·COM은 필요하지 않다.

## 준비와 실행

Python 의존성은 `pip install -r requirements.txt`로 설치한다. 기존 조판 엔진과 추출한 원본 글꼴은 공개 저장소에 포함하지 않았다. 저장소만 복제하면 실행되는 독립 배포본은 아니다.

```powershell
$env:EXAMKIT_TYPST_ROOT='C:/path/to/문제 조판'
$env:TYPST_EXE='C:/path/to/typst.exe'
python -m examkit build content/example.md -o output/example
python -m examkit review content/example.md -o output/review
python tools/build_final.py output/demo docs/examples/format-demo.md
```

엔진과 출력은 같은 드라이브에 둔다. 엔진에는 `scripts/compose.py`, `flow.py`, `cover.py`, `exam.typ`, `original-header.typ`, 원본 `source-layout/`, HML/JSON 자료, `fonts/`가 필요하다. 수식 `HancomEQN.ttf`, 해설용 `HBATANG-native-fallback.ttf`, `H2HDRM.TTF`, `H2MJRE.TTF`, `H2GTRE.TTF`, 정답표용 `Batang-native.ttf`와 검토 안내용 `H2GTRM.ttf`도 해당 폴더에 둔다. 누락된 글꼴을 다른 글꼴로 자동 대체하지 않는다. HTML 자료 그림은 Chrome/Edge가 추가로 필요하다.

## 편집 범위

- 본문은 `body_template: science`(기본)·`social`; 표지는 `cover_template: korean`·`math`다. 원본 엔진의 국어·영어·수학 본문은 아직 이 저장소의 Markdown 연결 대상이 아니다.
- `body_title`, `year`, `exam`, `area`, `subject`, `period`와 표지 문구를 바꿀 수 있다. `pages: auto`는 실제 쪽수로 표지/합본을 만든다. 숫자는 최소 쪽수를 확보하되 내용이 초과하면 오류로 처리한다.
- 상자·표·그림·대화·보기·짝짓기·선택지, 그림 위 글상자/말풍선/표, 나란히 배치, `{page}`, `{col}`, `{gap}`, `@status`를 연결했다. `@center`는 제목 서체, `@c`는 본문 서체로 가운데 정렬한다.
- 선택지는 실제 글폭·수식 폭과 한 글자 크기의 여유를 검사해 5개 한 줄 → 3+2 → 2+2+1 → 1개씩 순서로 고른다. 한 줄은 원본 번호/내용 10칸 표(과탐 13번, 사탐 12번), 3+2와 2+2+1은 원본 문단의 탭 위치와 행간을 재사용한다. `@choices auto|5|3|2|1`로 문항별 지정할 수 있다. `@inline`은 기존 한 줄 지정과 호환되며, 원본 칸을 넘는 강제 한 줄 배치는 오류로 알린다. 짝짓기 `grid`의 열은 그대로 유지한다.
- 자료 뒤 `?` 질문문은 과탐 `02-문제(2행)`·사탐 `문제 아래 - 일반` 스타일을 사용한다. 보기는 대응 원본 항목의 표지 문자와 본문 글자 모양을 각각 유지하며, 긴 항목의 줄바꿈·들여쓰기는 해당 원본 문단 서식을 따른다.
- `question_spacing: auto`(기본)는 단 아래에 남은 공간을 문항 사이와 마지막 문항 아래에 나누되, 문항 사이에 추가하는 간격을 원본 발문 두 줄 높이 이하로 제한한다. 큰 빈 공간을 전부 문항 사이에 밀어 넣지 않는다. 문항 내부의 상자·보기·선택지는 함께 이동하며, 쪽수와 단 배치는 유지한다. `compact`는 이 분배를 끄고 원본 문단 간격만 사용한다. `{gap=N}`은 여기에 빈 문단 N개를 더한다. 단을 넘겨 이어지는 문항이 있는 단은 재분배하지 않는다. 한 단에 들어가는 문항은 통째로 유지하므로 긴 문항 앞에는 남는 공간이 생길 수 있다.
- 수식은 매번 입력에서 생성한다. MathText에 `matrix`·`pmatrix`·`bmatrix`·`Bmatrix`·`vmatrix`·`Vmatrix`·`cases` 환경의 행/열 배치를 추가했다. 분수·첨자·중첩 행렬에도 적용하며, 본문·보기·선택지·해설에서 같은 처리기를 사용한다. 한글식 `matrix {a&b#c&d}`, `cases {x&x>0#-x&x<0}`와 기존 `over`도 지원한다. 원본 HancomEQN만 사용하고, 없는 이중 세로선 글리프는 같은 글꼴의 세로선 두 개로 구성한다. `array`·`align` 및 전체 한글 수식 문법을 구현한 것은 아니다. [행렬·경우 나눔 예제](examples/math-grids.md)를 참고한다.
- `--no-compile`(`--no-convert` 별칭)은 `.typ`와 `.assets`까지만 만든다. PDF 컴파일·쪽수·머리글·문항 번호 검사가 끝나야 기존 PDF를 교체한다.

## 검증과 한계

`EXAMKIT_TYPST_ROOT`와 `TYPST_EXE`를 설정한 뒤 `python -X utf8 -m unittest discover -s tests -v`로 실제 본문·표지 통합 검사를 실행한다. 본문 검사는 COM 모듈을 차단하고 새 문항, 메타데이터, 수식, 정답 세 가지 색, 실패 시 이전 PDF 보존을 확인한다. 전체 생성 명령도 별도 COM 차단 환경에서 실행했다.

한글 프로그램 없이 출력된다는 것과 한글 렌더링의 모든 픽셀이 같다는 것은 다르다. 수식 배치는 MathText, 문단 배치는 기존 원본 서식 엔진을 사용하며 한글과의 완전한 렌더링 동일성은 검증되지 않았다. 분할 불가능한 큰 표/그림은 내용이나 배치를 조정해야 한다. `--reuse`는 입력 변경을 자동 검증하지 않는다.

원본 저장소 PR은 사용자 검토 후 진행한다. 원본 글꼴·개인 문항·생성 PDF는 공개 커밋에 포함하지 않는다.
