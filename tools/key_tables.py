"""Column sizing for the measured science-answer table style.

The source table uses 8.76pt regular body text, 0.36pt rules, white cells,
and compact rows. Column widths must account for the actual rendered text;
assigning a fixed 1.5 weight to the first column breaks short later headers.
"""
import re


def plan_columns(cells, measure, width=199.41, padding=1.5, border=.36):
    """Return content widths in pt, with room for padding and collapsed rules.

    ``measure`` accepts one raw source line, including inline math markup,
    and returns its rendered width at the table's 8.76pt text size. Explicit
    ``<br>`` breaks are respected. Short headings and data stay on one line
    whenever the available width permits; long prose can wrap normally.
    """
    count = len(cells[0])
    if any(len(row) != count for row in cells):
        raise ValueError('해설 표의 열 수가 일치하지 않습니다')
    available = width - 2 * padding * count - border * (count + 1)
    minima, targets = [], []
    for col in range(count):
        lines = [line for row in cells
                 for line in re.split(r'<br\s*/?>', row[col])]
        measured = [float(measure(line)) for line in lines]
        # Keep two-line mathematical symbols as indivisible inline assets.
        words = [part for line in lines
                 for part in re.findall(r'\$[^$]*\$|[^\s$]+', line)]
        word_min = max([8.76] + [float(measure(word)) for word in words])
        header = max(float(measure(line)) for line in re.split(r'<br\s*/?>', cells[0][col]))
        short = [x for x in measured if x <= 52]
        minimum = max([word_min, min(header, 62)] + short) + 1.0
        minima.append(minimum)
        targets.append(max(minimum, min(max(measured), 120)))
    if sum(minima) > available:
        # Preserve a readable column floor. Text is never shrunk to fit.
        floor = min(18.0, available / count)
        excess = sum(minima) - available
        capacities = [max(0.0, w-floor) for w in minima]
        capacity = sum(capacities)
        if capacity < excess:
            raise ValueError('표가 단 폭에 들어가지 않습니다. 열 구조를 정리하세요.')
        return [w - excess*c/capacity for w, c in zip(minima, capacities)]
    widths = minima[:]
    remaining = available - sum(widths)
    need = [max(0.0, target-w) for target, w in zip(targets, widths)]
    if sum(need):
        share = min(1.0, remaining/sum(need))
        widths = [w+share*n for w,n in zip(widths,need)]
        remaining = available-sum(widths)
    # Spare space belongs to all columns, not disproportionately to column 1.
    return [w + remaining/count for w in widths]
