"""그림 요소가 있는 자료 11개: ChatGPT는 글자 없는 틀(테두리·장식·삽화)만 그리고, 빈 판에 Claude가 글·표를 얹는다."""
import os, shutil
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "illust")
OUT = os.path.join(ROOT, "handoff2")
FONT = r"C:\Windows\Fonts\malgun.ttf"

COMMON = """## 빈 판 규칙 (가장 중요)
- **그림 안에 글자·숫자·기호를 하나도 넣지 않는다.** 제목, 표 내용, 말, 날짜, 아이콘 속 글자까지 모두 Claude가 문서에서 직접 얹는다.
- `layout.png`의 **흰 칸(빈 판)**은 순백색으로 비워 둔다. 선, 줄무늬, 격자, 그림자, 질감도 넣지 않는다.
- 빈 판의 위치와 크기는 `layout.png`와 최대한 같게 한다. 테두리·장식·삽화는 빈 판 **바깥**에만 그린다.
- 빈 판 모서리는 반듯하게. 기울이거나 휘게(원근) 그리지 않는다. 정면에서 본 모습.

## 인쇄 조건
- 평가원 시험지의 자료 그림처럼 **흑백(회색조)**, 흰 배경, 선명한 윤곽, 회색 1~2단계.
- 사람·사물 그림은 기존 삽화(`style_1.png`, `style_2.png`)와 같은 그림체.

## 금지
- 글자·숫자, 실제 앱·회사 로고와 상표, 실존 인물, 컬러.
"""

