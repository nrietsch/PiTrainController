from __future__ import annotations

import json
import threading
import urllib.request
from pathlib import Path

import pytest

from pitraincontroller.gateway.webconfig import default_body, make_server

FIXTURE = Path(__file__).parent / "fixtures" / "rocrail_plan_sample.xml"
DCC_BASE = 0xC000


def _is_cs3(geraet_vrs: bytes) -> bool:
    """Mirror of TrainControl's CS2File.isCS3: any line containing this text."""
    return any("Central Station 3" in line for line in geraet_vrs.decode().splitlines())


def test_station_type_detection_matches_trainControl():
    assert not _is_cs3(default_body("/config/geraet.vrs", "cs2"))
    assert _is_cs3(default_body("/config/geraet.vrs", "cs3"))
    assert not _is_cs3(default_body("/config/geraet.vrs"))


@pytest.fixture()
def make(tmp_path):
    servers = []

    def _make(plan: bool, station: str = "cs2"):
        plan_path = None
        if plan:
            p = tmp_path / "plan.xml"
            p.write_text(FIXTURE.read_text())
            plan_path = str(p)
        root = tmp_path / ("root_" + str(len(servers)))
        root.mkdir()
        srv = make_server(0, str(root), host="127.0.0.1", plan_path=plan_path, station=station)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        servers.append(srv)
        return srv

    yield _make
    for srv in servers:
        srv.shutdown()
        srv.server_close()


def _get(srv, path):
    with urllib.request.urlopen(f"http://127.0.0.1:{srv.server_address[1]}{path}", timeout=3) as r:
        return r.headers.get("Content-Type"), r.read()


def test_cs3_server_announces_itself_in_geraet_vrs(make):
    _, body = _get(make(plan=False, station="cs3"), "/config/geraet.vrs")
    assert _is_cs3(body)
    _, body = _get(make(plan=False, station="cs2"), "/config/geraet.vrs")
    assert not _is_cs3(body)


def test_lists_are_empty_json_arrays_without_a_plan(make):
    srv = make(plan=False)
    for path in ("/app/api/locos", "/app/api/mags", "/app/api/automatics"):
        content_type, body = _get(srv, path)
        assert content_type == "application/json"
        assert json.loads(body) == []


def test_locos_json_has_the_fields_trainControl_reads(make):
    _, body = _get(make(plan=True), "/app/api/locos")
    locos = {loco["name"]: loco for loco in json.loads(body)}
    assert set(locos) == {"BR260", "BR103"}
    br103 = locos["BR103"]
    # TrainControl reads these as strings/ints and subtracts the protocol base from uid
    assert int(br103["uid"], 0) - DCC_BASE == 15
    assert "dcc" in br103["dectyp"]
    assert isinstance(br103["icon"], str) and br103["internname"] == "BR103"
    assert len(br103["funktionen"]) == 32
    for f in br103["funktionen"]:
        assert {"typ", "typ2", "dauer", "isMoment"} <= f.keys()
        assert isinstance(f["typ"], int) and isinstance(f["isMoment"], bool)


def test_mags_json_has_ids(make):
    _, body = _get(make(plan=True), "/app/api/mags")
    mags = json.loads(body)
    assert [(m["id"], m["name"]) for m in mags] == [(1, "sw1"), (2, "sw2")]


def test_cs2_files_still_served_in_cs3_mode(make):
    srv = make(plan=True, station="cs3")
    _, body = _get(srv, "/config/gleisbild.cs2")
    assert b"Level 0" in body
    _, body = _get(srv, "/config/magnetartikel.cs2")
    assert b"sw1" in body
