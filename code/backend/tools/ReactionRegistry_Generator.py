#!/usr/bin/env python3
"""
Generates data/reaction_registry.json (read by Godot's ReactionRegistry,
see backend/data_synchronizer.gd) from the actual reaction source of truth
on the Python side.

Nothing about "which reactions exist" or "which engine runs them" is
hand-maintained anywhere - it's discovered from the filesystem:

  - Cantera:  one simulation<ReactionId>.py per reaction (e.g.
              simulationNaBr2.py -> reaction "NaBr2"). Every such file
              becomes one registry entry, engineId = "WebSocket Cantera".
  - Reaktoro: one generic engine handles every "Aqueous:"-prefixed
              reaction (see reaktoro_engine.py) - a single fixed entry,
              no per-reaction file to scan.

The only thing that IS hand-maintained is glow strength (reactionStrength),
since that's a VFX tuning value with no natural home in either the Cantera
mechanism YAMLs (pure chemistry, parsed by Cantera itself) or Reaktoro
(which has no per-reaction file at all). It lives in a small separate file,
reaction_meta.yaml, keyed by the same reaction id / prefix used above.
Reactions missing from it simply don't glow (reactionStrength = 0.0) until
someone adds a line - no other data is required to add a reaction.

Also exported: the list of reagent names Reaktoro understands (the keys of
REAGENT_FORMULAS in reaktoro_engine.py), as top-level "aqueousReagents" in
the JSON. This used to be duplicated by hand as AQUEOUS_REAGENT_NAMES in
Godot's reaction_data.gd - now it's read straight out of reaktoro_engine.py
(via `ast`, without importing it - this script shouldn't need the `reaktoro`
package installed just to read a Python dict literal) so there is exactly
one place that list is written.

CONFIG below (ENGINE_SOURCES) is a guess at your folder layout, based on
the reaktoro_engine.py docstring (simulation_hub.py / simulationNaBr2.py /
reaktoro_hub.py) - please adjust the paths to match reality.

Extending with a new chemistry engine:
  - "one file per reaction" style (like Cantera): add a "per_reaction"
    source with its script folder + filename pattern.
  - "one instance handles everything" style (like Reaktoro): add a
    "generic_prefix" source with the whatReaction prefix it owns.
No other code needs to change either way.

Usage:
    python tools/generate_reaction_registry.py \
        --out ../godot_project/data/reaction_registry.json
"""

import argparse
import ast
import json
import re
import sys
from pathlib import Path

import yaml

# ── CONFIG - adjust to your actual repo layout ───────────────────────────────
#
# Everything below is relative to REPO_ROOT, not to the current working
# directory - so `python3 backend/tools/generate_reaction_registry.py` works
# the same whether you run it from the repo root, from backend/tools/, or
# from a git hook / CI job with a different cwd.
#
# Assumed monorepo layout (adjust SCRIPT_DIR's parents below if this script
# lives somewhere else):
#   repo/code/
#     backend/
#       Cantera/simulation<Id>.py   <- one file per Cantera reaction
#       Reaktoro/reaktoro_engine.py <- one generic engine, no per-reaction files
#       tools/ReactionRegistry_Generator.py <- this script
#       tools/reaction_meta.yaml            <- hand-curated glow strengths
#     godot_project_VR_Chemistry_Lab/
#       data/reaction_registry.json         <- generated output

SCRIPT_DIR = Path(__file__).resolve().parent          # .../backend/tools
REPO_ROOT = SCRIPT_DIR.parent.parent                   # .../repo

ENGINE_SOURCES = [
    {
        "kind": "per_reaction",
        "engineId": "WebSocket Cantera",
        "scriptDir": REPO_ROOT / "backend" / "Cantera",
        "scriptGlob": "simulation*.py",
        # reaction id = filename with "simulation" prefix / ".py" suffix stripped.
        # (?!_) excludes helper/hub files like "simulation_hub.py" - only an
        # underscore right after "simulation" excludes a file; further
        # underscores inside the id itself (if you ever have one) are fine.
        "idPattern": re.compile(r"^simulation(?!_)(.+)\.py$"),
    },
    {
        "kind": "generic_prefix",
        "engineId": "WebSocket Reaktoro",
        "reactionKey": "Aqueous:",
    },
    # Add further engines here, e.g.:
    # {
    #     "kind": "per_reaction",
    #     "engineId": "WebSocket Phreeqc",
    #     "scriptDir": REPO_ROOT / "backend" / "engineName" / ...,
    #     "scriptGlob": "simulation*.py",
    #     "idPattern": re.compile(r"^simulation(?!_)(.+)\.py$"),
    # },
]

DEFAULT_META_PATH = SCRIPT_DIR / "reaction_meta.yaml"
DEFAULT_OUT_PATH = REPO_ROOT / "godot_project_VR_Chemistry_Lab" / "data" / "reaction_registry.json"

REACTION_DEFINITIONS_DIR = ( REPO_ROOT / "backend" / "Cantera" / "reaction_definitions" )

# Where REAGENT_FORMULAS lives - its keys become "aqueousReagents" in the JSON.
REAKTORO_ENGINE_PATH = REPO_ROOT / "backend" / "Reaktoro" / "reaktoro_engine.py"


# ── discovery ─────────────────────────────────────────────────────────────

# Helper/hub scripts like "simulation_hub.py" - matched separately from
# idPattern so they're skipped silently (expected), not with a warning.
_NOT_A_REACTION_PATTERN = re.compile(r"^simulation_")

