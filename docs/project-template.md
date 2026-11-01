# 새 모의고사 프로젝트 시작하기

어떤 주제든 이 순서로 시작한다. 사용자가 "○○ 모의고사 만들어 줘" 한 줄만 주어도 아래를 구체화하고 [실행 조건](agent-workflow.md)을 충족하면 완성까지 진행한다. 특정 프로젝트의 완성 예시는 별도 브랜치(인곽: `ishs`)에 있으며, 그 브랜치의 규칙을 다른 주제에 가져오지 않는다.

## 1. 프로젝트 문서 한 장 (`projects/<이름>/PROJECT.md` 또는 사용자가 정한 위치)

아래 항목을 채운다. 모르면 기본값을 쓴다.

| 항목 | 기본값 | 적을 것 |
|---|---|---|
| 대상 | 일반 | 누가 푸는가, 어느 수준의 상식을 전제로 하는가 |
| 소재 범위 | 사용자가 준 주제 | 무엇을 묻고 무엇을 묻지 않는가, 사실 확인에 쓸 자료(URL·파일) |
| 교시·과목 | 1교시 | `area`(영역)·`subject`(과목) 이름, 교시 수 |
| 문항 수·배점 | 20문항, 3점 10개, 2점 10개 | 다르면 `examkit check`가 보는 `count`·`three`도 바꾼다 |
| 정답 분포 | ①~⑤ 각 4개 | |
| 쪽수 | 5문항↓ 2쪽, 6~10문항 4쪽, 20문항 4쪽(넘치면 6쪽) | MD 머리 `pages:`. 빌드 결과 쪽수와 같아야 표지 합본이 된다 |
| 표지 | 붙임 | 필적 확인 문구 `handwriting:`, 발행 표시 `issuer:` |
| 금지 | 실명·개인정보 | 주제별 추가 금지 사항 |
| 그림 | 글자 없는 흑백 틀 + 문서에서 글 얹기 | 작업 AI가 직접 그리는지, 외부에 맡기는지 |

## 2. 문항 파일 머리

```markdown
---
title: 1교시 일반 상식
year: 2026학년도
exam: 상식능력시험
period: 제1교시
area: 상식탐구
subject: 일반 상식
pages: 4
count: 20
three: 10
handwriting: 아는 만큼 보인다
issuer: 상식 모의고사 출제팀
---
```

`title`은 출력 파일 이름, `period`·`area`·`subject`는 머리글과 표지에, `handwriting`·`issuer`는 표지에 들어간다. 문법은 README, 작성 규칙은 [출제 노하우](authoring-style.md).

## 3. 작업 순서

1. 문항 20개를 `content/<N>교시.md`에 쓴다. 계산·퍼즐은 코드로 검산한다.
2. 그림이 필요하면 글자 없는 틀을 만들어(직접 생성 또는 [요청서](illustration-request.md)) `assets/illust/`에 두고, MD에서 `::: figure file`로 넣고 글을 얹는다([배치 노트](hwpx-layout-notes.md)).
3. 해설을 `content/<N>교시_해설.md`에 먼저 쓴다. 문항과 번호·정답을 맞춘다([해설 양식](explanation-format.md)).
4. `python tools/build_final.py out content/<N>교시.md` 한 줄이면 검사→문제지 빌드→표지→정답표→해설→교시별 파일까지 끝난다(AI 실행 환경에서도 승인 한 번). 표지 포함 문제지·정답표·해설 PDF가 합본으로, 그리고 `out/교시별/`에 교시마다 따로 나온다. 배포할 때는 전체 합본과 교시별 파일을 모두 제공한다.
5. `tools/qpos.py`·`colfill.py`·`widows.py`·`qcrop.py`로 배치와 외톨이 줄을 보고, 전체 쪽을 렌더링해 확인한다([재현 절차](reproduction-guide.md) 6절).

## 4. 환경

- PDF까지 만들려면 Windows + 한컴오피스 한글(COM)이 필요하다. 없으면 `--no-convert`로 HWPX까지만 나오고, 정답표·해설 PDF는 한글 없이도 된다.
- 글꼴·보안 모듈 등 환경 확인은 [재현 절차](reproduction-guide.md) 2절.
