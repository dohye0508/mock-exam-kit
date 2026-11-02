# 대화 기록 없이 처음부터 이어 만드는 절차

이 문서는 README·AGENTS.md의 실행 안내다. **이미 있는 양식과 제작기를 재사용한다.** 과거 대화, 외부 작업 폴더, 다른 AI의 기억을 필수 입력으로 삼지 않는다. 명령은 모두 저장소 루트에서 실행한다. 예시의 날짜·출력 폴더는 작업 회차에 맞게 바꾼다.

## 1. 먼저 작업 범위를 정한다

| 요청 | 주로 고칠 파일 | 그대로 둘 것 |
|---|---|---|
| 문제 내용 수정 | `content/N교시.md` ([출제 노하우](authoring-style.md) 먼저) | 승인된 소재·공유 상식·다른 문항. 정답이 바뀌면 해당 해설도 동기화 |
| 정답·해설 수정 | `content/N교시_해설.md` | 문제 조건·번호·정답을 서식 때문에 임의 변경하지 않음 |
| 표지 문구 수정 | 문항 MD의 메타데이터, 필요한 경우 `tools/build_cover.py` | `templates/covers/*-source.*` 원본 |
| 해설 서식 수정 | `tools/build_key.py`, `docs/explanation-format.md` | 문제·정답. 새 렌더러를 별도로 만들지 않음 |
| 본문 배치 수정 | MD의 그림 크기·`{page}`·`{col}`·`{gap}`; 공통 엔진 오류이면 `examkit/` | 정답에 필요한 단서, 원본 템플릿의 승인된 서식 |
| 삽화 추가/교체 | `assets/illust/<id>.png`, 해당 MD의 `figure file`와 얹는 글 좌표 | 대사·숫자·단서의 정확한 원문 |

다른 시험을 새로 만들면 프로젝트 문서에 대상·과목·문항 수·배점·분포·쪽수·공유 전제·자료 출처를 먼저 적는다. 인곽의 학교 상식과 문항별 과거 피드백은 범용 출제 규칙이 아니다. 현재 CLI 검사와 독립 정답표/표지에는 5지선다·2/3점·20문항 중심의 제약이 남아 있다. 다른 문항 체계는 관련 코드와 검사도 함께 변경해야 한다.

## 2. 파일·환경 확인

```powershell
git status --short
git branch --show-current
git ls-files content templates tools docs
python -c "import sys; print(sys.executable); print(sys.version)"
python -m pip install -r requirements.txt
python -c "import lxml, matplotlib, pymupdf, PIL, win32com.client; print('imports OK')"
```

- Python이 여러 개면 위에서 확인한 실행 파일을 이후 명령에도 동일하게 쓴다. 현재 작업 PC의 경로는 프로젝트 인수인계에만 기록한다.
- HWP/HWPX → PDF에는 Windows + 한컴오피스 한글 + COM + 자동화 보안 모듈이 필요하다. [변환 환경](hwpx-layout-notes.md)의 10절을 따른다. `HKCU\Software\HNC\HwpAutomation\Modules`의 `FilePathCheckerModule`은 **실제로 존재하는 DLL 절대 경로**여야 한다. DLL은 이 저장소에 포함되어 있지 않다.
- 설치·레지스트리 변경이 필요한 경우 현재 사용자의 허용 범위와 실행 환경 정책을 따른다. 기존 등록이 유효하면 다시 설치하지 않는다. 사용자가 열어 둔 한글 문서를 일괄 종료하지 않는다.
- 글꼴: 본문은 템플릿의 `Contents/header.xml`; 표지는 [표지 글꼴표](cover-format.md); 해설은 [해설 글꼴표](explanation-format.md)를 따른다. 해설은 `HBATANG.TTF`, `H2HDRM.TTF`, `H2MJRE.TTF`, `H2GTRE.TTF`, 독립 정답표는 `C:/Windows/Fonts/batang.ttc`를 사용한다. 함초롬바탕은 한컴 바탕의 대체물이 아니다.
- `examkit/materials.py`의 자료 이미지는 Chrome/Edge headless가 필요하다. `pdftoppm`은 PDF 렌더링에 쓴다. 없으면 사용 가능한 렌더러를 확인하고 검증 방법을 기록한다.
- 한글이 없으면 `--no-convert`로 HWPX까지 만들 수 있다. 그 경우 PDF 변환·최종 쪽수·인쇄 배치까지 검증했다고 보고하지 않는다.

