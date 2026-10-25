#!/usr/bin/env python3
"""Build the stroked drawings in icons-src/ into Aiko's filled sprite symbols.

Each source is a 20x20 SVG drawn with 1.33 round strokes. Strokes are expanded
and unioned into one filled path (the house style of assets/icons.svg), svgo
compacts the path data, and the symbol plus its metadata line are written into
assets/icons.svg and index.html in place.

Source elements, in document order:
  <use href="#<id>"/>   adds an existing sprite glyph (optional transform)
  class="fill"          adds the shape's filled area only
  class="cut"           removes the shape's area (plus its stroke if it sets
                        stroke-width) from everything drawn before it
  anything else         adds the shape's stroke (and fill, unless fill="none")

Root attributes: data-id (6-hex, added on first build), data-category, data-tags.

  python3 scripts/build-icons.py          rebuild and write
  python3 scripts/build-icons.py --check  fail if the committed files are stale
"""
import json
import random
import re
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

import pathops
from fontTools.misc.transform import Transform
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.svgLib.path import parse_path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "icons-src"
SPRITE = ROOT / "assets" / "icons.svg"
INDEX = ROOT / "index.html"
SVGO = "svgo@4.1.0"
STROKE = 1.33
LIVE_AREA = (0.5, 19.5)  # every new icon must sit inside this square
CATEGORIES = ["UI", "AI", "Developer", "Files", "Social", "Media", "System", "Business", "Other"]


class CubicPathPen(SVGPathPen):
    """SVGPathPen that writes quadratic curves as cubics, so svgo can turn them into arcs."""
    _qCurveToOne = SVGPathPen.__bases__[0]._qCurveToOne


def shape_d(el):
    tag = el.tag.split("}")[-1]
    num = lambda k, default=0.0: float(el.get(k, default))
    if tag == "path":
        return el.get("d")
    if tag == "line":
        return f"M{num('x1')} {num('y1')}L{num('x2')} {num('y2')}"
    if tag in ("polyline", "polygon"):
        pts = re.findall(r"-?[\d.]+", el.get("points"))
        pairs = [f"{pts[i]} {pts[i + 1]}" for i in range(0, len(pts), 2)]
        return "M" + "L".join(pairs) + ("Z" if tag == "polygon" else "")
    if tag == "circle":
        cx, cy, r = num("cx"), num("cy"), num("r")
        return f"M{cx - r} {cy}a{r} {r} 0 1 0 {2 * r} 0a{r} {r} 0 1 0 {-2 * r} 0Z"
    if tag == "ellipse":
        cx, cy, rx, ry = num("cx"), num("cy"), num("rx"), num("ry")
        return f"M{cx - rx} {cy}a{rx} {ry} 0 1 0 {2 * rx} 0a{rx} {ry} 0 1 0 {-2 * rx} 0Z"
    if tag == "rect":
        x, y, w, h = num("x"), num("y"), num("width"), num("height")
        r = min(num("rx", el.get("ry", 0)), w / 2, h / 2)
        if not r:
            return f"M{x} {y}h{w}v{h}h{-w}Z"
        return (f"M{x + r} {y}h{w - 2 * r}a{r} {r} 0 0 1 {r} {r}v{h - 2 * r}a{r} {r} 0 0 1 {-r} {r}"
                f"h{-(w - 2 * r)}a{r} {r} 0 0 1 {-r} {-r}v{-(h - 2 * r)}a{r} {r} 0 0 1 {r} {-r}Z")
    raise ValueError(f"unsupported element <{tag}>")


def parse_transform(text):
    t = Transform()
    for name, args in re.findall(r"(\w+)\(([^)]*)\)", text or ""):
        a = [float(v) for v in re.findall(r"-?[\d.]+(?:e-?\d+)?", args)]
        if name == "translate":
            t = t.translate(a[0], a[1] if len(a) > 1 else 0)
        elif name == "scale":
            t = t.scale(a[0], a[1] if len(a) > 1 else a[0])
        elif name == "rotate":
            if len(a) == 3:
                t = t.translate(a[1], a[2]).rotate(a[0] * 3.141592653589793 / 180).translate(-a[1], -a[2])
            else:
                t = t.rotate(a[0] * 3.141592653589793 / 180)
        elif name == "matrix":
            t = t.transform(a)
        else:
            raise ValueError(f"unsupported transform {name}")
    return t


