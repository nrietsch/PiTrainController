from __future__ import annotations

import threading
import urllib.error
import urllib.request

import pytest

from pitraincontroller.gateway.webconfig import default_body, make_server


def test_default_body_known_paths():
    assert default_body("/can/") is not None
    assert default_body("/can") == default_body("/can/")
    assert default_body("/config/gleisbild.cs2").startswith(b"[gleisbild]")
    assert default_body("/config/lokomotive.cs2").startswith(b"[lokomotive]")
    assert default_body("/config/geraet.vrs").startswith(b"[geraet]")


def test_default_body_unknown_path_is_none():
    assert default_body("/config/nonsense.cs2") is None
    assert default_body("/config/gleisbilder/anything.cs2") is None


@pytest.fixture()
def server(tmp_path):
    srv = make_server(0, str(tmp_path), host="127.0.0.1")
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    yield srv, tmp_path
    srv.shutdown()
    srv.server_close()


def _get(srv, path):
    url = f"http://127.0.0.1:{srv.server_address[1]}{path}"
    return urllib.request.urlopen(url, timeout=3)


def test_defaults_answer_200_with_no_files(server):
    srv, _ = server
    for path in ("/can/", "/config/gleisbild.cs2", "/config/lokomotive.cs2"):
        with _get(srv, path) as resp:
            assert resp.status == 200
            assert resp.read()


def test_real_file_overrides_default(server):
    srv, root = server
    (root / "config").mkdir()
    (root / "config" / "lokomotive.cs2").write_text("[lokomotive]\nREAL\n")
    with _get(srv, "/config/lokomotive.cs2") as resp:
        assert b"REAL" in resp.read()


def test_layout_file_served_from_disk_and_missing_is_404(server):
    srv, root = server
    (root / "config" / "gleisbilder").mkdir(parents=True)
    (root / "config" / "gleisbilder" / "main.cs2").write_text("[gleisbild]\n")
    with _get(srv, "/config/gleisbilder/main.cs2") as resp:
        assert resp.status == 200
    with pytest.raises(urllib.error.HTTPError) as err:
        _get(srv, "/config/gleisbilder/missing.cs2")
    assert err.value.code == 404


def test_path_traversal_does_not_escape_root(server):
    srv, root = server
    with pytest.raises(urllib.error.HTTPError) as err:
        _get(srv, "/../../../../etc/passwd")
    assert err.value.code in (400, 404)
