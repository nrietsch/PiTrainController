"""
Builds CS2 track-diagram pages (gleisbild.cs2 + gleisbilder/<page>.cs2) from
the track items in a Rocrail plan.xml, so CS2 clients such as TrainControl can
show the layout. One way, read-only, like rocrail_plan.py.

Tile geometry comes from TrainControl's own port table (automationui/
TilePorts.java): at rotation 0 a straight connects E-W, a curve E-S, a buffer
has its stub at N, and a switch has its toe at S with the straight leg to N
(a left switch branches to W, a right switch to E). A rotation of n
(`.drehung`) turns the tile n quarter turns counter-clockwise.

Rather than trusting Rocrail's orientation attributes, the rotation of curves,
buffers and switches is derived from which neighbouring cells connect to them.
Rocrail's own `ori` is only a fallback where the neighbours don't settle it.

Mapping:
- tk straight / curve / buffer, fb (s88kontakt), sw left/right: one cell each.
- bk (block): a run of straights, 2 cells for a small symbol, 4 otherwise
  (along y if the block is oriented north/south).
- Everything else (signals, outputs, text, routes, ...) is not exported.
- One page per Rocrail level (z); coordinates are shifted so the layout starts
  at 0,0.
"""

from __future__ import annotations

import logging
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass

log = logging.getLogger("pitraincontroller.cs2web")

SIDES = "NESW"  # clockwise
_DELTA = {"N": (0, -1), "E": (1, 0), "S": (0, 1), "W": (-1, 0)}

# Fallbacks from Rocrail's `ori`, calibrated on the user's test plan.
_CURVE_BY_ORI = {"east": "NE", "south": "NW", "west": "SW", "north": "SE"}
_BUFFER_SIDE_BY_ORI = {"north": "N", "east": "E", "south": "S", "west": "W"}


def _opposite(side: str) -> str:
    return SIDES[(SIDES.index(side) + 2) % 4]


def _ccw(side: str, quarter_turns: int) -> str:
    return SIDES[(SIDES.index(side) - quarter_turns) % 4]


@dataclass(frozen=True)
class Element:
    x: int
    y: int
    typ: str
    rotation: int
    artikel: int


@dataclass(frozen=True)
class Page:
    name: str
    elements: tuple[Element, ...]


@dataclass
class _Cell:
    kind: str  # straight | feedback | curve | buffer | switch
    ori: str = ""
    sw_type: str = ""
    address: int = -1
    ports: frozenset[str] | None = None  # sides it connects on; None until resolved
    toe: str = ""  # switches only
    branch: str = ""  # switches only


def _int(value: str | None, default: int = 0) -> int:
    try:
        return int(value) if value is not None else default
    except ValueError:
        return default


def _vertical(ori: str) -> bool:
    return ori in ("north", "south")


def _line_ports(ori: str) -> frozenset[str]:
    return frozenset("NS" if _vertical(ori) else "EW")


def _page_name(name: str, z: int) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9 _.\-]", "", name).strip()
    return cleaned or f"Level {z}"


def parse_pages(xml_text: str) -> list[Page]:
    root = ET.fromstring(xml_text)

    titles: dict[int, str] = {}
    for index, level in enumerate(root.iterfind("./zlevel")):
        titles[_int(level.get("z"), index)] = level.get("title") or ""

    levels: dict[int, dict[tuple[int, int], _Cell]] = {}

    def put(z: int, x: int, y: int, cell: _Cell) -> None:
        grid = levels.setdefault(z, {})
        if (x, y) in grid:
            log.warning("Rocrail plan has two items at %d,%d (level %d); keeping the first", x, y, z)
            return
        grid[(x, y)] = cell

    for tk in root.iterfind("./tklist/tk"):
        z, x, y, ori = _int(tk.get("z")), _int(tk.get("x")), _int(tk.get("y")), tk.get("ori") or ""
        kind = {"straight": "straight", "curve": "curve", "buffer": "buffer"}.get(tk.get("type") or "")
        if kind is None:
            log.warning("Rocrail track %s has unsupported type %r; drawing a straight", tk.get("id"), tk.get("type"))
            kind = "straight"
        put(z, x, y, _Cell(kind, ori=ori, ports=_line_ports(ori) if kind == "straight" else None))

    for fb in root.iterfind("./fblist/fb"):
        z, x, y, ori = _int(fb.get("z")), _int(fb.get("x")), _int(fb.get("y")), fb.get("ori") or ""
        put(z, x, y, _Cell("feedback", ori=ori, address=_int(fb.get("addr"), -1), ports=_line_ports(ori)))

    for bk in root.iterfind("./bklist/bk"):
        z, x, y, ori = _int(bk.get("z")), _int(bk.get("x")), _int(bk.get("y")), bk.get("ori") or ""
        length = 2 if bk.get("smallsymbol") == "true" else 4
        for i in range(length):
            dx, dy = (0, i) if _vertical(ori) else (i, 0)
            put(z, x + dx, y + dy, _Cell("straight", ori=ori, ports=_line_ports(ori)))

    for sw in root.iterfind("./swlist/sw"):
        z, x, y = _int(sw.get("z")), _int(sw.get("x")), _int(sw.get("y"))
        sw_type = sw.get("type") or ""
        if sw_type not in ("left", "right"):
            log.warning("Rocrail switch %s has unsupported type %r; drawing a straight", sw.get("id"), sw_type)
            put(z, x, y, _Cell("straight", ports=frozenset("EW")))
            continue
        put(z, x, y, _Cell("switch", sw_type=sw_type, address=_int(sw.get("addr1"), 0)))

    pages: list[Page] = []
    for z in sorted(levels):
        grid = levels[z]
        _resolve(grid)
        min_x = min(x for x, _ in grid)
        min_y = min(y for _, y in grid)
        elements = tuple(
            _element(x - min_x, y - min_y, cell)
            for (x, y), cell in sorted(grid.items(), key=lambda item: (item[0][1], item[0][0]))
        )
        pages.append(Page(_page_name(titles.get(z, ""), z), elements))
    return pages


