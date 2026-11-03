"""Regular-weight math assets for the measured answer/explanation layout.

HancomEQN supplies equation glyphs without a substitute-font fallback.  This preserves the reference's light 9 pt equation style without
claiming that MathText is the native Hancom equation typesetter.
"""
from functools import lru_cache
import hashlib
import os
import re
from pathlib import Path

MATH_SIZE = 9.0
MATH_DPI = 600


@lru_cache(maxsize=1)
def _font_config():
    from matplotlib import font_manager

    from examkit.typst_runtime import engine_root
    path = engine_root() / 'fonts/HancomEQN.ttf'
    if not path.is_file(): raise FileNotFoundError(path)
    font_manager.fontManager.addfont(str(path))
    pattern = font_manager.FontProperties(fname=str(path)).get_fontconfig_pattern()
    config = {f'mathtext.{key}': pattern for key in ('rm', 'it', 'bf', 'sf', 'tt', 'cal')}
    config.update({'mathtext.fontset': 'custom', 'mathtext.default': 'it', 'mathtext.fallback': None})
    return config



def render_math(expression, display, directory):
    """Return width, height, baseline depth (pt), and a local PNG filename.

    Fractions use full-size 9pt numerator/denominator glyphs. Surrounding
    symbols retain their regular weight and size; only the containing line
    grows. Raster dimensions preserve the equation's natural aspect ratio.
    """
    import matplotlib as mpl
    from matplotlib.font_manager import FontProperties
    from matplotlib.mathtext import MathTextParser, math_to_image
    from PIL import Image

    expression = expression.strip()
    if not expression:
        raise ValueError('빈 수식은 조판할 수 없습니다')
    # mathtext가 모르는 흔한 LaTeX 별칭. 한글 단위는 \text{} 대신 수식 밖에 쓴다
    for alias, name in ((r'\\ge(?![a-zA-Z])', r'\\geq'), (r'\\le(?![a-zA-Z])', r'\\leq'), (r'\\ne(?![a-zA-Z])', r'\\neq')):
        expression = re.sub(alias, name, expression)
    if re.search(r'\\text\{[^}]*[가-힣]', expression):
        raise ValueError('수식 안 한글(\\text{초} 등)은 글리프가 없습니다. 단위는 수식 밖 본문에 쓰세요: ' + expression)
    from examkit.native_math import equation
    from examkit.typst_runtime import engine_root
    equation(expression, MATH_SIZE, str(engine_root() / 'fonts/HancomEQN.ttf'))
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    key = ('hancom-eqn-no-fallback-v3', expression, bool(display), MATH_SIZE, MATH_DPI)
    filename = 'math-' + hashlib.sha256(repr(key).encode()).hexdigest()[:20] + '.png'
    path = directory / filename
    with mpl.rc_context(_font_config()):
        prop = FontProperties(size=MATH_SIZE, weight='normal', math_fontfamily='custom')
        source = '$' + re.sub(r'\\frac\b', r'\\dfrac', expression) + '$'
        metrics = MathTextParser('path').parse(source, dpi=72, prop=prop)
        if not path.is_file():
            math_to_image(source, path, prop=prop, format='png', dpi=MATH_DPI,
                          color='black')
    with Image.open(path) as image:
        width, height = (value * 72 / MATH_DPI for value in image.size)
    # math_to_image builds the canvas from path metrics.  Match its sub-pixel
    # rounded height while retaining the measured baseline of the same layout.
    depth = float(metrics.depth) * height / float(metrics.height)
    return width, height, depth, filename
