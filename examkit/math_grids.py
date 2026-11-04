"""Matrix/cases boxes using the existing MathText glyph and delimiter renderer."""
import re


DELIMITERS = {'matrix': ('.','.'), 'pmatrix': ('(',')'), 'bmatrix': ('[',']'),
              'Bmatrix': ('{','}'), 'vmatrix': ('|','|'), 'Vmatrix': ('|','|'),
              'cases': ('{','.'), 'array':('.','.'), 'aligned':('.','.'), 'align':('.','.'), 'align*':('.','.')}
ENVIRONMENT = re.compile(r'\\(begin|end)\{([A-Za-z]+\*?)\}')


def rows(source, separator=r'\\'):
    """Split only outside groups; nested environments have already become atoms."""
    result=[[]];start=0;depth=0;i=0
    while i<len(source):
        if depth==0 and source.startswith(separator,i):
            result[-1].append(source[start:i].strip());result.append([])
            i+=len(separator);start=i;continue
        if source[i]=='\\':i+=2;continue
        if source[i]=='{':depth+=1
        elif source[i]=='}':
            depth-=1
            if depth<0:raise ValueError('행렬 수식의 중괄호가 맞지 않습니다.')
        elif source[i]=='&' and depth==0:
            result[-1].append(source[start:i].strip());start=i+1
        i+=1
    if depth:raise ValueError('행렬 수식의 중괄호가 맞지 않습니다.')
    result[-1].append(source[start:].strip())
    if len(result)>1 and result[-1]==['']:result.pop()  # A final row separator is valid LaTeX.
    if not any(cell for row in result for cell in row):raise ValueError('빈 행렬은 조판할 수 없습니다.')
    if len({len(row) for row in result})!=1:raise ValueError('행렬의 각 행은 열 개수가 같아야 합니다.')
    return result


def expand(source, grids, reserved):
    stack=[];spans=[]
    for match in ENVIRONMENT.finditer(source):
        action,name=match.groups()
        if action=='begin':
            if name not in DELIMITERS:raise ValueError('지원하지 않는 수식 환경: '+name)
            stack.append(match)
        else:
            if not stack or stack[-1][2]!=name:raise ValueError('수식 begin/end 환경이 맞지 않습니다.')
            begin=stack.pop()
            if not stack:spans.append((begin,match))
    if stack:raise ValueError('수식 환경의 end가 없습니다.')
    result=[];start=0
    for begin,end in spans:
        result.append(source[start:begin.start()])
        body=source[begin.end():end.start()];alignment=None
        if begin[2]=='array':
            spec=re.match(r'\s*\{([lcr]+)\}',body)
            if spec is None:raise ValueError('array에는 {lcr} 형식의 열 정렬이 필요합니다. 수직선·너비 지정은 지원하지 않습니다.')
            alignment=spec[1];body=body[spec.end():]
        cells=rows(expand(body,grids,reserved))
        if begin[2]=='cases' and len(cells[0])!=2:raise ValueError('cases는 식과 조건의 두 열이 필요합니다.')
        if alignment is not None and len(alignment)!=len(cells[0]):raise ValueError('array 열 정렬 개수와 실제 열 수가 다릅니다.')
        if begin[2] in ('align','align*','aligned'):
            if len(cells[0])%2:raise ValueError('align은 좌변과 우변을 &로 나눈 열 쌍이 필요합니다.')
            alignment='rl'*(len(cells[0])//2)
        # Private atoms never reach font lookup, and cannot shadow the user's text.
        atom=next((chr(n) for n in range(0xE000,0xF900) if chr(n) not in reserved),None)
        if atom is None:raise ValueError('한 수식에 행렬이 너무 많습니다.')
        reserved.add(atom);grids[atom]=(begin[2],cells,alignment);result.append(atom);start=end.end()
    result.append(source[start:])
    return ''.join(result)


def math_parser(output, source):
    from matplotlib.mathtext import MathTextParser
    parser=MathTextParser(output)
    if not ENVIRONMENT.search(source):return parser
    from matplotlib import _mathtext as m

    # shortcut: Matplotlib's box API is private; run matrix layout tests on upgrades.
    class GridParser(m.Parser):
        def parse(self, expression, *args):
            self.grids={}
            expression=expand(expression,self.grids,set(expression))
            return super().parse(expression,*args)

        def symbol(self, expression, location, tokens):
            if tokens['sym'] not in self.grids:return super().symbol(expression,location,tokens)
            name,cells,alignment=self.grids[tokens['sym']]
            boxes=[]
            for row in cells:
                line=[]
                for cell in row:
                    depth=len(self._state_stack);script=self._in_subscript_or_superscript
                    self.push_state()
                    try:line.append(self._math_expression.parse_string(cell,parse_all=True)[0] if cell else m.Hlist([]))
                    finally:
                        del self._state_stack[depth:]
                        self._in_subscript_or_superscript=script
                boxes.append(line)
            state=self.get_state();em=state.fontsize*state.dpi/72
            widths=[max(row[i].width for row in boxes) for i in range(len(boxes[0]))]
            lines=[]
            for row in boxes:
                pieces=[m.Vbox(em*.8,em*.2)]
                for i,(cell,width) in enumerate(zip(row,widths)):
                    if i:pieces.append(m.Hbox(em*(.2 if i%2 else 2) if name in ('align','align*','aligned') else em))
                    align=alignment[i] if alignment else 'l' if name=='cases' else 'c'
                    pad=(width-cell.width)*{'l':0,'c':.5,'r':1}[align]
                    pieces.extend([m.Hbox(pad),cell,m.Hbox(width-cell.width-pad)])
                if lines:lines.append(m.Vbox(0,em*.2))
                lines.append(m.Hlist(pieces,do_kern=False))
            grid=m.Vlist(lines)
            metrics=state.fontset.get_metrics(state.font,state.font_class,'=',state.fontsize,state.dpi)
            axis=(metrics.ymax+metrics.ymin)/2
            grid.shift_amount=(grid.height-grid.depth)/2-axis
            middle=m.Hlist([grid])
            if name=='Vmatrix':
                # HancomEQN lacks U+2016; compose the two bars from its own | glyph.
                def bars():
                    return [m.AutoHeightChar('|',middle.height,middle.depth,state),m.Hbox(em*.12),
                            m.AutoHeightChar('|',middle.height,middle.depth,state)]
                return [m.Hlist(bars()+[middle]+bars(),do_kern=False)]
            return [self._auto_sized_delimiter(DELIMITERS[name][0],[middle],DELIMITERS[name][1])]

    parser._parser=GridParser()
    return parser
