from pathlib import Path

import mkdocs_gen_files

SRC_ROOT = Path("chatkit")
URL_ROOT = Path("chatkit") / "chatkit"
DOCS_ROOT = Path("docs")
MANUAL_DOCS_ROOT = DOCS_ROOT / URL_ROOT

if MANUAL_DOCS_ROOT.exists():
    MANUAL_DOCS = {
        path.relative_to(DOCS_ROOT) for path in MANUAL_DOCS_ROOT.rglob("*.md")
    }
else:
    MANUAL_DOCS = set()

# Root index page for the package
root_doc = URL_ROOT / "index.md"
if root_doc not in MANUAL_DOCS:
    with mkdocs_gen_files.open(root_doc, "w") as f:
        f.write("# chatkit\n\n")
        f.write("::: chatkit\n")
else:
    mkdocs_gen_files.set_edit_path(root_doc, DOCS_ROOT / root_doc)

for path in SRC_ROOT.rglob("*.py"):
    if path.name.startswith("_"):
        continue
    if path.name in {"version.py", "logger.py", "actions.py"}:
        continue

    module_path = path.with_suffix("").relative_to(SRC_ROOT)
    identifier = ".".join(("chatkit", *module_path.parts))
    doc_path = (URL_ROOT / module_path).with_suffix(".md")

    if doc_path in MANUAL_DOCS:
        mkdocs_gen_files.set_edit_path(doc_path, DOCS_ROOT / doc_path)
        continue

    mkdocs_gen_files.set_edit_path(doc_path, path)
    with mkdocs_gen_files.open(doc_path, "w") as f:
        f.write(f"# {path.stem}\n\n")

        # For the widgets module, keep the module-level directive but only include
        # a curated set of public members so we preserve nice headings.
        if identifier == "chatkit.widgets":
            f.write(f"::: {identifier}\n")
            f.write("    options:\n")
            f.write("      members:\n")
            for symbol in (
                "WidgetTemplate",
                "DynamicWidgetRoot",
                "BasicRoot",
                "DynamicWidgetComponent",
            ):
                f.write(f"        - {symbol}\n")
        else:
            f.write(f"::: {identifier}\n")
