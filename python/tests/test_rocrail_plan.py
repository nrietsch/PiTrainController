from __future__ import annotations

import re
import threading
import urllib.request
from pathlib import Path

import pytest

from pitraincontroller.gateway.rocrail_plan import (
    build_lokomotive_cs2,
    build_magnetartikel_cs2,
    parse_plan,
)
from pitraincontroller.gateway.webconfig import make_server

FIXTURE = Path(__file__).parent / "fixtures" / "rocrail_plan_sample.xml"


def _parse_cs2(text: str) -> list[dict[str, str]]:
    """Mirror of the block parser in TrainControl's CS2File.parseFile, to check
    that what we write is what that reader understands."""
    items: list[dict[str, str]] = []
    item: dict[str, str] | None = None
    array: dict[str, str] = {}
    last = ""
    for line in text.splitlines() + ["__done"]:
        if re.fullmatch(r" \.\.[A-Za-z0-9]+=.+", line):
            key, value = line[3:].split("=", 1)
            array[key] = value
            continue
        if array and item is not None:
            entry = "{" + ",".join(f"{k}={v}" for k, v in array.items()) + "}"
            item[last] = item.get(last, "") + entry
            array = {}
        if re.fullmatch(r"[A-Za-z]+", line):
            item = {"_type": line.lower()}
            items.append(item)
        elif re.fullmatch(r" \.[A-Za-z0-9]+=.+", line):
            key, value = line[2:].split("=", 1)
            assert item is not None
            item[key] = value
        elif re.fullmatch(r" \.[A-Za-z0-9]+", line):
            last = line[2:]
    return items


def test_parse_sample_plan():
    locos, switches = parse_plan(FIXTURE.read_text())
    assert [(l.name, l.address, l.kind, l.functions) for l in locos] == [
        ("BR260", 5, "dcc", 4),
        ("BR103", 15, "dcc", 32),
    ]
    assert [(s.name, s.address, s.decoder, s.kind) for s in switches] == [
        ("sw1", 1, "mm2", "rechtsweiche"),
        ("sw2", 2, "mm2", "linksweiche"),
    ]


def test_lokomotive_file_is_readable_the_way_trainControl_reads_it():
    locos, _ = parse_plan(FIXTURE.read_text())
    items = [i for i in _parse_cs2(build_lokomotive_cs2(locos)) if i["_type"] == "lokomotive"]
    assert [i["name"] for i in items] == ["BR260", "BR103"]
    br103 = items[1]
    assert int(br103["adresse"], 0) == 15
    assert int(br103["uid"], 0) == 0xC000 + 15
    assert br103["typ"] == "dcc"
    assert br103["funktionen"].count("nr=") == 32
    assert br103["funktionen"].startswith("{nr=0,typ=1}")


def test_magnetartikel_file_is_readable_the_way_trainControl_reads_it():
    _, switches = parse_plan(FIXTURE.read_text())
    items = [i for i in _parse_cs2(build_magnetartikel_cs2(switches)) if i["_type"] == "artikel"]
    assert [(i["id"], i["name"], i["typ"]) for i in items] == [
        ("1", "sw1", "rechtsweiche"),
        ("2", "sw2", "linksweiche"),
    ]
    assert all("weiche" in i["typ"] and "dectyp" in i for i in items)


def test_unknown_protocol_falls_back_to_mm2():
    xml = '<plan><lclist><lc id="X" addr="3" prot="Z" fncnt="2"/></lclist></plan>'
    locos, _ = parse_plan(xml)
    assert locos[0].kind == "mm2"


def test_inactive_and_unusable_entries_are_skipped():
    xml = (
        "<plan><lclist>"
        '<lc id="off" addr="3" prot="N" active="false"/>'
        '<lc id="noaddr" addr="0" prot="N"/>'
        '<lc id="" addr="4" prot="N"/>'
        '<lc id="ok" addr="6" prot="M"/>'
        "</lclist></plan>"
    )
    locos, _ = parse_plan(xml)
    assert [l.name for l in locos] == ["ok"]


def test_function_count_is_clamped():
    xml = '<plan><lclist><lc id="a" addr="1" prot="N" fncnt="99"/><lc id="b" addr="2" prot="N" fncnt="0"/></lclist></plan>'
    locos, _ = parse_plan(xml)
    assert [l.functions for l in locos] == [32, 1]


@pytest.fixture()
def server(tmp_path):
    plan = tmp_path / "plan.xml"
    plan.write_text(FIXTURE.read_text())
    root = tmp_path / "root"
    root.mkdir()
    srv = make_server(0, str(root), host="127.0.0.1", plan_path=str(plan))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield srv, root, plan
    srv.shutdown()
    srv.server_close()


def _get(srv, path) -> bytes:
    with urllib.request.urlopen(f"http://127.0.0.1:{srv.server_address[1]}{path}", timeout=3) as r:
        return r.read()


def test_server_generates_from_plan(server):
    srv, _, _ = server
    assert b"BR103" in _get(srv, "/config/lokomotive.cs2")
    assert b"sw2" in _get(srv, "/config/magnetartikel.cs2")


def test_server_reflects_plan_changes_without_restart(server):
    srv, _, plan = server
    plan.write_text(FIXTURE.read_text().replace("BR103", "BR999"))
    body = _get(srv, "/config/lokomotive.cs2")
    assert b"BR999" in body and b"BR103" not in body


def test_real_file_on_disk_beats_the_plan(server):
    srv, root, _ = server
    (root / "config").mkdir()
    (root / "config" / "lokomotive.cs2").write_text("[lokomotive]\nFROMDISK\n")
    assert b"FROMDISK" in _get(srv, "/config/lokomotive.cs2")


def test_unreadable_plan_falls_back_to_default(server):
    srv, _, plan = server
    plan.write_text("this is not xml")
    body = _get(srv, "/config/lokomotive.cs2")
    assert body.startswith(b"[lokomotive]") and b"BR103" not in body