## 3. 네 종류의 양식을 혼동하지 않는다

### 문제 본문

`templates/kice-sci/`는 **HWPX를 풀어 둔 디렉터리**다. `Contents/header.xml`에 문자/문단/테두리 정의, `frags/p0.xml`에 첫 문단과 머리글, `Contents/masterpage*.xml`에 바탕쪽이 있다. `examkit/build.py`가 템플릿을 복사한 뒤 머리글 치환과 문항 조립을 한다. `examkit/hwpx.py`의 STYLE/BF 등 ID는 이 템플릿과 한 세트다.

내용은 MD를 수정한다. 생성된 `<title>_build/Contents/section0.xml`을 직접 고쳐 납품하면 다음 빌드에서 사라진다. 공통 서식을 고칠 때만 엔진·템플릿과 배치 문서를 함께 수정한다. 다른 템플릿을 도입할 때는 폴더만 복사하면 끝나는 것이 아니라 서식 ID와 머리글 치환도 맞춰야 한다.

### 교시별 표지

`templates/covers/csat-2017-v2-source.hwpx`가 빌더 입력이다. `.hwp`는 받은 원본, `.pdf`는 비교 원본이다. `tools/build_cover.py`를 사용한다. 성명·수험번호 칸, 안내 상자, 필적 상자, 경고문은 원본 개체를 유지한다. 가형·나형·홀수형·짝수형·단답형 안내를 제거하고, 필적 문구는 **지혜를 모아 지혜를 모아**다. 제목·교시·과목은 MD 메타데이터에서 가져온다.

원본 크기 PDF와 본문 용지에 균일 축소한 합본은 다르다. [표지 양식](cover-format.md)에 실제 용지·글꼴·치환 규칙이 있다. 합본은 표지 1쪽 + 해당 교시 본문을 반복하며, 본문의 쪽수/쪽번호는 표지를 제외한다.

### 정답 및 해설

`tools/build_key.py`가 `2026고1-10월과탐정답해설.pdf`를 실측한 **841×1190pt, 3단 PDF**를 만든다. 원본 PDF는 저장소에 포함되어 있지 않지만 구현·실측표·미리보기는 포함 대상이다. 재빌드에 원본 PDF를 요구하거나 새로 눈대중으로 만들지 않는다. 원본과의 재실측이 필요한 변경이면 실제 원본을 확보한다.

- 원문: `content/N교시_해설.md`, 정답 기준: `content/N교시.md`의 `@answer`.
- 형식: `## 1. [출제의도] …` → 다음 줄 `@answer 3` → 빈 줄 뒤 설명. 각 문항의 번호/정답/본문이 있어야 한다.
- `RIGHT_INSET=5.67pt`로 각 단 오른쪽 여백을 약2mm 늘렸다. 영역과 과목·정답표 사이의 불필요한 62pt 공백은 제거했다. `SUBJECT_BASELINE`, `GRID_TOP`, `GRID_ROW_HEIGHT`, `BODY_AFTER_GRID`가 기준이다.
- 핵심 근거 → 계산/추론 → 결론으로 짧게 쓴다. 주어진 조건을 길게 되풀이하지 않는다. 학교 구성원의 공유 상식은 누락 조건으로 취급하지 않는다.
- [수치와 글꼴](explanation-format.md), [승인 배치 미리보기](explanation-layout-preview.png)를 함께 확인한다.

### 독립 정답표와 검토본

`tools/answer_key.py`는 문항 번호·정답·배점만 담은 **별도의 595×842pt PDF**다. 해설 첫머리의 작은 정답표와 다르다. 현재 20문항용 5행×4묶음이며 더 많은 문항은 코드 확장 없이 쓰지 않는다.

`python -m examkit review`는 정답에 색을 칠한 **검토 전용** PDF다. 맨 앞의 색상 설명 표지는 `review.py`가 그리며, 학생용 HWP 표지와 다르다. `--overlay`도 무색 본문을 한글로 변환한 뒤 색 상자를 얹으므로 **한글 없이 동작하는 기능이 아니다**. `--reuse`는 기존 검토 PDF를 재사용한다. 검토본을 풀이용으로 배포하지 않는다.

