import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from lxml import etree
from tools.import_typst_fonts import import_fonts

ROOT=Path(__file__).resolve().parents[1]


class RuntimeDistributionTests(unittest.TestCase):
    def test_exact_local_fonts_and_failed_import_preserves_existing(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);runtime=root/'runtime';source=root/'source'
            (runtime/'fonts').mkdir(parents=True);source.mkdir()
            data=b'fixture font';sha=hashlib.sha256(data).hexdigest()
            (runtime/'fonts-manifest.json').write_text(json.dumps({'font.ttf':{'sha256':sha}}))
            (runtime/'fonts/font.ttf').write_bytes(b'previous')
            (source/'font.ttf').write_bytes(b'wrong version')
            with self.assertRaisesRegex(ValueError,'불일치'):import_fonts(source,runtime=runtime)
            self.assertEqual((runtime/'fonts/font.ttf').read_bytes(),b'previous')
            (source/'renamed.ttf').write_bytes(data)
            self.assertEqual(import_fonts(source,runtime=runtime),(1,1))
            self.assertEqual(import_fonts(runtime=runtime),(0,1))

    def test_templates_and_records_are_self_contained(self):
        for subject in ('korean','english','math','social','science','cover-korean','cover-math'):
            with self.subTest(subject=subject):
                tree=etree.parse(str(ROOT/f'runtime/templates/{subject}.xml'))
                self.assertFalse(tree.findall('.//DOCSUMMARY'))
                self.assertFalse(tree.findall('.//SHAPECOMMENT'))
                self.assertFalse(tree.findall('.//SCRIPTCODE'))
                self.assertEqual(len(tree.findall('.//BINDATA')),1 if subject in ('korean','english') else 0)
                data=json.loads((ROOT/f'runtime/source-layout/{subject}.json').read_text(encoding='utf8'))
                self.assertEqual(set(data),{'line_segments','paragraph_records'})
                paragraphs=list(tree.getroot().iter('P'))
                for index,record in data['paragraph_records'].items():
                    self.assertLess(int(index),len(paragraphs))
                    self.assertIn('lines',record)
                    if subject.startswith('cover-'):continue
                    units=record.get('text_utf16_units',[]);i=0
                    while i<len(units):
                        if units[i] in (1,2,3,9,11,12,14,15,16,17,18,21,22,23):i+=8
                        else:self.assertEqual(units[i],0);i+=1


if __name__=='__main__':unittest.main()
