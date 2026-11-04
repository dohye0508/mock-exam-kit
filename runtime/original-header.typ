#let source-commands(commands, year: 2025, page-no: 1, total: 20) = {
  assert(str(year).len() == 4)
  let unit(n) = n / 100 * 1pt
  let total-items = commands.filter(c => c.at("field",default:none) == "total")
  if total-items.len() > 0 {
    assert(type(total) == int and total > 0, message: "Total page count must be a positive integer")
    let model = total-items.first()
    let last = total-items.last()
    let digits = str(total).clusters()
    let right = last.x + last.advance - last.trailing_spacing
    let start = right - (digits.len() * model.advance - model.trailing_spacing)
    let left = commands.find(c => c.at("field",default:none) == "page-number").x
    assert(start >= left, message: "Total page count exceeds the original footer cell")
    commands = commands.filter(c => c.at("field",default:none) != "total")
    commands += digits.enumerate().map(((i,ch)) => model + (char:ch,field_index:i,x:start+i*model.advance))
  }
  for item in commands {
    let content = if item.kind == "text" {
      let char = if item.at("field", default: none) == "year" { str(year).clusters().at(item.field_index) }
        else if item.at("field", default: none) == "page-number" { str(page-no) }
        else if item.at("field", default: none) == "total" { str(total).clusters().at(item.field_index, default: "") }
        else { item.char }
      skew(ax: -calc.atan(item.at("shear", default: 0)), origin: top+left,
      scale(x: item.ratio * 100%, y: 100%, origin: top+left,
        text(font: item.font, size: unit(item.height), fill: rgb(item.at("color",default:"#000000")), weight: item.at("weight", default: if item.bold {"bold"} else {"regular"}),
          tracking: 0pt,
          style: if item.at("italic",default:false) {"italic"} else {"normal"},
          stroke: if item.at("stroke",default:0)>0 {unit(item.stroke)} else {none},
          fallback: false, top-edge: "baseline", bottom-edge: "baseline", char)))
    } else if item.kind == "line" {
      // HncBaseDraw uses 280 units/mm and dash/gap factors 110/15 and 110/25.
      // shortcut: device-pixel rounding varies with print resolution; PDF keeps the physical lengths.
      let dash-pen = calc.round(item.pen * 25.4 / 7200 * 280)
      line(start: (0pt,0pt),end: (unit(item.width),unit(item.height)),
        stroke: (paint: rgb(item.at("color",default:"#000000")),
          thickness: unit(if item.dash {dash-pen} else {item.pen}),
          dash: if item.at("dot",default:false) {(array: (unit(item.pen * 1.5),unit(item.pen * 2.25)))}
            else if item.dash {(array: (unit(dash-pen * 110 / 15),unit(dash-pen * 110 / 25)))} else {"solid"}))
    } else if item.kind == "rect" {
      box(width: unit(item.width),height: unit(item.height),stroke: unit(item.pen),radius: item.radius * 100%)
    } else if item.kind == "fill" {
      box(width: unit(item.width),height: unit(item.height),fill: rgb(item.at("color",default:"#000000")))
    } else if item.kind == "equation" {
      image("assets/equations/" + item.key + ".svg", width: unit(item.width), height: unit(item.height), fit: "stretch")
    } else if item.kind == "image" {
      let picture = box(width: unit(item.width),height: unit(item.height),clip: true,
        place(top+left,dx: -unit(item.at("crop_x",default:0)),dy: -unit(item.at("crop_y",default:0)),
          image(item.path,width: unit(item.full_width),height: unit(item.full_height),fit: "stretch")))
      scale(x: if item.at("flip_x",default:false) {-100%} else {100%},
        y: if item.at("flip_y",default:false) {-100%} else {100%},origin:center,
        box(width: unit(item.width),height: unit(item.height), {
          place(top+left,picture)
          if item.at("border",default:none) != none {
            // shortcut: Typst omits zero-width strokes; near-zero preserves a PDF path but does not reproduce Hancom's device hairline. Replace when native hairline output is supported.
            place(top+left,box(width: unit(item.width),height: unit(item.height),
              stroke: (paint: rgb(item.border.color),thickness: unit(calc.max(item.border.pen,0.001)))))
          }
        }))
    }
    if item.at("clip",default:none) != none {
      let clip = item.clip
      place(top+left,dx: unit(item.x+clip.x),dy: unit(item.y+clip.y),
        box(width:unit(clip.width),height:unit(clip.height),clip:true,
          place(top+left,dx:-unit(clip.x),dy:-unit(clip.y),content)))
    } else {
      place(top+left,dx: unit(item.x),dy: unit(item.y),content)
    }
  }
}

#let source-furniture(filename, year: 2025, page-no: 1, total: 20) = source-commands(
  json("source-layout/" + filename + ".json"), year: year, page-no: page-no, total: total)

#let source-heading(subject, year, page-no, title: none, commands: none) = {
  let variant = if page-no > 1 {
    if calc.even(page-no) { "-even" } else { "-odd" }
  } else { "" }
  let commands = if commands == none { json("source-layout/" + subject + variant + "-header.json") } else { commands }
  if title != none and page-no == 1 {
    let year-glyph = commands.find(c => c.at("field", default: none) == "year")
    commands = commands.filter(c => c.kind != "text" or c.y != year-glyph.y)
  }
  source-commands(commands, year: year, page-no: page-no)
}
#let source-footer(subject, page-no, total) = source-furniture(subject + "-footer", page-no: page-no, total: total)
