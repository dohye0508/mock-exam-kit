"""Render the supplied HWP cover records through the existing Typst engine."""
import argparse
from copy import deepcopy
import json
from pathlib import Path
import subprocess

from lxml import etree as E

from compose import Composer
from extract_body_fixture import Body, record_text
from extract_headers import Header, ROOT
from typst_source import render_pdf, typst_executable


class Cover(Body):
    def __init__(self, variant, edits=None):
        if variant not in ('korean', 'math'):
            raise ValueError('Cover variant must be korean or math')
        Header.__init__(self, 'cover-' + variant)
        self.variant = variant
        # Reuse table layout; its source argument carries the cover's own styles.
        self.subject = 'social'
        paragraphs = list(self.root.find('./BODY/SECTION').iter('P'))
        assert len(paragraphs) == len(self.raw)
        self.records = dict(zip(paragraphs, self.raw))
        self.ids = {p: str(i) for i, p in enumerate(paragraphs)}
        # User approved the HWP's saved substitute only for cover page ranges.
        ranges = {'29', '37', '41'} if variant == 'korean' else {'33', '41', '45', '49'}
        latin = self.root.find('.//FONTFACE[@Lang="Latin"]')
        self.range_shapes = set()
        for p in paragraphs:
            for run in p.findall('TEXT'):
                shape = self.root.find(f'.//CHARSHAPE[@Id="{run.get("CharShape")}"]')
                font = latin.find(f'FONT[@Id="{shape.find("FONTID").get("Latin")}"]')
                if font.get('Name') == 'DAUL-EQN2':
                    assert self.ids[p] in ranges, 'DAUL-EQN2 substitution is approved only for page ranges'
                    assert font.find('SUBSTFONT').get('Name') == '한컴바탕'
                    self.range_shapes.add(shape.get('Id'))
        self.range_font = str(max(int(f.get('Id')) for f in latin) + 1)
        E.SubElement(latin, 'FONT', Id=self.range_font, Name='한컴바탕', Type='ttf')
        self.edits = edits or {}
        assert set(self.edits) <= set(self.ids.values()), 'Unknown cover paragraph ID'
        self.skip = set()
        self.images = {}; self.numbers = {}; self.fragments = {}; self.fragment_of = {}
        self.paragraph_count = 0
        self.equations = {}; self.equation_cache = {}
        # Hancom expands text boxes around flow-with-text tables before inline placement.
        for rectangle in self.root.findall('.//RECTANGLE'):
            size = rectangle.find('./SHAPEOBJECT/SIZE')
            draw = rectangle.find('./DRAWINGOBJECT/DRAWTEXT')
            if size is None or draw is None:
                continue
            margin = draw.find('TEXTMARGIN')
            bottom = 0
            for p in draw.findall('./PARALIST/P'):
                for table in p.findall('./TEXT/TABLE'):
                    position = table.find('./SHAPEOBJECT/POSITION')
                    if position.get('FlowWithText') == 'true':
                        _, ty, _, th = self.position(table, (0, self.records[p]['lines'][0]['vertical_position'], int(size.get('Width'))))
                        bottom = max(bottom, ty + th)
            if bottom:
                size.set('Height', str(max(int(size.get('Height')), bottom + int(margin.get('Top')) + int(margin.get('Bottom')))))

    def glyph(self, char, shape):
        if ord(char) < 0x2b0 and char not in ' \x1e\x1f':
            fid = shape.find('FONTID').get('Latin')
            family = self.root.find(f'.//FONTFACE[@Lang="Latin"]/FONT[@Id="{fid}"]').get('Name')
            if family == 'DAUL-EQN2':
                if shape.get('Id') not in self.range_shapes or char not in '0123456789~':
                    raise ValueError('DAUL-EQN2 대체는 표지 쪽수의 숫자와 범위 기호에만 허용됩니다.')
                shape = deepcopy(shape)
                shape.find('FONTID').set('Latin', self.range_font)
        glyph = super().glyph(char, shape)
        if char == '○' and glyph['font'] == 'Original HFT SPJGT':
            # The supplied cover's native outline differs from the decoded HFT circle.
            glyph['font'] = 'Original HFT cover-native-circle'
        return glyph

    def rectangle(self, rectangle, parent, fixed=None):
        badge = rectangle.findall('./DRAWINGOBJECT/DRAWTEXT/PARALIST/P')
        if any(self.ids[p] == '6' for p in badge) and self.edits.get('6') == '':
            return
        x, y, width, height = fixed if fixed is not None else self.position(rectangle, parent)
        brush = rectangle.find('./DRAWINGOBJECT/FILLBRUSH/WINDOWBRUSH')
        if brush is not None and brush.get('FaceColor') != '4294967295':
            value = int(brush.get('FaceColor'))
            color = '#' + ''.join(f'{(value >> shift) & 255:02x}' for shift in (0, 8, 16))
            self.commands.append(dict(kind='fill', x=x, y=y, width=width, height=height, color=color))
        line = rectangle.find('./DRAWINGOBJECT/LINESHAPE')
        if line is not None and line.get('Style') != 'None':
            self.commands.append(dict(kind='rect', x=x, y=y, width=width, height=height,
                                      pen=int(line.get('Width')), radius=int(rectangle.get('Ratio')) / 100))
        draw = rectangle.find('./DRAWINGOBJECT/DRAWTEXT')
        if draw is None:
            return
        margin = draw.find('TEXTMARGIN'); paragraphs = draw.findall('./PARALIST/P')
        mt, mb = int(margin.get('Top')), int(margin.get('Bottom'))
        bottom = max((self.records[p]['lines'][-1]['vertical_position'] + self.records[p]['lines'][-1]['line_height']
                      for p in paragraphs), default=0)
        # The cover's instruction table floats inside its text box; it sets the content height.
        for p in paragraphs:
            for table in p.findall('./TEXT/TABLE'):
                _, ty, _, th = self.position(table, (0, self.records[p]['lines'][0]['vertical_position'], width))
                bottom = max(bottom, ty + th)
        align = draw.find('PARALIST').get('VertAlign')
        dy = height - mt - mb - bottom if align == 'Bottom' else (height - mt - mb - bottom) / 2 if align == 'Center' else 0
        for p in paragraphs:
            self.paragraph(p, x + int(margin.get('Left')), y + mt + dy,
                           width - int(margin.get('Left')) - int(margin.get('Right')))

    def container(self, container, x, y):
        for element in container.iter():
            if element.tag not in ('RECTANGLE', 'LINE'):
                continue
            component = element.find('./DRAWINGOBJECT/SHAPECOMPONENT')
            transforms = list(component.find('RENDERINGINFO'))
            def point(px, py):
                for transform in reversed(transforms):
                    a, b, c, d, e, f = (float(transform.get('E' + str(i))) for i in range(1, 7))
                    px, py = a * px + b * py + c, d * px + e * py + f
                return x + px, y + py
            if element.tag == 'RECTANGLE':
                left, top = point(int(element.get('X0')), int(element.get('Y0')))
                right, bottom = point(int(element.get('X2')), int(element.get('Y2')))
                corner = point(int(element.get('X1')), int(element.get('Y1')))
                # Stored inverse rotations leave less than 0.05 pt of rounding residue.
                assert abs(corner[0]-right) < 5 and abs(corner[1]-top) < 5, 'Rotated cover text needs an affine text renderer'
                self.rectangle(element, (x, y, self.width), fixed=(left, top, right-left, bottom-top))
            else:
                sx, sy = point(int(element.get('StartX')), int(element.get('StartY')))
                ex, ey = point(int(element.get('EndX')), int(element.get('EndY')))
                line = element.find('./DRAWINGOBJECT/LINESHAPE')
                assert line.get('Style') in ('Solid', 'Dash', 'Dot')
                self.commands.append(dict(kind='line', x=sx, y=sy, width=ex-sx, height=ey-sy,
                                          pen=int(line.get('Width')), dash=line.get('Style') == 'Dash',
                                          dot=line.get('Style') == 'Dot'))

    def paragraph(self, p, x, y, width, nested_cells=None):
        key = self.ids[p]
        containers = p.findall('./TEXT/CONTAINER')
        if containers:
            assert len(containers) == 1 and not record_text(self.records[p]).strip()
            container = containers[0]; line = self.records[p]['lines'][0]
            size = container.find('./SHAPEOBJECT/SIZE')
            ps = self.root.find(f'.//PARASHAPE[@Id="{p.get("ParaShape")}"]')
            assert ps.get('Align') == 'Center'
            left = x + line['column_start'] + (line['segment_width'] - int(size.get('Width'))) / 2
            top = y + line['vertical_position'] + line['baseline_distance'] - int(size.get('Height')) * .85
            self.container(container, left, top)
            return 0
        if key not in self.edits:
            return super().paragraph(p, x, y, width, nested_cells)
        text = self.edits[key]
        assert isinstance(text, str), 'Cover paragraph edits must be strings'
        if text == record_text(self.records[p]):
            return super().paragraph(p, x, y, width, nested_cells)
        objects = [c for run in p.findall('TEXT') for c in run if c.tag != 'CHAR']
        if objects:
            assert all(c.tag == 'RECTANGLE' and c.find('SHAPEOBJECT/POSITION').get('TreatAsChar') == 'false' for c in objects), 'Edit the text inside an object, not its anchor'
            start = len(self.commands)
            super().paragraph(p, x, y, width, nested_cells)
            self.commands[start:] = [c for c in self.commands[start:] if 'z_order' in c]
        line = self.records[p]['lines'][0]
        cs = self.root.find(f'.//CHARSHAPE[@Id="{p.find("TEXT").get("CharShape")}"]')
        ps = deepcopy(self.root.find(f'.//PARASHAPE[@Id="{p.get("ParaShape")}"]'))
        ps.find('PARAMARGIN').set('Prev', '0')
        composer = Composer('social')
        composer.header = self; composer.root = self.root
        composer.styles['@cover'] = (cs, ps)
        top = y + line['vertical_position']
        composer.paragraph(text, '@cover', x, top, width)
        original_bottom = y + self.records[p]['lines'][-1]['vertical_position'] + self.records[p]['lines'][-1]['line_height']
        assert all(c['y'] + (c.get('height', 0) if c['kind'] != 'text' else 0) <= original_bottom + 1 for c in composer.commands), f'Cover paragraph {key} exceeds its original height'
        self.commands.extend(composer.commands)
        return 0

    def extract_cover(self):
        left = int(self.margin.get('Left'))
        top = int(self.margin.get('Top')) + int(self.margin.get('Header'))
        width = self.width - left - int(self.margin.get('Right'))
        placements = []; previous = -1
        for p in self.root.findall('./BODY/SECTION/P'):
            lines = self.records[p]['lines']
            if not lines:
                continue
            current = lines[0]['vertical_position']
            if placements and (current < previous or p.get('PageBreak') == 'true'):
                break
            placements.append((p, left, top, width))
            previous = lines[-1]['vertical_position']
        self.paragraph_borders(placements)
        for p, x, y, w in placements:
            self.paragraph(p, x, y, w)
        self.order_objects()
        return self.commands


