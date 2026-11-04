"""Create a private, relocatable checkout with the existing engine and fonts."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from examkit.typst_runtime import engine_root, executable


def bundle(destination):
    destination=Path(destination).resolve()
    if destination.exists():raise FileExistsError('새 폴더를 지정하세요: '+str(destination))
    engine=engine_root();typst=Path(executable())
    names=subprocess.check_output(['git','ls-files','-z','--cached'],cwd=ROOT).decode('utf8').split('\0')
    files={ROOT/name:Path(name) for name in names if name and (ROOT/name).is_file()}
    patterns=('*.typ','equations.json','fonts-manifest.json','templates/*.xml','scripts/*.py','source-layout/*.json','source-layout/*.txt',
              'output/reference/*-original.hml','fonts/*.otf','fonts/*.ttf','fonts/*.TTF',
              'fonts/*.json','assets/original/*','assets/equations/*.svg','assets/equations/manifest.json')
    for pattern in patterns:
        for source in engine.glob(pattern):
            if source.is_file():files[source]=Path('runtime')/source.relative_to(engine)
    files[typst]=Path('runtime/bin')/typst.name
    records={}
    for source,relative in files.items():
        target=destination/relative;target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(source,target)
        records[relative.as_posix()]=hashlib.sha256(target.read_bytes()).hexdigest()
    # Older engine checkouts ignored editable mathematics headings on page one.
    exam=destination/'runtime/exam.typ'
    text=exam.read_text(encoding='utf8')
    old='subject == "math" and page-no == 1 and elective-profile == none {'
    if old in text:
        text=text.replace(old,old[:-1]+'and active-heading == none {')
        exam.write_text(text,encoding='utf8')
        records['runtime/exam.typ']=hashlib.sha256(exam.read_bytes()).hexdigest()
    manifest=destination/'bundle-manifest.json'
    manifest.write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf8')
    assert all(hashlib.sha256((destination/p).read_bytes()).hexdigest()==h for p,h in records.items())
    print(destination,len(records),'files',flush=True)
    return destination


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('destination',type=Path)
    bundle(parser.parse_args().destination)
