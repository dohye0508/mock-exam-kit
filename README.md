# 안내 사이트

`index.html`은 claude.ai 아티팩트로 발행한 안내·다운로드 페이지의 원본이다(https://claude.ai/artifact/VKKBLRCAzkfVm63eeiUksa).

- `papers/`: 다운로드 PDF(`ishs/pdf/`의 합본과 교시별 파일을 영문 이름으로 복사)

## 2026년 11월 공개 일정

- 11월 2일: 공개 자료 없음
- 11월 3일: 1교시 원본 문제
- 11월 4일: 2교시 원본 문제
- 11월 5일: 3교시 원본 문제
- 11월 6일: 4교시 원본 문제
- 11월 7일: 1~4교시 합본 문제지와 모든 정답표·정답 및 해설·전체 ZIP

공개 여부는 `index.html`에서 한국 시간(`Asia/Seoul`)을 기준으로 자동 판정한다. 공개 전 항목은 파일을 받지 않고 공개일 안내 팝업만 표시한다.
- `img/body1~4.jpg`: 교시별 첫 문제 쪽 썸네일, `img/team.png`: 메인의 1번 예시 문항 캡처
- `source/demo-question.md`: 그 예시 문항 원문. `python -m examkit build site/source/demo-question.md -o out`으로 다시 만들고 문항 부분을 잘라 `img/team.png`로 쓴다(⑤는 검은 동그라미로 칠함).
