"""HWPX → HWP / PDF 변환. Windows + 한컴오피스(한글) COM 자동화가 필요하다.

숨은 한글 창이 대화상자에서 멈추면 COM 호출이 영원히 돌아오지 않으므로,
실제 변환은 하위 프로세스에서 하고 제한 시간이 지나면 오류로 끝낸다.
"""
import json, os, subprocess, sys, tempfile
from contextlib import ExitStack

TIMEOUT = 240  # 초. 4쪽 시험지는 보통 1분 안에 끝난다.


def _convert_inproc(hwpx_path, hwp_out=None, pdf_out=None):
    import win32com.client as w

    h = w.gencache.EnsureDispatch("HWPFrame.HwpObject")
    with ExitStack() as staging:
        pending = []
        try:
            # 보안 모듈이 없으면 숨은 창에서 접근 허용 대화상자가 변환을 막는다.
            if not h.RegisterModule("FilePathCheckDLL", "FilePathCheckerModule"):
                raise RuntimeError("한글 보안 모듈 등록 실패: HKCU\\Software\\HNC\\HwpAutomation\\Modules 에 "
                                   "FilePathCheckerModule = <FilePathCheckerModuleExample.dll 경로> 값이 있는지 확인하세요.")
            h.XHwpWindows.Item(0).Visible = False
            try:
                h.SetMessageBoxMode(0x2FFF1)
            except Exception:
                pass
            if not h.Open(os.path.abspath(hwpx_path), "HWPX", "forceopen:true"):
                raise RuntimeError("한글에서 열지 못함: %s" % hwpx_path)
            results = {"pages": h.PageCount}
            for path, fmt in ((hwp_out, "HWP"), (pdf_out, "PDF")):
                if not path:
                    continue
                path = os.path.abspath(path)
                directory = staging.enter_context(tempfile.TemporaryDirectory(prefix=".examkit-", dir=os.path.dirname(path)))
                temporary = os.path.join(directory, os.path.basename(path))
                if not h.SaveAs(temporary, fmt, "") or not os.path.isfile(temporary) or os.path.getsize(temporary) == 0:
                    raise RuntimeError("한글 %s 저장 실패: %s" % (fmt, path))
                pending.append((temporary, path))
                results[fmt.lower()] = True
        finally:
            # 저장 실패 때도 문서를 닫아 임시 파일의 잠금을 해제한다.
            h.Quit()
        # 모든 형식의 저장이 성공한 뒤에만 기존 결과를 교체한다.
        for temporary, path in pending:
            os.replace(temporary, path)
        return results


def _lock(root):
    """여러 작업이 동시에 한글을 띄우지 않도록 output/.convert.lock 을 잡는다(최대 10분 대기)."""
    import msvcrt, time
    os.makedirs(os.path.join(root, "output"), exist_ok=True)
    f = open(os.path.join(root, "output", ".convert.lock"), "a+")
    for _ in range(600):
        try:
            f.seek(0)
            msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
            return f
        except OSError:
            time.sleep(1)
    f.close()
    raise RuntimeError("다른 한글 변환이 10분 넘게 끝나지 않았습니다.")


def convert(hwpx_path, hwp_out=None, pdf_out=None, timeout=TIMEOUT):
    import msvcrt
    args = [os.path.abspath(p) if p else "" for p in (hwpx_path, hwp_out, pdf_out)]
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    lock = _lock(root)
    try:
        r = subprocess.run([sys.executable, "-m", "examkit.convert", *args], cwd=root,
                           capture_output=True, text=True, encoding="utf-8", timeout=timeout)
    except subprocess.TimeoutExpired:
        raise RuntimeError("한글 변환이 %d초 안에 끝나지 않았습니다: %s\n"
                           "작업 관리자에서 남아 있는 '한글(Hwp.exe)' 프로세스를 닫고 다시 실행하세요." % (timeout, hwpx_path))
    finally:
        try:
            lock.seek(0)
            msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
        except OSError:
            pass
        lock.close()
    if r.returncode != 0:
        raise RuntimeError("한글 변환 실패: %s\n%s" % (hwpx_path, r.stderr.strip()[-800:]))
    result = json.loads(r.stdout.strip().splitlines()[-1])
    if pdf_out and result.get("pdf"):
        _fix_pdf_size(hwpx_path, pdf_out)
    return result

def _fix_pdf_size(hwpx_path, pdf_path):
    """한글의 인쇄 용지 설정(예: B4 '용지에 맞춤')이 PDF 저장에 끼어들면 쪽 전체가 줄어든다.
    문서 용지(HWPX pagePr) 크기와 다르면 왼쪽 위 기준으로 다시 키워 원래 용지 크기로 되돌린다."""
    import re, zipfile
    import pymupdf as fitz
    with zipfile.ZipFile(hwpx_path) as z:
        m = re.search(rb'<hp:pagePr[^>]*?width="(\d+)" height="(\d+)"', z.read("Contents/section0.xml"))
    if not m:
        return
    w, h = int(m.group(1)) / 100, int(m.group(2)) / 100      # HWPUNIT → pt
    src = fitz.open(pdf_path)
    r = src[0].rect
    if abs(r.width - w) < 1 and abs(r.height - h) < 1:
        src.close()
        return
    s = min(r.width / w, r.height / h)                         # 한글이 줄인 배율
    out = fitz.open()
    for i in range(src.page_count):
        page = out.new_page(width=w, height=h)
        page.show_pdf_page(page.rect, src, i, clip=fitz.Rect(0, 0, w * s, h * s))
    src.close()
    tmp = pdf_path + ".tmp"
    out.save(tmp, garbage=3, deflate=True)
    out.close()
    os.replace(tmp, pdf_path)



if __name__ == "__main__":
    a = (sys.argv[1:] + ["", "", ""])[:3]
    print(json.dumps(_convert_inproc(a[0], a[1] or None, a[2] or None)))