# 영역: (x0, y0, x1, y1) 비율, 이름, 종류(panel=빈 판 / art=그림 요소)
ITEMS = [
    dict(id="geo_sign_01", q="1교시(지리) 6번 — 본관 층별 안내판", size=(80, 53), ratio=(1536, 1024),
         what="학교 복도 벽에 붙은 **층별 안내판**을 정면에서 본 모습. 둥근 모서리의 판, 벽 고정 나사 정도의 장식.",
         regions=[((0.08, 0.10, 0.92, 0.90), "빈 판: 층별 표(Claude)", "panel")]),
    dict(id="geo_board_01", q="1교시(지리) 8번 — 공항 출발 안내 전광판", size=(95, 63), ratio=(1536, 1024),
         what="공항 출국장 천장에 매달린 **출발 안내 전광판**의 겉틀(두꺼운 회색 테두리, 위쪽 매달린 지지대, 왼쪽 위 작은 비행기 그림).",
         regions=[((0.15, 0.08, 0.93, 0.18), "빈 판: 제목(Claude)", "panel"),
                  ((0.05, 0.22, 0.95, 0.93), "빈 판: 출발 표(Claude)", "panel"),
                  ((0.04, 0.06, 0.13, 0.19), "비행기 그림", "art")]),
    dict(id="geo_notice_gym_01", q="1교시(지리) 9번 — 체력단련실 이용 안내문", size=(95, 63), ratio=(1536, 1024),
         what="체력단련실 문에 테이프로 붙인 **안내문 종이**. 오른쪽에 탁구 치는 학생 그림(`illust.png`를 그대로 쓰거나 같은 그림체로).",
         regions=[((0.05, 0.06, 0.64, 0.94), "빈 판: 제목·안내 항목(Claude)", "panel"),
                  ((0.67, 0.18, 0.96, 0.82), "탁구 그림", "art")], copy={"illust.png": "geo_pingpong_01.png"}),
    dict(id="geo_notice_interview_01", q="1교시(지리) 11번 — 3차 면접 진행 안내문", size=(90, 60), ratio=(1536, 1024),
         what="체육관 앞 이젤(받침대)에 세운 **안내 보드**. 오른쪽 아래에 의자 줄 그림을 작게.",
         regions=[((0.06, 0.06, 0.78, 0.86), "빈 판: 제목·안내 항목(Claude)", "panel"),
                  ((0.80, 0.55, 0.97, 0.92), "의자 그림", "art")]),
    dict(id="geo_news_yeongjong_01", q="1교시(지리) 12번 — 영종구 출범 신문 기사", size=(95, 63), ratio=(1536, 1024),
         what="가위로 오린 **신문 기사 스크랩**(종이 가장자리, 살짝 그림자). 오른쪽에 섬과 산이 보이는 흑백 사진 칸.",
         regions=[((0.04, 0.05, 0.96, 0.15), "빈 판: 제호·날짜(Claude)", "panel"),
                  ((0.04, 0.17, 0.96, 0.33), "빈 판: 제목·부제(Claude)", "panel"),
                  ((0.04, 0.36, 0.62, 0.95), "빈 판: 본문(Claude)", "panel"),
                  ((0.65, 0.36, 0.96, 0.82), "사진: 섬과 산", "art"),
                  ((0.65, 0.84, 0.96, 0.95), "빈 판: 사진 설명(Claude)", "panel")]),
    dict(id="geo_news_ev_01", q="1교시(지리) 16번 — 전기자동차 교내 신문 기사", size=(95, 63), ratio=(1536, 1024),
         what="**교내 신문 기사 스크랩**. 오른쪽에 동아리가 만든 낡은 소형 전기자동차 사진 칸(번호판·글자 없음).",
         regions=[((0.04, 0.05, 0.96, 0.15), "빈 판: 제호·호수(Claude)", "panel"),
                  ((0.04, 0.17, 0.96, 0.33), "빈 판: 제목·부제(Claude)", "panel"),
                  ((0.04, 0.36, 0.62, 0.95), "빈 판: 본문(Claude)", "panel"),
                  ((0.65, 0.36, 0.96, 0.82), "사진: 전기자동차", "art"),
                  ((0.65, 0.84, 0.96, 0.95), "빈 판: 사진 설명(Claude)", "panel")]),
    dict(id="geo_chat_library_01", q="1교시(지리) 17번 — 메신저 대화", size=(95, 63), ratio=(1536, 1024),
         what="노트북 화면 속 **메신저 앱 창**(특정 앱과 닮지 않게). 창 테두리와 위쪽 제목 줄, 아래 입력 줄만 그린다. 말풍선·프로필은 Claude가 얹는다.",
         regions=[((0.06, 0.08, 0.94, 0.17), "빈 판: 대화방 이름(Claude)", "panel"),
                  ((0.06, 0.19, 0.94, 0.86), "빈 판: 대화 말풍선(Claude)", "panel"),
                  ((0.06, 0.88, 0.94, 0.95), "입력 줄(빈 칸 + 보내기 아이콘)", "art")]),
    dict(id="life_notice_points_01", q="2교시(생활) 4번 — 기숙사 상벌점 기준표", size=(95, 63), ratio=(1536, 1024),
         what="기숙사 게시판(코르크판)에 압정으로 꽂은 **기준표 종이**.",
         regions=[((0.08, 0.07, 0.92, 0.17), "빈 판: 제목(Claude)", "panel"),
                  ((0.08, 0.20, 0.92, 0.58), "빈 판: 점수 표(Claude)", "panel"),
                  ((0.08, 0.61, 0.92, 0.93), "빈 판: 규칙 3개(Claude)", "panel")]),
    dict(id="life_post_bot_01", q="2교시(생활) 7번 — 급식 봇 게시물", size=(70, 70), ratio=(1024, 1024),
         what="휴대폰 화면 속 **게시물 카드**(인스타그램과 닮지 않게). 동그란 프로필 테두리, 오른쪽 위 점 세 개, 아래 하트·말풍선·종이비행기 아이콘 줄만 그린다.",
         regions=[((0.08, 0.10, 0.22, 0.24), "프로필 원(속은 비움)", "art"),
                  ((0.25, 0.10, 0.85, 0.24), "빈 판: 계정·시각(Claude)", "panel"),
                  ((0.08, 0.28, 0.92, 0.80), "빈 판: 게시물 본문(Claude)", "panel"),
                  ((0.08, 0.83, 0.50, 0.92), "아이콘 줄", "art")]),
    dict(id="life_playlist_01", q="2교시(생활) 13번 — 기상송 재생 목록", size=(65, 65), ratio=(1024, 1024),
         what="음악 앱의 **재생 목록 화면**(특정 앱과 닮지 않게). 위쪽 음표·스피커 같은 작은 장식, 아래쪽 재생 버튼 줄만 그린다.",
         regions=[((0.08, 0.06, 0.92, 0.16), "빈 판: 목록 제목(Claude)", "panel"),
                  ((0.08, 0.19, 0.92, 0.82), "빈 판: 5곡 목록(Claude)", "panel"),
                  ((0.25, 0.85, 0.75, 0.95), "재생 버튼 줄", "art")]),
    dict(id="life_notice_morning_01", q="2교시(생활) 16번 — 기숙사 아침 일과 안내문", size=(90, 60), ratio=(1536, 1024),
         what="기숙사 복도 벽에 붙은 **안내문 종이**. 오른쪽에 아침에 일어나는 기숙사 방 그림(`illust.png`를 그대로 쓰거나 같은 그림체로, 시계는 숫자 없이).",
         regions=[((0.05, 0.06, 0.62, 0.94), "빈 판: 제목·안내 항목(Claude)", "panel"),
                  ((0.65, 0.12, 0.96, 0.88), "기상 장면 그림", "art")], copy={"illust.png": "life_wakeup_01.png"}),
]


