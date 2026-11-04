# 저장소에 포함된 조판 엔진

`examkit/_typst_engine.py`가 이 폴더의 Python 조판 코드와 Typst 출력 코드를 사용한다. 정상 빌드에는 원본 HWP나 별도의 이전 작업 폴더가 필요하지 않다. `EXAMKIT_TYPST_ROOT`를 생략하면 이 폴더를 선택한다.

| 경로 | 역할 |
|---|---|
| `scripts/compose.py`, `flow.py` | 원본 문단·글자·표 서식으로 내용 배치와 쪽 나눔 |
| `scripts/extract_headers.py`, `extract_body_fixture.py`, `cover.py` | 양식 구조·문단 기록·머리글·표지 처리 |
| `exam.typ`, `original-header.typ` | 글자·선·그림 명령을 Typst PDF로 출력 |
| `templates/*.xml`, `source-layout/` | 다섯 과목·두 표지의 서식 및 줄 위치·선택과목·머리말/꼬리말 데이터 |
| `fonts-manifest.json` | 필요한 원본 글꼴 144개의 파일명·크기·SHA-256 |

## 설치

저장소 루트에서 다음을 실행한다. Python 의존성과 Typst 실행 파일은 별도로 설치한다.

```powershell
python -m pip install -r requirements.txt
python tools/import_typst_fonts.py 'D:/보유한/글꼴묶음'
python tools/import_typst_fonts.py
python -m examkit build docs/examples/migration-compat.md -o output/demo
```

가져오기 경로에는 글꼴 폴더 자체 또는 전달용 묶음의 루트를 지정한다. 정확한 파일 해시가 맞아야 하며, 시스템에 설치된 같은 이름의 다른 글꼴을 자동 선택하지 않는다. 글꼴은 공개 재배포 허가가 확인되지 않아 커밋에서 제외한다. 글꼴 묶음을 보유하지 않았다면 위 설정을 완료할 수 없다. Typst는 PATH 또는 `TYPST_EXE`로 지정한다.

## 양식 데이터의 범위

사용자가 제공한 HWP 양식에서 추출한 글자·문단·테두리·표·쪽 구조를 보존한다. 기출 문항 본문·수식 내용·문항 삽화·작성자 주석·로컬 경로는 배포 데이터에서 제거했다. 국어·영어 영역명의 원본 이미지는 고정 머리글 자산으로 포함한다. 한글 원본 문항을 다시 출력하는 예제 캐시는 포함하지 않으며 새 Markdown 입력을 조판한다.

`tools/export_runtime_templates.py`는 원래의 로컬 추출 작업 폴더에서 이 구조를 다시 만드는 유지보수 도구다. 문자 내용을 지워도 문단과 표의 인덱스는 유지하고, 문단과 줄 기록의 연결을 `paragraph_records`로 저장한다. 원본 입력의 해시는 `template-provenance.json`에 있다. 일반 사용자는 이 추출 도구를 실행할 필요가 없다.

원본 글꼴 없이 실행되는 통합 검사는 제공하지 않는다. 글꼴을 준비한 뒤 `EXAMKIT_TYPST_ROOT`를 이 폴더로 지정하면 기존 본문·표지 통합 테스트가 활성화된다. 렌더링의 100% 동일성 및 아직 지원하지 않는 입력은 [지원 범위](../docs/typst-migration.md)를 참고한다.