def build_cover(variant, edits=None, name=None):
    name = name or 'cover-' + variant
    assert Path(name).name == name, 'Cover output name must be a filename stem'
    cover = Cover(variant, edits)
    commands = cover.extract_cover()
    destination = ROOT / 'generated'
    (destination / f'{name}.json').write_text(json.dumps(commands, ensure_ascii=False, indent=2), encoding='utf-8')
    source = destination / f'{name}.typ'
    source.write_text('#import "../original-header.typ": source-commands\n' +
        f'#set page(width: {cover.width / 100}pt, height: {int(cover.page.get("Height")) / 100}pt, margin: 0pt)\n' +
        f'#source-commands(json("{name}.json"))\n', encoding='utf-8')
    return source


def read_cover(path):
    path = Path(path).resolve()
    result = subprocess.run([typst_executable(), 'eval', 'query(<cover-source>).map(it => it.value)',
                             '--in', str(path), '--root', str(ROOT), '--diagnostic-format', 'short'],
                            capture_output=True, text=True, encoding='utf-8', timeout=30)
    if result.returncode or result.stderr.strip():
        raise ValueError(result.stderr)
    documents = json.loads(result.stdout)
    if len(documents) != 1 or not isinstance(documents[0], dict):
        raise ValueError('Declare one #metadata dictionary labelled <cover-source>')
    return documents[0]


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('variant', help='korean, math, or an editable cover .typ file')
    parser.add_argument('--edits', type=Path)
    parser.add_argument('--name')
    parser.add_argument('--export-json', type=Path, help='Export cover commands for an external Typst caller')
    args = parser.parse_args()
    data = (read_cover(args.variant) if args.variant.endswith('.typ') else
            json.loads(Path(args.variant).read_text(encoding='utf-8')) if args.variant.endswith('.json') else
            dict(variant=args.variant))
    edits = json.loads(args.edits.read_text(encoding='utf-8')) if args.edits else data.get('paragraphs')
    if args.export_json:
        cover = Cover(data['variant'], edits)
        result = dict(width=cover.width, height=int(cover.page.get('Height')), commands=cover.extract_cover())
        args.export_json.write_text(json.dumps(result, ensure_ascii=False), encoding='utf-8')
    else:
        source = build_cover(data['variant'], edits, args.name)
        print(render_pdf(source, ROOT / f'output/{source.stem}.pdf', 1))