def to_path(d, transform, fill_type=pathops.FillType.WINDING):
    p = pathops.Path(fillType=fill_type)
    parse_path(d, TransformPen(p.getPen(), transform))
    return p


def union(a, b):
    return pathops.op(a, b, pathops.PathOp.UNION, fix_winding=True)


def stroked(path, width):
    s = pathops.Path()
    s.addPath(path)
    s.stroke(width, pathops.LineCap.ROUND_CAP, pathops.LineJoin.ROUND_JOIN, 4)
    s.convertConicsToQuads(0.001)
    return s


def sprite_symbols(text):
    return {m.group(1): m.group(0) for m in re.finditer(r'<symbol id="([0-9a-f]{6})"[^>]*>.*?</symbol>', text)}


def glyph(symbols, ident):
    sym = symbols[ident]
    evenodd = 'fill-rule="evenodd"' in sym
    acc = pathops.Path()
    for m in re.finditer(r'<path( fill-rule="evenodd")? d="([^"]+)"', sym):
        ft = pathops.FillType.EVEN_ODD if (evenodd or m.group(1)) else pathops.FillType.WINDING
        part = to_path(m.group(2), Transform(), ft)
        part.simplify(fix_winding=True)
        acc = union(acc, part)
    return acc


def build_shape(src, symbols):
    root = ET.parse(src).getroot()
    acc = pathops.Path()
    for el in root.iter():
        if el is root:
            continue
        tag = el.tag.split("}")[-1]
        t = parse_transform(el.get("transform"))
        cls = el.get("class", "")
        if tag == "use":
            ref = (el.get("href") or el.get("{http://www.w3.org/1999/xlink}href")).lstrip("#")
            acc = union(acc, glyph(symbols, ref).transform(*t))
            continue
        d = shape_d(el)
        area = to_path(d, t)
        area.simplify(fix_winding=True)
        if cls == "cut":
            region = area
            if el.get("stroke-width"):
                region = union(region, stroked(to_path(d, t), float(el.get("stroke-width"))))
            acc = pathops.op(acc, region, pathops.PathOp.DIFFERENCE, fix_winding=True)
        elif cls == "fill":
            acc = union(acc, area)
        else:
            part = stroked(to_path(d, t), float(el.get("stroke-width", STROKE)))
            if el.get("fill", "none") != "none":
                part = union(part, area)
            acc = union(acc, part)
    acc.simplify(fix_winding=True)
    x0, y0, x1, y1 = acc.bounds
    lo, hi = LIVE_AREA
    if min(x0, y0) < lo or max(x1, y1) > hi:
        raise SystemExit(f"{src.name}: bounds {acc.bounds} leave the {LIVE_AREA} live area")
    pen = CubicPathPen(None, ntos=lambda v: f"{v:.4f}".rstrip("0").rstrip("."))
    acc.draw(pen)
    return root, pen.getCommands()


def svgo(paths):
    """Compact every path with svgo in one run; returns {id: d}."""
    body = "".join(f'<path id="p{i}" d="{d}"/>' for i, d in paths.items())
    config = ("export default { multipass: true, plugins: [{ name: 'convertPathData', params: "
              "{ floatPrecision: 3, convertToQ: false, makeArcs: { threshold: 2.5, tolerance: 0.5 } } }] };")
    with tempfile.TemporaryDirectory() as tmp:
        (Path(tmp) / "in.svg").write_text(f'<svg xmlns="http://www.w3.org/2000/svg">{body}</svg>')
        (Path(tmp) / "svgo.config.mjs").write_text(config)
        subprocess.run(["npx", "--yes", SVGO, "--config", "svgo.config.mjs", "-i", "in.svg", "-o", "out.svg", "--quiet"],
                       cwd=tmp, check=True)
        out = (Path(tmp) / "out.svg").read_text()
    return {m.group(1): m.group(2) for m in re.finditer(r'<path id="p([0-9a-f]{6})" d="([^"]+)"', out)}


