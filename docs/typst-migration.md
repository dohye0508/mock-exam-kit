# Typst 출력 연결

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
- 한 줄 선택지는 원본의 번호/내용 10칸 표(과탐 13번, 사탐 12번)를 재사용한다. 셀 폭·여백을 유지하며 내용만 교체한다. 셀 안 문단의 탭 좌표를 전체 선택지 위치로 사용하거나 단 폭을 임의 등분하지 않는다.
- 수식은 매번 입력에서 생성한다. LaTeX MathText 문법과 한글식 `over`·일부 연산자 변환을 지원한다. 원본 HancomEQN 글꼴만 쓰며 미지원 명령/글리프는 오류다. 행렬·cases 등 모든 한글 수식 문법을 지원하는 것은 아니다.
- `--no-compile`(`--no-convert` 별칭)은 `.typ`와 `.assets`까지만 만든다. PDF 컴파일·쪽수·머리글·문항 번호 검사가 끝나야 기존 PDF를 교체한다.

## 검증과 한계

`EXAMKIT_TYPST_ROOT`와 `TYPST_EXE`를 설정한 뒤 `python -X utf8 -m unittest discover -s tests -v`로 실제 본문·표지 통합 검사를 실행한다. 본문 검사는 COM 모듈을 차단하고 새 문항, 메타데이터, 수식, 정답 세 가지 색, 실패 시 이전 PDF 보존을 확인한다. 전체 생성 명령도 별도 COM 차단 환경에서 실행했다.

한글 프로그램 없이 출력된다는 것과 한글 렌더링의 모든 픽셀이 같다는 것은 다르다. 수식 배치는 MathText, 문단 배치는 기존 원본 서식 엔진을 사용하며 한글과의 완전한 렌더링 동일성은 검증되지 않았다. 분할 불가능한 큰 표/그림은 내용이나 배치를 조정해야 한다. `--reuse`는 입력 변경을 자동 검증하지 않는다.

원본 저장소 PR은 사용자 검토 후 진행한다. 원본 글꼴·개인 문항·생성 PDF는 공개 커밋에 포함하지 않는다.
