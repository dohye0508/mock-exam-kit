// Compile through scripts/build.py so the original HWP styles and metrics apply.
#let exam-source(document) = {
  assert(type(document) == dictionary, message: "exam-source expects a document dictionary")
  assert(document.subject in ("korean", "english", "math", "social", "science"), message: "Unknown subject")
  [#metadata(document)<exam-source>]
}