def _accepting_sides(grid: dict[tuple[int, int], _Cell], x: int, y: int) -> list[str]:
    """Sides of (x, y) whose neighbouring cell would connect toward it."""
    sides = []
    for side in SIDES:
        dx, dy = _DELTA[side]
        neighbour = grid.get((x + dx, y + dy))
        if neighbour is None:
            continue
        if neighbour.ports is None or _opposite(side) in neighbour.ports:
            sides.append(side)
    return sides


def _resolve(grid: dict[tuple[int, int], _Cell]) -> None:
    for (x, y), cell in grid.items():
        if cell.kind == "curve":
            sides = _accepting_sides(grid, x, y)
            if len(sides) == 2 and sides[0] != _opposite(sides[1]):
                cell.ports = frozenset(sides)
            else:
                log.warning("curve at %d,%d has %d connecting neighbours; using Rocrail's orientation", x, y, len(sides))
                cell.ports = frozenset(_CURVE_BY_ORI.get(cell.ori, "NE"))
        elif cell.kind == "buffer":
            sides = _accepting_sides(grid, x, y)
            cell.ports = frozenset(sides[0] if len(sides) == 1 else _BUFFER_SIDE_BY_ORI.get(cell.ori, "W"))

    for (x, y), cell in grid.items():
        if cell.kind == "switch":
            _resolve_switch(grid, x, y, cell)


def _resolve_switch(grid: dict[tuple[int, int], _Cell], x: int, y: int, cell: _Cell) -> None:
    """
    Work out the toe and branch from the neighbours: with three connecting
    sides, the one without an opposite is the branch, and the branch tile's
    other connection says which way the diverging route leans, so the toe is on
    the opposite end of the straight axis.
    """
    sides = _accepting_sides(grid, x, y)
    toe = branch = None
    odd = [s for s in sides if _opposite(s) not in sides]
    if len(sides) == 3 and len(odd) == 1:
        branch = odd[0]
        dx, dy = _DELTA[branch]
        neighbour = grid[(x + dx, y + dy)]
        if neighbour.ports is not None and len(neighbour.ports) == 2:
            (leans,) = neighbour.ports - {_opposite(branch)}
            if leans in sides and leans != branch:
                toe = _opposite(leans)
    if toe is None or branch is None:
        toe = "W"
        branch = "S" if cell.sw_type == "right" else "N"
        log.warning("switch at %d,%d: the layout doesn't settle its direction; assuming the toe is west", x, y)
    cell.toe, cell.branch = toe, branch
    cell.ports = frozenset({toe, _opposite(toe), branch})


def _element(x: int, y: int, cell: _Cell) -> Element:
    ports = cell.ports or frozenset()
    if cell.kind == "straight":
        return Element(x, y, "gerade", 1 if "N" in ports else 0, -1)
    if cell.kind == "feedback":
        return Element(x, y, "s88kontakt", 1 if "N" in ports else 0, cell.address)
    if cell.kind == "buffer":
        (stub,) = ports
        return Element(x, y, "prellbock", (SIDES.index("N") - SIDES.index(stub)) % 4, -1)
    if cell.kind == "curve":
        for rotation in range(4):
            if frozenset({_ccw("E", rotation), _ccw("S", rotation)}) == ports:
                return Element(x, y, "bogen", rotation, -1)
        return Element(x, y, "bogen", 0, -1)
    rotation = (SIDES.index("S") - SIDES.index(cell.toe)) % 4
    typ = "linksweiche" if cell.branch == _ccw("W", rotation) else "rechtsweiche"
    return Element(x, y, typ, rotation, cell.address * 2)


def build_gleisbild_cs2(pages: list[Page]) -> str:
    lines = ["[gleisbild]", "version", " .major=1", "groesse"]
    if pages:
        lines += ["zuletztBenutzt", f" .name={pages[0].name}"]
    for index, page in enumerate(pages, start=1):
        lines += ["seite", f" .id={index}", f" .name={page.name}"]
    return "\n".join(lines) + "\n"


def build_page_cs2(page: Page, page_id: int = 1) -> str:
    lines = ["[gleisbildseite]", f"page={page_id}", "version", " .major=1"]
    for e in page.elements:
        lines += ["element", f" .id=0x1{e.y:02x}{e.x:02x}", f" .typ={e.typ}"]
        if e.rotation:
            lines.append(f" .drehung={e.rotation}")
        lines.append(f" .artikel={e.artikel}")
    return "\n".join(lines) + "\n"
