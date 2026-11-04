#let equation-manifest = json("assets/equations/manifest.json")
#let hwp-equation(key) = {
  let value = equation-manifest.at(key)
  box(width: value.width * 1pt, height: value.height * 1pt,
    baseline: (value.height-value.baseline) * 1pt,
    image("assets/equations/" + key + ".svg", width: value.width * 1pt, height: value.height * 1pt))
}
