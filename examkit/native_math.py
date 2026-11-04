"""Lay out fresh equations with the original HancomEQN outlines, without COM."""
from functools import lru_cache
import re


def latex(expression):
    expression = expression.strip()
    if not expression:
        raise ValueError('빈 수식입니다.')
    if '\\' in expression:
        return expression
    # Translate balanced HWP groups before handing layout to MathText.
    depth = 0
    for i, char in enumerate(expression):
        if char == '{': depth += 1
        elif char == '}': depth -= 1
        if depth == 0 and expression[i:i+4] == 'over' and (i == 0 or not expression[i-1].isalpha()) and (i+4 == len(expression) or not expression[i+4].isalpha()):
            return r'\frac{' + latex(expression[:i]) + '}{' + latex(expression[i+4:]) + '}'
        if depth < 0: raise ValueError('수식 중괄호가 맞지 않습니다.')
    if depth: raise ValueError('수식 중괄호가 맞지 않습니다.')
    result = ''; i = 0
    while i < len(expression):
        grid=re.match(r'(matrix|cases)\s*\{',expression[i:]) if i==0 or not expression[i-1].isalpha() else None
        if grid is None and (i==0 or not expression[i-1].isalpha()) and re.match(r'(matrix|cases)\b',expression[i:]):
            raise ValueError('matrix/cases의 내용은 중괄호로 감싸 주세요.')
        if grid:
            from .math_grids import rows
            start=i+grid.end();end=start;depth=1
            while depth:
                depth+=(expression[end]=='{')-(expression[end]=='}');end+=1
            cells=rows(expression[start:end-1],separator='#')
            name=grid[1]
            result+=r'\begin{'+name+'}'+r'\\'.join('&'.join(latex(c) if c else '' for c in row) for row in cells)+r'\end{'+name+'}'
            i=end;continue
        if expression[i] == '{':
            end = i+1; depth = 1
            while depth:
                depth += (expression[end] == '{') - (expression[end] == '}'); end += 1
            result += '{' + latex(expression[i+1:end-1]) + '}'; i = end
        else:
            result += expression[i]; i += 1
    if re.search(r'\b(pile|atop|binom)\b', result):
        raise ValueError('이 한글 수식 명령은 LaTeX로 작성해 주세요: ' + expression)
    words = 'sqrt sum prod int lim sin cos tan log ln exp alpha beta gamma delta epsilon theta lambda mu pi rho sigma phi omega infinity times div leq geq neq cdot'.split()
    result = re.sub(r'(?<!\\)\b(' + '|'.join(words) + r')\b', lambda m: '\\' + ('infty' if m[0] == 'infinity' else m[0]), result)
    result = re.sub(r'\bLEFT\b', r'\\left', result)
    result = re.sub(r'\bRIGHT\b', r'\\right', result)
    for word, command in [('rm', 'mathrm'), ('it', 'mathit'), ('bold', 'mathbf')]:
        if result.startswith(word + ' '): result = '\\' + command + '{' + result[len(word)+1:] + '}'
    return result.replace('`', r'\,')


@lru_cache(maxsize=512)
def equation(expression, size, font_path):
    import matplotlib as mpl
    import logging
    from matplotlib import font_manager
    from matplotlib.font_manager import FontProperties
    from .math_grids import math_parser
    from fontTools.ttLib import TTFont
    from pathlib import Path

    font_path = Path(font_path)
    if not font_path.is_file():
        raise FileNotFoundError(f'원본 수식 글꼴이 필요합니다: {font_path}')
    font_manager.fontManager.addfont(str(font_path))
    with TTFont(font_path, lazy=True) as font:
        cmap = font.getBestCmap()
    pattern = FontProperties(fname=str(font_path)).get_fontconfig_pattern()
    config = {f'mathtext.{key}': pattern for key in ('rm', 'it', 'bf', 'sf', 'tt', 'cal')}
    config.update({'mathtext.fontset': 'custom', 'mathtext.default': 'it', 'mathtext.fallback': None})
    source = '$' + latex(expression) + '$'
    messages = []
    class Warnings(logging.Handler):
        def emit(self, record):
            if record.levelno >= logging.WARNING: messages.append(record.getMessage())
    logger = logging.getLogger('matplotlib'); handler = Warnings(); logger.addHandler(handler)
    try:
        with mpl.rc_context(config):
            parsed = math_parser('path',source).parse(source, dpi=72, prop=FontProperties(size=size))
    finally: logger.removeHandler(handler)
    if messages:
        raise ValueError('원본 수식 글꼴로 출력할 수 없습니다: ' + '; '.join(messages))
    baseline = float(parsed.height - parsed.depth) * 100
    commands = []
    for face, points, code, x, y in parsed.glyphs:
        if Path(face.fname).resolve() != font_path.resolve() or code not in cmap:
            raise ValueError(f'원본 수식 글꼴에 없는 문자: U+{code:04X} ({expression})')
        commands.append(dict(kind='text', char=chr(code), font='HancomEQN', height=float(points)*100,
                             ratio=1, bold=False, italic=False, x=float(x)*100, y=baseline-float(y)*100,
                             advance=0, trailing_spacing=0))
    for x, y, w, h in parsed.rects:
        commands.append(dict(kind='fill', x=float(x)*100, y=baseline-float(y+h)*100,
                             width=float(w)*100, height=float(h)*100))
    return dict(commands=commands, width=float(parsed.width)*100, height=float(parsed.height)*100, baseline=baseline)