## 4. 참고 기출 → 삽화 → 글 배치

1. [시각 자료 가이드](visual-reference-guide.md)에서 형식을 고른다. 사람 대화뿐 아니라 공지·기사·표·메신저·사물·유물·실험 장치 등을 사용한다.
2. 기출·모의고사 문제지는 사용자가 구해 로컬 `assets/reference/`에 둔다(git 제외). 없으면 사용자에게 몇 개 받아 달라고 한다.
3. 참고 자료는 형식·구도를 배우는 용도다. 자료 내용이 출제 조건의 진실성을 보증하지 않는다.
4. 자동 후보 선별은 보조다. 예: `python tools/find_illust.py assets/reference/<폴더> -n 32 -o output/reference-sheet`. 썸네일을 직접 보고 비슷한 그림체 2~3장을 고른다.
5. 새 요청은 [삽화 요청서](illustration-request.md) 양식대로 `assets/illust/handoffN/`에 `PROMPT.md`·`<id>/layout.png`·`<id>/style_k.png`로 쓰고 zip으로 사용자에게 넘긴다. 묶음은 저장소에 올리지 않는다. 인곽의 과거 묶음(handoff5~7)은 `ISHS_Wiki/인곽생활_모의고사/handoffN_그림요청.zip`에 있다.
6. 현재 프로젝트는 API 연결 없이 ChatGPT에서 글자 없는 장면/틀을 생성한다. 파일명은 `assets/illust/<id>.png`. 그래프·지도·조직도처럼 수치·관계가 정답을 좌우하면 코드·편집 가능한 도형으로 만든다. 기존 코드 그림은 `assets/illust/sources/`를 본다.
7. 완성 PNG를 실제로 열고 확인한다. 인물/좌석/상자 수, 책상과 의자의 비율, 서로 바라보는 방향, 포스터 가로세로비 등이 요청과 맞아야 한다. 자동 생성은 같은 요청만으로 픽셀 단위 재현을 보장하지 않으므로 승인된 PNG를 원본 자산으로 보존한다.
8. `DELIVERY.md`에 **최종 그림**의 px 크기·빈 판 좌표·삽입 mm를 기록한다. MD의 `textN`·`bubbleN`·`tableN`·`labelN` 좌표는 **삽입 크기 기준 mm**다. `mm = 원본px / 원본폭px × 삽입폭mm`로 환산한다. `w/h`는 HWPUNIT, `crop`과 `cx`는 px다. 단위를 섞지 않는다.
9. HWPX 글상자·말풍선·표로 정확한 글자를 배치하고 실제 크기로 검토한다. 자세한 문법, 자르기, 가운데 맞춤, 글꼴 ID는 [배치 노트](hwpx-layout-notes.md) 5절을 따른다.

## 5. 검사와 첫 전체 빌드

현재 4교시를 새로 재현하는 명령이다. **처음에는 `--reuse`를 쓰지 않는다.** README의 설명용 코드 블록에 붙인 `# 설명`은 실제 MD 메타데이터에 그대로 복사하지 않는다. 현재 파서는 YAML 전체 문법을 지원하지 않는다.

```powershell
python -m examkit check content/1교시.md content/2교시.md content/3교시.md content/4교시.md
python tools/build_final.py output/release_20261101_v2 content/1교시.md content/2교시.md content/3교시.md content/4교시.md
```

생성물:

```text
output/release_20261101_v2/
  _build/1/ ... _build/4/    표지 없는 각 교시 HWPX/HWP/PDF와 작업 파일
  _covers/                 교시별 편집용 HWPX/HWP/PDF와 원본 크기 표지 합본
  원본 문제.pdf             교시별 표지+본문, 정답 표시 없음
  정답표.pdf                교시별 번호·정답·배점
  정답 및 해설.pdf          3단 해설
```

