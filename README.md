# 안내 사이트

`index.html`은 claude.ai 아티팩트로 발행한 안내·다운로드 페이지의 원본이다(https://claude.ai/artifact/VKKBLRCAzkfVm63eeiUksa).

- `papers/`: 다운로드 PDF(`ishs/pdf/`의 합본과 교시별 파일을 영문 이름으로 복사)
- `img/body1~4.jpg`: 교시별 첫 문제 쪽 썸네일, `img/team.png`: 메인의 1번 예시 문항 캡처
- `source/demo-question.md`: 그 예시 문항 원문. `python -m examkit build site/source/demo-question.md -o out`으로 다시 만들고 문항 부분을 잘라 `img/team.png`로 쓴다(⑤는 검은 동그라미로 칠함).