def meta_line(ident, name, category, tags):
    return f'      "{ident}": {{ name: "{name}", category: "{category}", tags: {json.dumps(tags, separators=(", ", ": "))} }},'


def write_meta(html, ident, line, category):
    existing = re.compile(rf'^      "{ident}": .*$', re.M)
    if existing.search(html):
        return existing.sub(lambda _: line, html, count=1)
    group = re.search(rf"^      // {category}\n", html, re.M)
    if not group:
        later = next(c for c in CATEGORIES[CATEGORIES.index(category) + 1:] if re.search(rf"^      // {c}\n", html, re.M))
        at = re.search(rf"^      // {later}\n", html, re.M).start()
        html = html[:at] + f"      // {category}\n" + html[at:]
        group = re.search(rf"^      // {category}\n", html, re.M)
    end = re.compile(r"^      (// |};)", re.M).search(html, group.end()).start()
    return html[:end] + line + "\n" + html[end:]


def check_sprite(sprite, html):
    ids = re.findall(r'<symbol id="([^"]+)"', sprite)
    meta = dict(re.findall(r'"([0-9a-f]{6})": \{ name: "([^"]+)"', html))
    problems = [f"bad id {i}" for i in ids if not re.fullmatch(r"[0-9a-f]{6}", i)]
    problems += [f"duplicate id {i}" for i in set(ids) if ids.count(i) > 1]
    problems += ["symbols are not sorted by id"] if ids != sorted(ids) else []
    problems += [f"{i} has no metadata" for i in ids if i not in meta]
    problems += [f"{i} has metadata but no symbol" for i in meta if i not in ids]
    problems += [f"{i} is still unnamed" for i, n in meta.items() if n.startswith("Icon ")]
    return problems


def main():
    check = "--check" in sys.argv
    sprite, html = SPRITE.read_text(), INDEX.read_text()
    symbols = sprite_symbols(sprite)
    taken = set(symbols)
    built, metas = {}, {}
    for src in sorted(SRC.glob("*.svg")):
        root, d = build_shape(src, symbols)
        ident = root.get("data-id")
        if not ident:
            if check:
                raise SystemExit(f"{src.name}: no data-id, run the build first")
            ident = next(i for i in (f"{random.randrange(16 ** 6):06x}" for _ in iter(int, 1)) if i not in taken)
            text = src.read_text()
            src.write_text(text.replace("<svg ", f'<svg data-id="{ident}" ', 1))
        taken.add(ident)
        category = root.get("data-category", "UI")
        if category not in CATEGORIES:
            raise SystemExit(f"{src.name}: unknown category {category}")
        built[ident] = d
        metas[ident] = (meta_line(ident, src.stem, category, root.get("data-tags", src.stem.replace("-", " ")).split()), category)
    if len(set(m[0].split('name: "')[1].split('"')[0] for m in metas.values())) != len(metas):
        raise SystemExit("two sources share a name")

    for ident, d in svgo(built).items():
        symbols[ident] = f'<symbol id="{ident}" viewBox="0 0 20 20"><path d="{d}"/></symbol>'
    head, tail = sprite.split("\n", 1)[0], "\n</svg>"
    new_sprite = head + "\n" + "\n".join(symbols[i] for i in sorted(symbols)) + tail
    new_html = html
    for ident, (line, category) in metas.items():
        new_html = write_meta(new_html, ident, line, category)

    problems = check_sprite(new_sprite, new_html)
    if check:
        problems += ["assets/icons.svg is stale"] if new_sprite != sprite else []
        problems += ["index.html is stale"] if new_html != html else []
    if problems:
        raise SystemExit("\n".join(problems))
    if not check:
        SPRITE.write_text(new_sprite)
        INDEX.write_text(new_html)
    print(f"{len(built)} source icons, {len(symbols)} symbols: ok")


if __name__ == "__main__":
    main()
