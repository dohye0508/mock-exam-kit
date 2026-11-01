"""HWPX → HWP / PDF 변환. Windows + 한컴오피스(한글) COM 자동화가 필요하다.

숨은 한글 창이 대화상자에서 멈추면 COM 호출이 영원히 돌아오지 않으므로,
실제 변환은 하위 프로세스에서 하고 제한 시간이 지나면 오류로 끝낸다.
"""
import json, os, subprocess, sys

TIMEOUT = 240  # 초. 4쪽 시험지는 보통 1분 안에 끝난다.


def _convert_inproc(hwpx_path, hwp_out=None, pdf_out=None):
    import win32com.client as w

    h = w.gencache.EnsureDispatch("HWPFrame.HwpObject")
    # 보안 모듈이 없으면 파일마다 '접근 허용' 창이 뜨고, 숨은 창에서는 그대로 멈춘다.
    # HKCU\Software\HNC\HwpAutomation\Modules 의 FilePathCheckerModule 값(DLL 경로)이 있어야 True가 된다.
    if not h.RegisterModule("FilePathCheckDLL", "FilePathCheckerModule"):
        h.Quit()
        raise RuntimeError("한글 보안 모듈 등록 실패: HKCU\\Software\\HNC\\HwpAutomation\\Modules 에 "
                           "FilePathCheckerModule = <FilePathCheckerModuleExample.dll 경로> 값이 있는지 확인하세요.")
    h.XHwpWindows.Item(0).Visible = False
    try:
        # 숨은 창에서 뜨는 확인 대화상자에 자동으로 답해 변환이 멈추지 않게 한다
        h.SetMessageBoxMode(0x2FFF1)
    except Exception:
        pass
    if not h.Open(os.path.abspath(hwpx_path), "HWPX", "forceopen:true"):
        raise RuntimeError("한글에서 열지 못함: %s" % hwpx_path)
    pages = h.PageCount
    results = {"pages": pages}
    for path, fmt in ((hwp_out, "HWP"), (pdf_out, "PDF")):
        if path:
            path = os.path.abspath(path)
            if os.path.exists(path):
                os.remove(path)
            results[fmt.lower()] = h.SaveAs(path, fmt, "")
    h.Clear(1)
    h.Quit()
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
    return json.loads(r.stdout.strip().splitlines()[-1])


if __name__ == "__main__":
    a = (sys.argv[1:] + ["", "", ""])[:3]
    print(json.dumps(_convert_inproc(a[0], a[1] or None, a[2] or None)))
