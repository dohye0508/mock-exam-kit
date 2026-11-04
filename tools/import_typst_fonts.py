"""Import the exact local font pack; never download, replace, or publish fonts."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

RUNTIME=Path(__file__).resolve().parents[1]/'runtime'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def import_fonts(source=None,*,runtime=RUNTIME):
    manifest=json.loads((runtime/'fonts-manifest.json').read_text(encoding='utf8'))
    destination=runtime/'fonts';pending=[];missing=[]
    candidates={}
    if source is not None:
        source=Path(source).resolve()
        folders=[source,source/'fonts',source/'runtime/fonts']
        for folder in folders:
            if folder.is_dir():
                for p in folder.iterdir():
                    if p.is_file() and p.suffix.lower() in ('.ttf','.otf'):candidates.setdefault(digest(p),p)
    for name,record in manifest.items():
        target=destination/name
        if target.is_file() and digest(target)==record['sha256']:continue
        if record['sha256'] in candidates:pending.append((candidates[record['sha256']],target))
        else:missing.append(name)
    if missing:
        raise ValueError(f'원본 글꼴 {len(missing)}개 누락 또는 버전 불일치: '+', '.join(missing)+
                         '\n보유한 글꼴 묶음의 fonts 폴더를 지정하세요. 다른 글꼴로 대체하지 않습니다.')
    destination.mkdir(parents=True,exist_ok=True)
    for original,target in pending:
        temporary=target.with_suffix(target.suffix+'.tmp')
        try:
            shutil.copyfile(original,temporary)
            if digest(temporary)!=manifest[target.name]['sha256']:raise ValueError('복사 중 글꼴이 변경됐습니다: '+target.name)
            temporary.replace(target)
        finally:temporary.unlink(missing_ok=True)
    return len(pending),len(manifest)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source',nargs='?',type=Path,help='보유한 fonts 폴더 또는 전달용 묶음의 루트. 생략하면 설치 상태만 검사')
    args=parser.parse_args()
    try:
        copied,total=import_fonts(args.source)
    except (ValueError,FileNotFoundError) as error:parser.exit(1,str(error)+'\n')
    print(f'원본 글꼴 {total}개 SHA-256 확인, {copied}개 가져옴')
