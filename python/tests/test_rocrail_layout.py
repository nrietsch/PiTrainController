from __future__ import annotations

import threading
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import pytest

from pitraincontroller.gateway.rocrail_layout import (
    SIDES,
    build_gleisbild_cs2,
    build_page_cs2,
    parse_pages,
)
from pitraincontroller.gateway.webconfig import make_server

FIXTURE = Path(__file__).parent / "fixtures" / "rocrail_plan_sample.xml"
DELTA = {"N": (0, -1), "E": (1, 0), "S": (0, 1), "W": (-1, 0)}

# What each CS2 tile connects at rotation 0, as documented in TrainControl's TilePorts
BASE_PORTS = {
    "gerade": "EW",
    "s88kontakt": "EW",
    "bogen": "ES",
    "prellbock": "N",
    "rechtsweiche": "SNE",
    "linksweiche": "SNW",
}


def _ports(typ: str, rotation: int) -> set[str]:
    """Rotation n turns the tile n quarter turns counter-clockwise."""
    return {SIDES[(SIDES.index(s) - rotation) % 4] for s in BASE_PORTS[typ]}


def _by_position(page):
    return {(e.x, e.y): e for e in page.elements}


def test_sample_plan_gives_one_page_with_the_expected_tiles():
    (page,) = parse_pages(FIXTURE.read_text())
    assert page.name == "Level 0"
    tiles = _by_position(page)
    # Top row (main line), x shifted so the layout starts at 0,0
    assert (tiles[(0, 0)].typ, tiles[(0, 0)].rotation) == ("prellbock", 3)  # stub east
    assert [tiles[(x, 0)].typ for x in (1, 2)] == ["gerade", "gerade"]  # bk1, a small block
    assert (tiles[(3, 0)].typ, tiles[(3, 0)].artikel) == ("s88kontakt", 1)  # fb1
    assert (tiles[(4, 0)].typ, tiles[(4, 0)].rotation, tiles[(4, 0)].artikel) == ("rechtsweiche", 3, 2)  # sw1
    assert (tiles[(5, 0)].typ, tiles[(5, 0)].artikel) == ("s88kontakt", 3)  # fb3
    assert (tiles[(9, 0)].typ, tiles[(9, 0)].rotation, tiles[(9, 0)].artikel) == ("linksweiche", 1, 4)  # sw2
    assert (tiles[(13, 0)].typ, tiles[(13, 0)].rotation) == ("prellbock", 1)  # stub west
    # Bottom row (loop)
    assert (tiles[(4, 1)].typ, tiles[(4, 1)].rotation) == ("bogen", 1)  # north-east curve
    assert (tiles[(9, 1)].typ, tiles[(9, 1)].rotation) == ("bogen", 2)  # west-north curve
    assert [tiles[(x, 1)].typ for x in (6, 7)] == ["gerade", "gerade"]  # bk2


def test_every_tile_connection_is_matched_by_its_neighbour():
    (page,) = parse_pages(FIXTURE.read_text())
    tiles = _by_position(page)
    for (x, y), tile in tiles.items():
        for side in _ports(tile.typ, tile.rotation):
            dx, dy = DELTA[side]
            neighbour = tiles.get((x + dx, y + dy))
            assert neighbour is not None, f"{tile.typ} at {x},{y} has an open {side} side"
            opposite = SIDES[(SIDES.index(side) + 2) % 4]
            assert opposite in _ports(neighbour.typ, neighbour.rotation), (
                f"{tile.typ} at {x},{y} and {neighbour.typ} at {x + dx},{y + dy} don't meet"
            )


def test_large_block_is_four_straights_and_vertical_block_runs_down():
    xml = (
        "<plan><bklist>"
        '<bk id="a" x="0" y="0" z="0"/>'
        '<bk id="b" x="0" y="1" z="0" ori="north" smallsymbol="true"/>'
        "</bklist></plan>"
    )
    (page,) = parse_pages(xml)
    tiles = _by_position(page)
    assert [tiles[(x, 0)].typ for x in range(4)] == ["gerade"] * 4
    assert (tiles[(0, 1)].typ, tiles[(0, 1)].rotation) == ("gerade", 1)
    assert (tiles[(0, 2)].typ, tiles[(0, 2)].rotation) == ("gerade", 1)


def test_levels_become_pages():
    xml = (
        '<plan><zlevel title="Ground" z="0"/><zlevel title="Upper!" z="1"/><fblist>'
        '<fb id="a" x="0" y="0" z="0" addr="1"/><fb id="b" x="0" y="0" z="1" addr="2"/>'
        "</fblist></plan>"
    )
    pages = parse_pages(xml)
    assert [p.name for p in pages] == ["Ground", "Upper"]
    assert "seite\n .id=2\n .name=Upper" in build_gleisbild_cs2(pages)


def test_page_file_uses_trainControl_coordinates_and_omits_zero_rotation():
    (page,) = parse_pages(FIXTURE.read_text())
    text = build_page_cs2(page)
    assert text.startswith("[gleisbildseite]\npage=1\nversion\n .major=1\n")
    assert "element\n .id=0x10000\n .typ=prellbock\n .drehung=3\n .artikel=-1\n" in text
    assert "element\n .id=0x10001\n .typ=gerade\n .artikel=-1\n" in text  # no .drehung line for rotation 0
    assert "element\n .id=0x10104\n .typ=bogen\n .drehung=1\n" in text  # x=4, y=1


@pytest.fixture()
def server(tmp_path):
    plan = tmp_path / "plan.xml"
    plan.write_text(FIXTURE.read_text())
    root = tmp_path / "root"
    root.mkdir()
    srv = make_server(0, str(root), host="127.0.0.1", plan_path=str(plan))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield srv
    srv.shutdown()
    srv.server_close()


def _get(srv, path):
    with urllib.request.urlopen(f"http://127.0.0.1:{srv.server_address[1]}{path}", timeout=3) as r:
        return r.read().decode()


def test_server_serves_master_and_page_from_the_plan(server):
    master = _get(server, "/config/gleisbild.cs2")
    assert "seite\n .id=1\n .name=Level 0" in master
    page = _get(server, "/config/gleisbilder/" + urllib.parse.quote("Level 0") + ".cs2")
    assert "[gleisbildseite]" in page and "rechtsweiche" in page


def test_unknown_page_is_404(server):
    with pytest.raises(urllib.error.HTTPError) as err:
        _get(server, "/config/gleisbilder/Nope.cs2")
    assert err.value.code == 404
