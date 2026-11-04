#import "original-header.typ": source-heading, source-footer, source-commands
// All families come from the original HWP's language-specific font records.
#let fonts = (
  body: ("Original HFT TEJMJHG", "Original HFT ENSMJ", "Original HFT SPSMJ"),
  title: ("Original HFT TESGRHG", "Original HFT TESGREN", "Original HFT SPSMJ"),
  year: ("Original HFT TEDNRHG", "Original HFT TEDNREN", "Original HFT SPSMJ"),
  period: ("Original HFT HGGMJ", "Original HFT ENGMJ", "Original HFT SPSMJ"),
  number: ("Original HFT TEGMJHG", "Original HFT TEGMJEN"),
  bold: ("Original HFT HGGGT", "Original HFT ENGGT", "Original HFT SPSMJ"),
  label: ("Original HFT HCHGTGT", "Original HFT HCENTGT", "Original HFT SPSMJ"),
)

#let original-settings = json("source-layout/overview.json")
#let hwp-unit(value) = float(value) / 100 * 1pt
#let specs = (
  korean: (title: "국어 영역", period: 1, width: 297mm, height: 420mm,
    left: 31mm, rule: 77.0mm, bottom: 376.5mm, gap: 11mm, total: 20, year-y: 41.4mm, title-y: 54.8mm),
  english: (title: "영어 영역", period: 3, width: 297mm, height: 420mm,
    left: 31mm, rule: 77.5mm, bottom: 376.5mm, gap: 11mm, total: 8, year-y: 41.4mm, title-y: 54.8mm),
  math: (title: "수학 영역", period: 2, width: 272mm, height: 394mm,
    left: 18.7mm, rule: 59.4mm, bottom: 357.8mm, gap: 11.7mm, total: 20, year-y: 24.4mm, title-y: 38mm),
  social: (title: "사회탐구 영역", period: 4, width: 272mm, height: 394mm,
    left: 18.7mm, rule: 66.5mm, bottom: 358.2mm, gap: 11mm, total: 32, year-y: 21.8mm, title-y: 36.5mm),
  science: (title: "과학탐구 영역", period: 4, width: 272mm, height: 394mm,
    left: 18.7mm, rule: 66.5mm, bottom: 358.2mm, gap: 11mm, total: 32, year-y: 21.8mm, title-y: 36.5mm),
)

#let lettering(body, font, size, ratio: 100%, tracking: 0em, weight: "regular") = {
  scale(x: ratio, y: 100%, reflow: true, origin: top + left,
    text(font: font, size: size, tracking: tracking, fallback: false, weight: weight,
      spacing: 0.5em, kerning: false, ligatures: false, cjk-latin-spacing: none,
      top-edge: "cap-height", bottom-edge: "baseline", body))
}

#let at(x, y, body) = place(top + left, dx: x, dy: y, body)

#let original-math-heading(year, page-no, title: none) = {
  let heading = json("source-layout/math-header.json")
  assert(str(year).len() == 4, message: "Year must contain four digits")
  for (name, glyphs) in heading {
    if name == "year" and title != none { continue }
    for (index, glyph) in glyphs.enumerate() {
      let char = if name == "year" and index < 4 { str(year).clusters().at(index) } else { glyph.char }
      if name == "page-number" {
        let content = scale(x: glyph.ratio * 100%, y: 100%, reflow: true, origin: top+left,
          text(font: glyph.font, size: glyph.height/100*1pt, fallback: false,
            top-edge: "baseline", bottom-edge: "baseline", str(page-no)))
        context { at((glyph.x+glyph.advance)/100*1pt-measure(content).width, glyph.y/100*1pt, content) }
      } else {
      at(glyph.x / 100 * 1pt, glyph.y / 100 * 1pt,
        scale(x: glyph.ratio * 100%, y: 100%, origin: top+left,
          text(font: glyph.font, size: glyph.height/100*1pt,
            weight: if glyph.bold {"bold"} else {"regular"}, fallback: false,
            top-edge: "baseline", bottom-edge: "baseline", char)))
      }
    }
  }
  let frames = json("source-layout/math-frames.json")
  let period = frames.period
  at(period.x/100*1pt, period.y/100*1pt,
    box(width: period.width/100*1pt, height: period.height/100*1pt,
      stroke: period.pen/100*1pt, radius: 50%))
  let label = frames.label
  at(label.x/100*1pt, label.y/100*1pt,
    box(width: label.width/100*1pt, height: label.height/100*1pt, stroke: label.pen_mm*1mm))
  let rule = frames.rule
  at(rule.x/100*1pt, rule.y/100*1pt, line(length: rule.width/100*1pt, stroke: rule.pen_mm*1mm))
}

