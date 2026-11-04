# 교시별 표지: 원본 HWP 양식 + Typst 출력

기본 표지 생성은 `tools/build_cover.py` → `examkit/cover.py` → 제공된 조판 엔진의 `scripts/cover.py` → Typst다. 한글 COM을 호출하지 않는다. 국어·수학 표지는 새로 제공된 `국어_표지_양식.hwp`, `수학_표지_양식.hwp`에서 가져온 글꼴·문단·도형 기록을 사용한다. 저장소의 옛 `templates/covers/csat-2017-v2-source.*`는 보존하지만 기본 빌더의 입력으로 사용하지 않는다.

## 실행 환경

표지 엔진 `runtime/scripts/cover.py`, Typst 출력 코드 `runtime/original-header.typ`, 두 표지의 XML·배치 데이터는 저장소에 포함한다. 빌드에 원본 HWP나 외부 작업 폴더가 필요하지 않다. 글꼴만 공개 저장소에서 제외하므로 `tools/import_typst_fonts.py`로 보유한 글꼴을 가져온다.

```powershell
python tools/import_typst_fonts.py 'C:/path/to/보유한/fonts'
$env:TYPST_EXE = 'C:/path/to/typst.exe'
python tools/build_cover.py output/covers content/example.md
python tools/build_cover.py output/covers --no-compile content/example.md
```

엔진과 출력 폴더는 같은 드라이브에 둔다. `--no-compile`은 Typst 소스와 조판 명령 JSON까지만 만든다. 기존 `--no-convert`는 그 별칭으로 남아 있지만 HWPX를 생성하지 않는다. 일반 실행은 개별 `*_표지.typ`, `*_표지.json`, `*_표지.pdf`와 `교시별_표지.pdf`를 만든다. 문구를 바꿀 때는 MD를 수정하고 같은 명령을 다시 실행한다.

PDF는 임시 파일로 컴파일하고 쪽수·필수 문구 검사를 통과한 후 교체한다. 글꼴 누락·문구 넘침·컴파일 실패 시 이전 PDF를 보존한다. Typst의 자동 글꼴 대체는 꺼져 있다. 표지 쪽수의 DAUL-EQN2 숫자·범위 기호만 사용자 승인에 따라 원본 HWP에 저장된 한컴바탕 대체 설정을 사용한다.

## 자유롭게 바꾸는 문구

기존 `year`, `exam`, `period`, `area`, `subject`, `pages`를 그대로 읽는다. `title`은 본문 파일 이름이고, 표지의 큰 시험 제목은 `cover_title`로 따로 지정한다.

```text
cover_template: korean
cover_title: 직접 지정한 시험 제목
cover_area: 원하는 영역명
cover_badge:
handwriting: 직접 지정한 필적 문구
issuer: 직접 지정한 발행 표시
```

`cover_template`은 `korean` 또는 `math`다. 생략하면 영역이 수학일 때 수학 표지, 나머지는 국어 표지를 사용한다. 제목·영역은 임의 문자열이며 선택한 표지와 같은 과목명으로 고정하지 않는다. 필적 문구 기본값은 `필적 확인란 문구`, 발행 표시는 `issuer` 또는 `exam`이다. 빈 `cover_badge`는 문형 사각형까지 제거한다.

기본 목차는 MD의 과목 하나와 `1~pages 쪽`을 표시하고, 사용하지 않는 선택과목·쪽수·점선을 비운다. 안내는 특정 선택지 수나 2/3점 배점을 강제하지 않는다. 원본 상자의 크기와 위치는 유지하므로 단일 과목은 아래 목차 상자에 여백이 남는다.

원본 문단의 다른 문구도 `cover_p번호: 내용`으로 바꿀 수 있다. 이 설정이 기본 치환보다 우선한다. 빈 값은 해당 문구를 지우며 `\n`은 줄바꿈이다. 엔진의 `source-layout/cover-korean-fields.json`, `cover-math-fields.json`에서 전체 번호를 확인한다.

| 항목 | 국어 | 수학 |
|---|---|---|
| 교시 / 제목 / 영역 / 문형 | 1 / 2 / 5 / 6 | 1 / 2 / 5 / 6 |
| 필적 / 답안 작성 안내 | 18 / 20 | 18 / 20 |
| 배점 안내 | 22 | 24 (22는 답안 방식 안내) |
| 목차 안내 / 첫 과목 / 첫 쪽수 | 25 / 27 / 29 | 29 / 31 / 33 |
| 선택과목 제목 | 31 | 35 |
| 선택과목 이름·점선·쪽수 | 35·36·37, 39·40·41 | 39·40·41, 43·44·45, 47·48·49 |
| 경고 / 발행 표시 | 44 / 47 | 52 / 53 |

문구가 원본 문단의 높이를 넘으면 실패한다. 자동 축소하거나 글을 지워서 맞추지 않는다. 문구를 늘릴 때는 최종 PDF에서 폭과 줄바꿈을 확인한다.

## 합본 연결

`tools/build_final.py`는 같은 `build_cover.build()`를 호출하므로 이 표지를 자동으로 사용한다. `examkit build`도 Typst 경로다. `pages: auto`는 전체 생성 명령이 실제 본문 쪽수를 표지에 전달한다. 표지만 단독 생성할 때는 숫자 쪽수를 지정한다. 기존 본문 PDF를 재사용할 때만 `--reuse`를 사용하며 원문과 일치하는지 먼저 확인한다.

표지는 원본 크기 771.02×1116pt로 만든다. `assemble()`은 이를 본문 용지에 종횡비를 유지해 가운데 배치하고 본문 페이지를 그대로 삽입한다. 본문 쪽수는 MD의 `pages`와 검사하며 책갈피는 각 교시 표지를 가리킨다. `_build/`에는 표지 없는 본문, `_covers/`에는 별도 표지를 둔다. 이미 표지가 붙은 본문에 다시 붙이지 않는다.

## 검증

`python -m unittest discover -s tests -v`. 환경변수 두 개가 있으면 실제 Typst로 국어·수학 표지를 출력하고 임의 제목·4점 안내·문형 제거를 확인한다. 합본 전후 본문 텍스트와 렌더링이 같은지, 너무 긴 제목 때문에 실패했을 때 이전 PDF가 보존되는지도 검사한다. 환경변수가 없으면 실제 출력 통합 검사는 건너뛰고 나머지 검사를 실행한다.

원본 표지와의 픽셀 단위 완전 동일성 및 실제 인쇄는 검증 완료로 주장하지 않는다.