def layout(it, path):
    W, H = it["ratio"]
    im = Image.new("RGB", (W, H), (235, 235, 235))
    d = ImageDraw.Draw(im)
    f = ImageFont.truetype(FONT, 34)
    for (x0, y0, x1, y1), name, kind in it["regions"]:
        r = (int(x0 * W), int(y0 * H), int(x1 * W), int(y1 * H))
        if kind == "panel":
            d.rectangle(r, fill="white", outline=(30, 30, 30), width=4)
        else:
            d.rectangle(r, fill=(185, 185, 185), outline=(90, 90, 90), width=3)
        fs = max(14, min(34, int((r[2] - r[0]) / (len(name) * 1.05))))
        ff = ImageFont.truetype(FONT, fs)
        tw = d.textlength(name, font=ff)
        d.text(((r[0] + r[2]) / 2 - tw / 2, (r[1] + r[3]) / 2 - fs * 0.6), name, fill=(70, 70, 70), font=ff)
    d.text((14, H - 40), "연회색 = 테두리·배경(자유) · 진회색 = 그림 요소 · 흰 칸 = 비워 둘 판(글자 금지)", fill=(90, 90, 90), font=ImageFont.truetype(FONT, 24))
    im.save(path)


if os.path.exists(OUT):
    shutil.rmtree(OUT)
os.makedirs(OUT)
index = ["# 자료 틀 그림 요청 목록 (ChatGPT 담당: 글자 없는 틀만)", "",
         "ChatGPT는 테두리·장식·삽화만 그리고 **흰 빈 판**을 남긴다. 제목·표·대화 등 모든 글자는 Claude가 한글 문서에서 빈 판 위에 얹는다.",
         "완성 파일은 `assets/illust/<id>.png`로 넣는다.", "",
         "| id | 문항 | 최종 크기(mm) | 생성 크기(px) |", "|---|---|---|---|"]
for it in ITEMS:
    d = os.path.join(OUT, it["id"]); os.makedirs(d)
    shutil.copy(os.path.join(ROOT, "geo_class_01.png"), os.path.join(d, "style_1.png"))
    shutil.copy(os.path.join(ROOT, "life_talk_01.png"), os.path.join(d, "style_2.png"))
    for dst, src in it.get("copy", {}).items():
        shutil.copy(os.path.join(ROOT, src), os.path.join(d, dst))
    layout(it, os.path.join(d, "layout.png"))
    w, h = it["size"]; pw, ph = it["ratio"]
    arts = [n for _, n, k in it["regions"] if k == "art"]
    lines = ["# 자료 틀 요청서 — %s" % it["id"], "",
             "- **완성 파일**: `assets/illust/%s.png`" % it["id"],
             "- **들어갈 곳**: %s" % it["q"],
             "- **크기**: 생성 %d×%d px, 문서 삽입 가로 %d mm × 세로 %d mm. 비율이 다르면 실제 픽셀 크기를 알려 주세요(문서에서는 흰 여백을 덧대며 자르지 않음)." % (pw, ph, w, h),
             "", "## 그릴 것", "- " + it["what"]]
    if arts:
        lines.append("- 그림 요소: " + ", ".join(arts) + " (`layout.png`의 진회색 칸 위치)")
    lines += ["", COMMON.rstrip(), "", "## 첨부", "- `layout.png`: 빈 판과 그림 요소의 위치(안내용 글자는 그리지 말 것)",
              "- `style_1.png`, `style_2.png`: 그림체 기준"]
    if it.get("copy"):
        lines.append("- `illust.png`: 이 자료에 넣을 기존 삽화")
    open(os.path.join(d, "request.md"), "w", encoding="utf-8").write("\n".join(lines) + "\n")
    index.append("| %s | %s | %d×%d | %d×%d |" % (it["id"], it["q"], w, h, pw, ph))
open(os.path.join(OUT, "README.md"), "w", encoding="utf-8").write("\n".join(index) + "\n")
print("made", len(ITEMS))