#let identity-row(s) = {
  let y = 55.1mm
  let label(body) = lettering(body, fonts.year, 16pt, ratio: 95%)
  at(s.width/2 - 98mm, y, grid(columns: (14.6mm, 29.7mm),
    stroke: 0.4pt, inset: 1.8mm, align: center + horizon, label[성명], []))
  at(s.width/2 - 49mm, y, grid(columns: (25.5mm, ..(7.2mm,)*9),
    stroke: 0.4pt, inset: (top: 1.8mm, bottom: 1.8mm), align: center + horizon,
    label[수험번호], [], [], [], [], [―], [], [], [], []))
  at(s.width/2 + 46.8mm, y, box(stroke: 0.4pt, inset: (x: 2.3mm, y: 1.8mm), label[제 [　] 선택]))
}

#let exam-page(subject, left-content, right-content, year: 2025, title: none, elective: none, page-no: 1, footer-no: none, total: none, last-page: none, auto-flow: false, heading-commands: none, overlay: []) = {
  assert(subject in specs, message: "Unknown subject")
  assert(elective == none or subject in ("math", "korean"), message: "Elective layouts apply to mathematics and Korean")
  let elective-profile = if elective == none { none } else { json("source-layout/" + subject + "-electives.json").at(elective) }
  if elective-profile != none {
    assert(page-no > 0 and (auto-flow or page-no in range(1,5)), message: "Original elective sections contain four pages")
    assert(page-no != 4 or "last_note" in elective-profile, message: "Original Korean final-note glyphs are not yet imported; page 4 cannot be rendered completely")
  }
  let original = if elective-profile != none { elective-profile.settings }
    else if subject == "social" and page-no > 1 { original-settings.social.sections.at(1) }
    else { original-settings.at(subject) }
  let active-heading = if elective-profile == none { heading-commands } else {
    let variant = if page-no == 1 { "first" } else if not auto-flow and page-no == 4 { "last" } else if calc.even(page-no) { "even" } else { "odd" }
    json("source-layout/" + elective-profile.headers.at(variant) + ".json")
  }
  let columns = original.columns.find(c => c.Count == "2")
  assert(columns != none, message: "Original HWP has no two-column definition")
  let s = specs.at(subject) + (
    width: hwp-unit(original.page.Width),
    height: hwp-unit(original.page.Height),
    gap: hwp-unit(columns.SameGap),
    left: hwp-unit(original.margins.Left),
  )
  let total = if total == none { s.total } else { total }
  let inquiry = subject in ("social", "science")
  let variant = subject in ("korean", "english")
  set page(width: s.width, height: s.height, margin: 0mm)
  set text(font: fonts.body, size: 11.5pt, fallback: false, lang: "ko",
    tracking: -0.05em, spacing: 0.5em, kerning: false, ligatures: false,
    cjk-latin-spacing: none, top-edge: "ascender", bottom-edge: "descender")
  set par(leading: 0.55em, spacing: 2.5mm, justify: true)
  if subject == "math" and page-no == 1 and elective-profile == none and active-heading == none { original-math-heading(year, page-no, title: title) }
  else { source-heading(subject, year, page-no, title: title, commands: active-heading) }
  if title != none and page-no == 1 {
    let commands = if active-heading == none { json("source-layout/" + subject + "-header.json") } else { active-heading }
    let glyphs = if subject == "math" and active-heading == none { commands.year } else {
      let y = commands.find(c => c.at("field", default: none) == "year").y
      commands.filter(c => c.kind == "text" and c.y == y)
    }
    let model = glyphs.first()
    context {
      let space-after = range(glyphs.len() - 1).find(i => glyphs.at(i+1).x - glyphs.at(i).x - glyphs.at(i).advance > 1)
      let space-width = (glyphs.at(space-after+1).x - glyphs.at(space-after).x - glyphs.at(space-after).advance)/100*1pt
      let chars = title.clusters().map(ch => {
        let latin = ch.matches(regex("^[ -~]$")).len() > 0
        let hangul = ch.matches(regex("^[가-힣]$")).len() > 0
        assert(latin or hangul, message: "Title needs an original-font mapping for: " + ch)
        let original-font = if latin { "Original HFT TEDNREN" } else { "Original HFT TEDNRHG" }
        let style = glyphs.find(g => g.font == original-font)
        let font = if hangul and not read("source-layout/wansung-hangul.txt").contains(ch) { "Original HFT HMKMG" } else { original-font }
        let render(c) = scale(x: style.ratio * 100%, y: 100%, reflow: true, origin: top+left,
          text(font: font, size: style.height/100*1pt, weight: "regular", tracking: 0em,
            fallback: false, top-edge: "baseline", bottom-edge: "baseline", c))
        let content = if ch == " " { [] } else { render(ch) }
        // Match HncBaseDraw's quarter-height scaling and integer tracking.
        let scaled = if ch == " " { 0 } else {
          measure(content).width / 1pt * 100 * calc.floor(style.height / 4) / style.height
        }
        let base = if style.ratio == 1 { calc.round(scaled) * 4 } else { calc.floor(scaled + 0.0000001) * 4 }
        let percent = calc.round(style.trailing_spacing * 100 / (style.advance - style.trailing_spacing))
        let tracking = calc.round(calc.abs(base / 4 * percent) / 100) * 4 * if percent < 0 {-1} else {1}
        (content: content, width: if ch == " " {space-width} else {base/100*1pt},
          advance: if ch == " " {space-width} else {(base+tracking)/100*1pt})
      })
      assert(chars.len() > 0, message: "Title must not be empty")
      let width = chars.map(c => c.advance).sum() + chars.last().width - chars.last().advance
      assert(width <= s.width - 2*s.left, message: "Title exceeds the original heading width")
      let last = glyphs.last()
      let last-width = (last.advance - last.trailing_spacing)/100*1pt
      let center = (glyphs.first().x/100*1pt + last.x/100*1pt + last-width)/2
      let x = center - width/2
      for ch in chars {
        at(x, model.y/100*1pt, ch.content)
        x += ch.advance
      }
    }
  }
  if subject == "math" and page-no == 1 and elective-profile == none {
    // Original first-page LINE: centered +105 HWPUNIT, y=16842, height=85039, pen=100.
    at(s.width/2 + hwp-unit("105"), hwp-unit("16842"),
      line(start: (0pt, 0pt), end: (hwp-unit("1"), hwp-unit("85039")), stroke: 1pt))
  } else if inquiry and page-no == 1 {
    at(s.width/2, hwp-unit("18991"), line(start: (0pt, 0pt), end: (hwp-unit("1"), hwp-unit("83330")), stroke: 1.13pt))
  }
  let layouts = json("source-layout/body-geometry.json").at(subject)
  let last-page = if last-page != none { last-page } else { ((subject == "english" and page-no == total) or
    (subject in ("social", "science") and page-no == 4) or
    (subject == "korean" and page-no == 12)) }
  let geometry = if elective != none {
      let index = if auto-flow { if page-no == 1 {0} else if calc.even(page-no) {1} else {2} } else {page-no - 1}
      let geometry = layouts.electives.at(elective).at(index)
      if auto-flow and last-page { geometry + (bottom: (geometry.bottom.first(), calc.min(geometry.bottom.last(), elective-profile.note_top))) } else {geometry}
    }
    else if page-no == 1 { layouts.at(if last-page { "first_last" } else { "first" }) }
    else { layouts.at(if last-page { "last" } else { "continuation" }) }
  for (index, body) in (left-content, right-content).enumerate() {
    let content = block(width: hwp-unit(geometry.width), body)
    at(hwp-unit(geometry.left + index * (geometry.width + geometry.gap)),
      hwp-unit(geometry.top.at(index)), context {
        assert(measure(content).height < hwp-unit(geometry.bottom.at(index) - geometry.top.at(index)),
          message: "Column overflows the original body area or final note: split questions onto another exam-page")
        content
      })
  }
  if elective-profile == none { source-footer(subject, if footer-no == none { page-no } else { footer-no }, total) }
  else { source-commands(json("source-layout/" + elective-profile.footer + ".json"),
    page-no: if footer-no != none {footer-no} else if auto-flow {page-no} else {page-no+elective-profile.page_offset}, total:total) }
  overlay
  if subject in ("english", "social", "science") and last-page {
    source-commands(json("source-layout/" + subject + "-last-note.json"))
  }
  if elective-profile != none and (if auto-flow {last-page} else {page-no == 4}) {
    source-commands(json("source-layout/" + elective-profile.last_note + ".json"))
  }
  if subject == "korean" and elective-profile == none and last-page {
    source-commands(json("source-layout/korean-common-last-note.json"))
  }
  pagebreak(weak: true)
}

#let question(number, body, points: none) = block(above: 0mm, below: 3mm)[
  #text(font: fonts.period, size: 13.5pt)[#number.]#h(1.3mm)#body
  #if points != none { [ [#points#("점")]] }
]

#let choices(items, columns: 1) = {
  assert(items.len() == 5, message: "Five answer choices are required")
  grid(columns: (1fr,)*columns, gutter: 2.5mm, row-gutter: 1.6mm,
    ..items.enumerate().map(((i, item)) => [#("①②③④⑤".clusters().at(i))#h(1.5mm)#item]))
}

#let passage(body) = block(width: 100%, inset: 3mm, stroke: 0.4pt, above: 3mm, below: 4mm, body)
#let example(body) = block(width: 100%, inset: (x: 3mm, y: 4mm), stroke: 0.4pt, above: 4mm, below: 4mm)[
  #place(top+center, dy: -6mm, box(fill: white, inset: (x: 0.8mm))[〈보 기〉])
  #body
]
#let label(body) = box(stroke: 0.4pt, inset: (x: 5mm, y: 2mm), text(font: fonts.label, size: 15pt, body))
