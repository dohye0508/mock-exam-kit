"""Read an editable Typst document through its labelled metadata."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import pymupdf

ROOT=Path(__file__).resolve().parents[1]


def typst_executable():
    executable=os.environ.get('TYPST_EXE') or shutil.which('typst') or str(ROOT/'bin'/('typst.exe' if os.name=='nt' else 'typst'))
    if not Path(executable).is_file():raise FileNotFoundError('Typst를 PATH에 설치하거나 TYPST_EXE를 지정하세요.')
    return executable



def read_document(path):
    path=Path(path)
    if path.suffix=='.json':document=json.loads(path.read_text(encoding='utf-8'))
    elif path.suffix=='.typ':
        result=subprocess.run([typst_executable(),'eval','query(<exam-source>).map(it => it.value)','--in',str(path),
            '--root',str(ROOT),'--font-path',str(ROOT/'fonts'),'--ignore-system-fonts','--ignore-embedded-fonts',
            '--diagnostic-format','short'],cwd=ROOT,capture_output=True,text=True,encoding='utf-8')
        if result.returncode or result.stderr.strip():raise ValueError(f'{path.name}: invalid Typst source:\n{result.stderr}')
        documents=json.loads(result.stdout)
        if not isinstance(documents,list) or len(documents)!=1 or not isinstance(documents[0],dict):
            raise ValueError('Declare exactly one #exam-source document')
        document=documents[0]
    else:raise ValueError('Use a .typ or .json exam source')
    if not isinstance(document,dict):raise ValueError('An exam source must be a document object')
    if document.get('subject') not in ('korean','english','math','social','science'):
        raise ValueError('Unknown subject in Typst source')
    if 'sections' in document:
        if document.get('flow') is not True or any(k in document for k in ('blocks','pages','elective')):
            raise ValueError('Automatic sections need flow: true and their own blocks/elective settings')
        pages=document['sections']
        if isinstance(pages,list) and any(isinstance(p,dict) and any(k in p for k in ('subject','flow','sections','pages')) for p in pages):
            raise ValueError('Sections share the document subject and automatic flow')
    else:pages=document.get('pages',[document])
    if not isinstance(pages,list) or not pages or any(not isinstance(p,dict) or not isinstance(p.get('blocks'),list) for p in pages):
        raise ValueError('Each page needs a blocks array')
    return document


def authoring_documents():
    documents={}
    for subject in ('korean','english','math','social','science'):
        path=ROOT/f'authoring/{subject}.typ'
        if not path.exists():path=path.with_suffix('.json')
        document=read_document(path)
        if document['subject']!=subject:raise ValueError(f'{path.name}: subject does not match the filename')
        documents[subject]=document
    return documents


def render_pdf(source,destination,pages):
    destination.parent.mkdir(exist_ok=True,parents=True)
    result=subprocess.run([typst_executable(),'compile',str(source),str(destination),'--root',str(ROOT),
        '--font-path',str(ROOT/'fonts'),'--ignore-system-fonts','--ignore-embedded-fonts',
        '--diagnostic-format','short'],cwd=ROOT,capture_output=True,text=True,encoding='utf-8')
    if result.returncode or result.stderr.strip():
        raise RuntimeError(f'{source.name}: compilation failed or warned:\n{result.stderr}')
    with pymupdf.open(destination) as pdf:
        assert len(pdf)==pages,(destination,len(pdf),pages)
        font_names=sorted({f[3] for p in pdf for f in p.get_fonts()})
        assert font_names,destination
        assert all(any(allowed in name for allowed in ('OriginalHFT','TimesNewRoman','HCRBatang','Gulim','Haansoft','Arial-Black','Batang','H2gtrM')) for name in font_names),font_names
    return dict(file=str(destination.relative_to(ROOT)),pages=pages,font_names=font_names,warnings=0)
