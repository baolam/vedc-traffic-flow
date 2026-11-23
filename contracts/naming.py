"""
EdgeFlow AI -- Canonical approach/direction display-name helper.

Approach IDs (e.g. "J1_N_IN", "TJ1_NORTH_IN", "MP1_NE_DIAG_IN") encode their meaning only in
the string itself -- there is no separate human-readable name field anywhere in the topology
schema. This module is the one place (per AGENTS.md's Schema Authority rule) that defines the
`<node>_<DIR>[_DIAG]_IN` convention, so every consumer (services/api, services/vision, demo/sim
scripts) calls into it instead of re-implementing its own string-splitting.

Deliberately permissive: an ID that doesn't follow this convention (SUMO edge ids like
"-132042183", grid lane ids like "A0A1", Mongo-style hex node ids...) is not an error -- those
topologies never used this convention, so parse_approach_id returns None and
default_display_name falls back to the raw id, unchanged from today's display behavior.
"""

import re
from dataclasses import dataclass
from typing import Dict, Optional

# Canonical short code (N/S/E/W/NE/NW/SE/SW) each spelling in the wild maps to -- topology
# authors have used both the single/double-letter form and the full word form (see
# junction.json / three_way_junction_v1.json: "TJ1_NORTH_IN").
_DIRECTION_TOKENS: Dict[str, str] = {
    "N": "N", "NORTH": "N",
    "S": "S", "SOUTH": "S",
    "E": "E", "EAST": "E",
    "W": "W", "WEST": "W",
    "NE": "NE", "NORTHEAST": "NE",
    "NW": "NW", "NORTHWEST": "NW",
    "SE": "SE", "SOUTHEAST": "SE",
    "SW": "SW", "SOUTHWEST": "SW",
}

# Longest tokens first so the alternation can't short-circuit on a shorter alias.
_APPROACH_ID_RE = re.compile(
    r"^(?P<node_id>.+)_(?P<direction>"
    + "|".join(sorted(_DIRECTION_TOKENS, key=len, reverse=True))
    + r")(?P<diag>_DIAG)?_IN$"
)

_VI_DIRECTION_LABELS: Dict[str, str] = {
    "N": "Bắc", "S": "Nam", "E": "Đông", "W": "Tây",
    "NE": "Đông Bắc", "NW": "Tây Bắc", "SE": "Đông Nam", "SW": "Tây Nam",
}


@dataclass(frozen=True)
class ApproachIdParts:
    """Result of successfully parsing the `<node>_<DIR>[_DIAG]_IN` convention."""
    node_id: str
    direction: str  # canonical short code: N, S, E, W, NE, NW, SE, SW
    diagonal: bool


def parse_approach_id(approach_id: str) -> Optional[ApproachIdParts]:
    """Parse the compass-approach naming convention. Returns None (never raises) when
    approach_id doesn't follow it -- e.g. a raw SUMO edge id or grid lane id."""
    if not approach_id:
        return None
    match = _APPROACH_ID_RE.match(approach_id)
    if not match:
        return None
    direction = _DIRECTION_TOKENS[match.group("direction")]
    return ApproachIdParts(
        node_id=match.group("node_id"), direction=direction, diagonal=bool(match.group("diag"))
    )


def default_display_name(approach_id: str, display_names: Optional[Dict[str, str]] = None) -> str:
    """The name to show a human for this approach.

    An explicit entry in `display_names` (a node's "approach_display_names" dict, when the
    topology author has set one) always wins. Otherwise derives a Vietnamese name from the
    compass convention when approach_id matches it, and falls back to the raw id unchanged
    when it doesn't -- never raises, so every topology (including SUMO-derived ones that never
    used this convention) keeps behaving exactly as it does today.
    """
    if display_names and approach_id in display_names:
        return display_names[approach_id]
    parts = parse_approach_id(approach_id)
    if parts is None:
        return approach_id
    label = f"Hướng {_VI_DIRECTION_LABELS[parts.direction]} vào"
    if parts.diagonal:
        label += " (chéo)"
    return label
