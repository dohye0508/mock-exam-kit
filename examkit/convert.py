"""HWPX → HWP / PDF 변환. Windows + 한컴오피스(한글) COM 자동화가 필요하다."""
import os


def convert(hwpx_path, hwp_out=None, pdf_out=None):
    import win32com.client as w

    h = w.gencache.EnsureDispatch("HWPFrame.HwpObject")
    try:
        h.RegisterModule("FilePathCheckDLL", "FilePathCheckerModule")
    except Exception:
        pass
    h.XHwpWindows.Item(0).Visible = False
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


if __name__ == "__main__":
    import sys
    print(convert(*sys.argv[1:4]))