새 프로젝트는 문항 MD 경로를 명시한다. 인자를 생략하면 현재 저장소의 교시 파일이 선택된다. 현재 `build_final.py`는 파일명 첫 글자를 교시 출력 폴더명으로 사용하므로 `1교시.md`처럼 서로 다른 숫자로 시작하는 파일명을 쓴다. 각 `_build/N/`에 다른 PDF를 섞지 않는다. 현재 `--reuse`는 폴더 안 PDF 존재 여부로 판단하며 입력 해시를 자동 비교하지 않는다.

한 교시의 배치 반복 작업은 `python -m examkit build content/1교시.md -o output/layout_1`로 한다. 해설만 수정했다면 `python tools/build_key.py output/해설_v2.pdf content/1교시.md content/2교시.md content/3교시.md content/4교시.md`로 해설만 재빌드한다. 부모 출력 폴더는 먼저 만든다.

## 6. 통과 기준 — 성공 메시지만 믿지 않는다

1. `check` 결과에 오류가 없어야 한다. 이 검사는 풀이의 참/거짓·유일성을 검증하지 않는다. 현재 분포 검사는 균등 분포에서 ±1을 허용하므로 인곽의 각 정답4개는 별도 집계한다. 계산·퍼즐은 독립 검산한다.
2. 교시별 본문 쪽수가 MD `pages`와 같은지 직접 확인한다. `build`는 쪽수 불일치를 경고만 하고 성공 종료할 수 있다. 표지 1쪽, 합본 총합 `sum(pages)+교시 수`를 확인한다.
3. 새 파일 생성 시각과 PDF 텍스트에서 이번 수정 문구를 확인한다. `--reuse` 또는 변환 실패 뒤 남은 옛 파일을 전달하지 않는다.
4. 전체 PDF를 렌더링한다. 예: `pdftoppm -r 120 -png "output/release_20261101_v2/원본 문제.pdf" output/qa/page` (먼저 `New-Item -ItemType Directory -Force output/qa`로 출력 폴더를 만든다). 바뀐 문항은 `python tools/qcrop.py <본문.pdf> <이미지폴더> 130 4 7 9`처럼 확대 확인한다.
5. `tools/qpos.py <본문.pdf>`, `colfill.py <본문.pdf>`, `widows.py <본문.pdf>`로 문항 시작·단 여백·외톨이 줄을 점검한다. 이 도구에는 **표지가 없는 교시별 본문 PDF**를 넣는다.
6. 마지막 쪽 오른쪽 '확인 사항' 상자, 표/수식/아래첨자, 말풍선 꼬리/화자, 줄바꿈을 확인한다. `balance.py --apply`는 MD를 수정하고 기존 gap에 더하므로 무조건 반복 실행하지 않는다.
7. 정답·해설 80개를 문항 MD와 대조한다. 해당 프로젝트의 문항 수가 다르면 그 수로 검사한다. 해설의 영역–과목–표 사이 공백과 각 단 오른쪽 여백을 유지한다.
8. 표지 내용 검사와 육안 비교를 한다. 표지만 붙인 작업이면 기존 본문 모든 쪽의 텍스트/렌더링이 그대로인지 비교한다. 글꼴·용지 크기가 다른데 화면상 비슷하다는 이유로 동일하다고 말하지 않는다.
9. 검증을 마친 새 결과만 `ishs/pdf/` 등 프로젝트 배포 위치에 복사한다. 다른 작업자가 파일을 바꿨다면 덮어쓰기 전에 변경을 확인한다. 실제 인쇄하지 않았으면 화면/렌더링 확인까지만 보고한다.

## 7. 다음 세션에 남길 기록

프로젝트 인수인계에 날짜, 브랜치/커밋, 변경 파일, 실행 명령과 환경, 결과 경로/쪽수/검증, 미완료·부재 자료, 커밋·원격 반영 여부를 적는다. 양식 규칙이 바뀌면 구현과 서식 문서·README/AGENTS의 안내를 함께 갱신한다.

**로컬 새 세션과 다른 PC의 새 clone은 다르다.** 문서·코드·템플릿·승인 PNG·필요 원문이 커밋/푸시되어야 다른 PC가 같은 상태를 받는다. `.gitignore` 예외만 추가했다고 원격에 저장된 것은 아니다. 사용자가 요청하지 않은 커밋·푸시를 문서화 작업의 일부로 자동 수행하지 않는다.