def _discoverPerReactionIds(source: dict) -> list:
    scriptDir: Path = source["scriptDir"]
    if not scriptDir.is_dir():
        print(f"warning: {scriptDir} does not exist, skipping {source['engineId']}", file=sys.stderr)
        return []

    ids = []
    for scriptPath in sorted(scriptDir.glob(source["scriptGlob"])):
        if _NOT_A_REACTION_PATTERN.match(scriptPath.name):
            continue  # e.g. simulation_hub.py - not a reaction, nothing to warn about
        match = source["idPattern"].match(scriptPath.name)
        if match is None:
            print(f"warning: '{scriptPath.name}' doesn't match {source['idPattern'].pattern}, skipping", file=sys.stderr)
            continue
        ids.append(match.group(1))
    return ids

def _discoverReactionParticipants(
    reactionId: str,
    reactionDefinitionsDir: Path,
) -> tuple[list[str], list[str]]:
    """
    Reads

        reaction_definitions/<reactionId>.yaml

    and extracts the reactants/products from the first reaction equation.

    Example:

        reactions:
          - equation: 2 Na + Br2 <=> 2 NaBr

    ->
        (["Na", "Br2"], ["NaBr"])
    """

    yamlPath = reactionDefinitionsDir / f"{reactionId}.yaml"

    if not yamlPath.is_file():
        print(
            f"warning: reaction definition {yamlPath} not found",
            file=sys.stderr,
        )
        return [], []

    text = yamlPath.read_text(encoding="utf-8")
    text = text.replace("\t", "    ")   # tag → 4 spaces
    data = yaml.safe_load(text) or {}

    reactions = data.get("reactions", [])

    if not reactions:
        return [], []

    equation = reactions[0].get("equation")

    if not equation:
        return [], []

    if "<=>" in equation:
        lhs, rhs = equation.split("<=>", 1)
    elif "=>" in equation:
        lhs, rhs = equation.split("=>", 1)
    elif "->" in equation:
        lhs, rhs = equation.split("->", 1)
    else:
        return [], []

    def parse_side(side: str) -> list[str]:
        species = []

        for token in side.split("+"):
            token = token.strip()

            # remove stoichiometric coefficient
            token = re.sub(r"^\d+(\.\d+)?\s*", "", token)

            if token:
                species.append(token)

        return species
    
    return parse_side(lhs), parse_side(rhs)


def _discoverAqueousReagents(reaktoroEnginePath: Path) -> list:
    """Reads the keys of REAGENT_FORMULAS out of reaktoro_engine.py via the
    `ast` module - NOT via import, since that file does `import reaktoro`,
    and this generator script shouldn't need that (heavy, C++-backed)
    package installed just to read a Python dict literal."""
    if not reaktoroEnginePath.is_file():
        print(f"warning: {reaktoroEnginePath} not found, aqueousReagents will be empty", file=sys.stderr)
        return []

    tree = ast.parse(reaktoroEnginePath.read_text(encoding="utf-8"), filename=str(reaktoroEnginePath))
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "REAGENT_FORMULAS" for target in node.targets
        ):
            reagentFormulas = ast.literal_eval(node.value)
            return sorted(reagentFormulas.keys())

    print(f"warning: REAGENT_FORMULAS not found in {reaktoroEnginePath}, aqueousReagents will be empty", file=sys.stderr)
    return []


def _buildEntries(sources: list, glowStrengths: dict) -> list:
    entries = []
    for source in sources:
        if source["kind"] == "per_reaction":
            for reactionId in _discoverPerReactionIds(source):
                reactants, products = _discoverReactionParticipants( reactionId, REACTION_DEFINITIONS_DIR, )
                entries.append({
                    "reactionKey": reactionId,
                    "isPrefix": False,
                    "engineId": source["engineId"],
                    "reactionStrength": float(glowStrengths.get(reactionId, 0.0)),
                    "reactants": reactants,
                    "products": products,
                })
        elif source["kind"] == "generic_prefix":
            key = source["reactionKey"]
            entries.append({
                "reactionKey": key,
                "isPrefix": True,
                "engineId": source["engineId"],
                "reactionStrength": float(glowStrengths.get(key, 0.0)),
            })
        else:
            raise ValueError(f"unknown source kind: {source['kind']}")

    entries.sort(key=lambda e: e["reactionKey"])
    return entries


def generate(sources: list, metaPath: Path, reaktoroEnginePath: Path, outPath: Path) -> None:
    glowStrengths = {}
    if metaPath.exists():
        with metaPath.open("r", encoding="utf-8") as f:
            glowStrengths = yaml.safe_load(f) or {}
    else:
        print(f"note: {metaPath} not found, all reactions default to reactionStrength 0.0 (no glow)", file=sys.stderr)

    entries = _buildEntries(sources, glowStrengths)
    aqueousReagents = _discoverAqueousReagents(reaktoroEnginePath)

    outPath.parent.mkdir(parents=True, exist_ok=True)
    with outPath.open("w", encoding="utf-8") as f:
        json.dump({"entries": entries, "aqueousReagents": aqueousReagents}, f, indent=2, ensure_ascii=False)
        f.write("\n")

    print(f"wrote {len(entries)} reaction entries and {len(aqueousReagents)} aqueous reagents to {outPath}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--meta",
        type=Path,
        default=DEFAULT_META_PATH,
        help=f"path to the hand-curated glow-strength file (default: {DEFAULT_META_PATH})",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=DEFAULT_OUT_PATH,
        help=f"output path for the generated JSON (default: {DEFAULT_OUT_PATH})",
    )
    parser.add_argument(
        "--reaktoro-engine",
        type=Path,
        default=REAKTORO_ENGINE_PATH,
        help=f"path to reaktoro_engine.py, source of REAGENT_FORMULAS (default: {REAKTORO_ENGINE_PATH})",
    )
    args = parser.parse_args()

    generate(ENGINE_SOURCES, args.meta, args.reaktoro_engine, args.out)


if __name__ == "__main__":
    main()