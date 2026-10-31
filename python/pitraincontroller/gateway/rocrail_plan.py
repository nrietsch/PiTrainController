"""
Builds CS2 config files from a Rocrail plan.xml, so CS2 clients (TrainControl's
"Sync w/ Central Station", the CS2 App, ...) see the locomotives and switches
defined in Rocrail without entering them twice. One way only: Rocrail is the
source of truth and plan.xml is only ever read, never written.

File format (CS2 "block" text, as parsed by TrainControl's CS2File): a block
name on its own line, then ` .key=value` lines, with repeated ` .funktionen`
sub-blocks of ` ..nr=` / ` ..typ=` for locomotive functions.

Mapping, with what is and isn't known:
- Locomotive: Rocrail `id` -> name, `addr` -> address, `prot` N or L -> dcc,
  M -> mm2. Other protocol codes are logged and treated as mm2 (the CS2
  default); the exact meaning of Rocrail's `prot` letters beyond these wasn't
  confirmed from Rocrail's docs. `fncnt` -> number of functions (1..32).
- Switch: Rocrail `id` -> name, `addr1` -> accessory id (ports are not
  mapped), `prot` N -> dcc, M or D (Rocrail's default) -> mm2, `type` right /
  left / threeway -> rechtsweiche / linksweiche / dreiwegweiche, anything else
  -> weiche.
- Signals, outputs, routes and blocks are not exported.
"""

from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
from dataclasses import dataclass

log = logging.getLogger("pitraincontroller.cs2web")

MAX_FUNCTIONS = 32
_UID_BASE = {"mm2": 0x0000, "mfx": 0x4000, "dcc": 0xC000}
_LOCO_KINDS = {"N": "dcc", "L": "dcc", "M": "mm2"}
_SWITCH_DECODERS = {"N": "dcc", "M": "mm2", "D": "mm2"}
_SWITCH_TYPES = {"right": "rechtsweiche", "left": "linksweiche", "threeway": "dreiwegweiche"}


@dataclass(frozen=True)
class Loco:
    name: str
    address: int
    kind: str
    functions: int


@dataclass(frozen=True)
class Switch:
    name: str
    address: int
    decoder: str
    kind: str


def _int(value: str | None) -> int | None:
    try:
        return int(value) if value is not None else None
    except ValueError:
        return None


def _clean(text: str) -> str:
    return " ".join(text.split())


def parse_plan(xml_text: str) -> tuple[list[Loco], list[Switch]]:
    root = ET.fromstring(xml_text)

    locos: list[Loco] = []
    for lc in root.iterfind("./lclist/lc"):
        name = _clean(lc.get("id") or "")
        address = _int(lc.get("addr"))
        if lc.get("active") == "false":
            continue
        if not name or address is None or address <= 0:
            log.warning("skipping Rocrail loco %r: no usable id/address", lc.get("id"))
            continue
        prot = lc.get("prot") or ""
        kind = _LOCO_KINDS.get(prot)
        if kind is None:
            log.warning("Rocrail loco %s has protocol %r; exporting as mm2", name, prot)
            kind = "mm2"
        functions = min(max(_int(lc.get("fncnt")) or 1, 1), MAX_FUNCTIONS)
        locos.append(Loco(name, address, kind, functions))

    switches: list[Switch] = []
    for sw in root.iterfind("./swlist/sw"):
        name = _clean(sw.get("id") or "")
        address = _int(sw.get("addr1"))
        if not name or address is None or address <= 0:
            log.warning("skipping Rocrail switch %r: no usable id/address", sw.get("id"))
            continue
        decoder = _SWITCH_DECODERS.get(sw.get("prot") or "", "mm2")
        kind = _SWITCH_TYPES.get(sw.get("type") or "", "weiche")
        switches.append(Switch(name, address, decoder, kind))

    return locos, switches


def build_lokomotive_cs2(locos: list[Loco], session_id: int = 1) -> str:
    lines = ["[lokomotive]", "version", " .minor=3", "session", f" .id={session_id}"]
    for loco in locos:
        lines += [
            "lokomotive",
            f" .uid=0x{_UID_BASE[loco.kind] + loco.address:x}",
            f" .name={loco.name}",
            f" .adresse=0x{loco.address:x}",
            f" .typ={loco.kind}",
        ]
        for nr in range(loco.functions):
            lines += [" .funktionen", f" ..nr={nr}", f" ..typ={1 if nr == 0 else 0}"]
    return "\n".join(lines) + "\n"


def build_magnetartikel_cs2(switches: list[Switch], session_id: int = 1) -> str:
    lines = ["[magnetartikel]", "version", " .minor=1", "session", f" .id={session_id}"]
    for sw in switches:
        lines += [
            "artikel",
            f" .id={sw.address}",
            f" .name={sw.name}",
            f" .typ={sw.kind}",
            f" .dectyp={sw.decoder}",
            " .stellung=0",
        ]
    return "\n".join(lines) + "\n"
