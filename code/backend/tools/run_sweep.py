import argparse
import importlib.util
import itertools
import os
import re
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


# ---------------------------------------------------------------------------
# Fixed sweep keys and defaults
# ---------------------------------------------------------------------------

FIXED_SWEEP_KEYS = ("site_density", "A", "Ea")

DEFAULT_SWEEP_RANGES = {
    "site_density": {"start": 1.0e-5, "end": 1.0e-3, "steps": 5, "log_scale": True},
    "A":            {"start": 1.0e8,  "end": 1.0e10, "steps": 5, "log_scale": True},
    "Ea":           {"start": 10.0,   "end": 1.0e4,  "steps": 5, "log_scale": False},
}

DEFAULT_TEMPERATURES = [400, 600, 800, 1000, 1200]
DEFAULT_SIM_TIME     = 1.0     # seconds
DEFAULT_MAX_TIMESTEP = 1.0e-3  # seconds


# ---------------------------------------------------------------------------
# ParameterSweep
# ---------------------------------------------------------------------------

class ParameterSweep:
    def __init__(self, name, start, end, steps=5, log_scale=False, fixed_values = None):
        self.name      = name
        self.start     = start
        self.end       = end
        self.steps     = steps
        self.log_scale = log_scale
        self.fixed_values = fixed_values 

    def values(self):
        if self.fixed_values is not None:
            return np.array(self.fixed_values)
        if self.log_scale:
            return np.logspace(np.log10(self.start), np.log10(self.end), self.steps)
        return np.linspace(self.start, self.end, self.steps)


# ---------------------------------------------------------------------------
# Module loading
# ---------------------------------------------------------------------------

def load_module(path: str):
    path = os.path.abspath(path)
    if not os.path.isfile(path):
        sys.exit(f"Error: File not found: {path}")

    spec = importlib.util.spec_from_file_location("_target_sim", path)
    mod  = importlib.util.module_from_spec(spec)

    target_dir = os.path.dirname(path)
    if target_dir not in sys.path:
        sys.path.insert(0, target_dir)

    spec.loader.exec_module(mod)
    return mod


def get_attr(mod, name, default=None):
    return getattr(mod, name, default)


# ---------------------------------------------------------------------------
# Derive class and YAML path from the module
# ---------------------------------------------------------------------------

def get_sim_class(mod, module_path: str):
    """
    Class name == filename without .py, e.g.
    NaBrSimulation.py  ->  NaBrSimulation
    """
    class_name = os.path.splitext(os.path.basename(module_path))[0]
    cls = get_attr(mod, class_name)
    if cls is None:
        # fallback: find any class whose name ends with "Simulation"
        import inspect
        candidates = [
            obj for _, obj in inspect.getmembers(mod, inspect.isclass)
            if obj.__name__.endswith("Simulation") and obj.__module__ == "_target_sim"
        ]
        if not candidates:
            sys.exit(
                f"Error: Could not find class '{class_name}' in {module_path}.\n"
                f"Make sure the filename matches the class name."
            )
        cls = candidates[0]
        print(f"  Using class: {cls.__name__}")
    return cls


def get_yaml_path(sim_class, module_dir: str, max_timestep: float) -> str:
    """
    Instantiate the sim class with a dummy timestep to read self.YAML_PATH.
    Resolves the path relative to the module directory.
    """
    try:
        instance = sim_class(max_timestep)
    except Exception as e:
        sys.exit(f"Error instantiating {sim_class.__name__}: {e}")

    yaml_path = getattr(instance, "YAML_PATH", None)
    if not yaml_path:
        sys.exit(
            f"Error: {sim_class.__name__} does not set self.YAML_PATH in __init__."
        )

    if not os.path.isabs(yaml_path):
        yaml_path = os.path.join(module_dir, yaml_path)

    if not os.path.isfile(yaml_path):
        sys.exit(f"Error: YAML not found: {yaml_path}")

    return yaml_path


# ---------------------------------------------------------------------------
# Auto-detect species from YAML
# ---------------------------------------------------------------------------

def detect_species_from_yaml(yaml_path: str):
    """
    Reads species lists from the YAML and splits them into
    gas-phase and surface species based on which phase they belong to.
    Returns (gas_species, surface_species).
    """
    with open(yaml_path) as fh:
        text = fh.read()

    # find the gas phase species list
    gas_match = re.search(
        r"- name: gas.*?species:\s*\[([^\]]+)\]",
        text, re.DOTALL,
    )
    # find the surface phase species list
    surf_match = re.search(
        r"- name: surface.*?species:\s*\[([^\]]+)\]",
        text, re.DOTALL,
    )

    def parse_list(m):
        if not m:
            return []
        return [s.strip() for s in m.group(1).split(",") if s.strip()]

    gas_species  = parse_list(gas_match)
    surf_species = parse_list(surf_match)
    return gas_species, surf_species


# ---------------------------------------------------------------------------
# Build SWEEPS dict
# ---------------------------------------------------------------------------

SWEEP_LABELS = {
    "site_density": "site-density [mol/cm²]",
    "A":            "pre-exponential A",
    "Ea":           "activation energy Ea [J/mol]",
}

def build_sweeps(module_ranges: dict, steps_override: int = None) -> dict:
    sweeps = {}
    for key in FIXED_SWEEP_KEYS:
        cfg   = {**DEFAULT_SWEEP_RANGES[key], **module_ranges.get(key, {})}
        steps = steps_override if steps_override else cfg["steps"]
        sweeps[key] = ParameterSweep(
            name      = SWEEP_LABELS[key],
            start     = cfg["start"],
            end       = cfg["end"],
            steps     = steps,
            log_scale = cfg.get("log_scale", False),
            fixed_values = cfg.get("fixed_values", None),
        )
    return sweeps


# ---------------------------------------------------------------------------
# Baselines from YAML
# ---------------------------------------------------------------------------

YAML_KEY_MAP = {
    "site_density": ["site-density"],
    "A":            ["rate-constant.A", "A"],
    "Ea":           ["rate-constant.Ea", "Ea"],
}

def _parse_yaml_scalar(text: str, key: str):
    if "." in key:
        parent, child = key.split(".", 1)
        m = re.search(
            rf"^\s*{re.escape(parent)}:\s*\n((?:\s+.+\n)*)",
            text, re.MULTILINE,
        )
        return _parse_yaml_scalar(m.group(1), child) if m else None

    m = re.search(rf"^\s*{re.escape(key)}:\s*([^\n#]+)", text, re.MULTILINE)
    if not m:
        return None
    try:
        return float(m.group(1).strip())
    except ValueError:
        return None


def read_baselines_from_yaml(yaml_path: str) -> dict:
    with open(yaml_path) as fh:
        text = fh.read()

    baselines = {}
    for key in FIXED_SWEEP_KEYS:
        val = None
        for cand in YAML_KEY_MAP[key]:
            val = _parse_yaml_scalar(text, cand)
            if val is not None:
                break
        if val is None:
            sys.exit(
                f"Error: Could not read baseline for '{key}' from '{yaml_path}'.\n"
                f"Use --baseline {key}=<value> to set it manually."
            )
        baselines[key] = val
        print(f"  Baseline from YAML: {key} = {val:.4g}")

    return baselines


# ---------------------------------------------------------------------------
# YAML patching — patches site-density, A, Ea in-place
# ---------------------------------------------------------------------------

def _patch_yaml(original_path: str, sd: float, A: float, Ea: float,
                output_path: str) -> str:
    with open(original_path) as fh:
        text = fh.read()

    text = re.sub(
        r"(^\s*site-density:\s*)([^\n#]+)",
        rf"\g<1>{sd:.6e}",
        text, flags=re.MULTILINE,
    )
    text = re.sub(
        r"(^\s*A:\s*)([^\n#]+)",
        rf"\g<1>{A:.6e}",
        text, flags=re.MULTILINE,
    )
    text = re.sub(
        r"(^\s*Ea:\s*)([^\n#]+)",
        rf"\g<1>{Ea:.6e}",
        text, flags=re.MULTILINE,
    )

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    with open(output_path, "w") as fh:
        fh.write(text)
    return output_path


# ---------------------------------------------------------------------------
# Filename helpers
# ---------------------------------------------------------------------------

def _safe_str(val: float) -> str:
    return f"{val:.3e}".replace(".", "p").replace("e+", "ep").replace("e-", "em")


# ---------------------------------------------------------------------------
# Single combination runner
# ---------------------------------------------------------------------------

def _run_combination(
    sd, A, Ea,
    original_yaml, sim_class,
    gas_species, surface_species,
    start_temperatures, sim_time, max_timestep,
    output_path, title, tmp_yaml_dir,
):
    tmp_yaml = os.path.join(
        tmp_yaml_dir,
        f"tmp_{_safe_str(sd)}_{_safe_str(A)}_{_safe_str(Ea)}.yaml",
    )
    _patch_yaml(original_yaml, sd, A, Ea, tmp_yaml)

    all_runs = []
    for T0 in start_temperatures:
        try:
            sim = sim_class(max_timestep)
            sim.YAML_PATH = tmp_yaml   # point to patched YAML
            sim.init(T0)
            result = sim.runUntilTargetTime(sim_time)
            all_runs.append((f"{T0} K", result["dataBlockList"]))
        except Exception as e:
            print(f"    Error at T={T0} K: {e}")
            import traceback; traceback.print_exc()

    try:
        os.remove(tmp_yaml)
    except OSError:
        pass

    if not all_runs:
        print(f"  No results for: {title}")
        return

    _plot(all_runs, gas_species, surface_species, output_path, title)


# ---------------------------------------------------------------------------
# Plotting
# ---------------------------------------------------------------------------

def _plot(simulation_runs, gas_species, surface_species, output_path, title):
    n_extra = len(gas_species) + len(surface_species)
    n_cols  = 2
    n_rows  = 1 + max(1, (n_extra + n_cols - 1) // n_cols)

    fig, axes = plt.subplots(n_rows, n_cols, figsize=(12, 4 * n_rows))
    axes = np.array(axes).reshape(-1)
    fig.suptitle(title)

    for label, data in simulation_runs:
        if not data:
            continue
        t  = [r["timeStamp"]   for r in data]
        T0 = data[0]["temperature"]
        P0 = data[0]["pressure"]

        axes[0].plot(t, [r["temperature"] - T0 for r in data], label=label)
        axes[1].plot(t, [r["pressure"]    - P0 for r in data], label=label)

        for i, sp in enumerate(gas_species):
            key = sp if sp in data[0] else f"amount_of_{sp}"
            if key in data[0]:
                axes[2 + i].plot(t, [r[key] for r in data], label=label)

        for i, sp in enumerate(surface_species):
            key = (sp if sp in data[0]
                    else f"{sp}_surface" if f"{sp}_surface" in data[0]
                    else f"amount_of_{sp}")
            if key in data[0]:
                axes[2 + len(gas_species) + i].plot(t, [r[key] for r in data], label=label)

    # NEU: beide Kategorien liefern jetzt Stoffmengen in mol statt
    # Molenbruch (gas) bzw. Bedeckungsgrad (surface) -> einheitliches Label
    meta = (
        [("Temperature change", "ΔT [K]"), ("Pressure change", "ΔP [Pa]")]
        + [(f"{sp} (gas)",     "amount [mol]") for sp in gas_species]
        + [(f"{sp} (surface)", "amount [mol]") for sp in surface_species]
    )
    for ax, (ptitle, ylabel) in zip(axes, meta):
        ax.set_title(ptitle)
        ax.set_xlabel("t [s]")
        ax.set_ylabel(ylabel)
        ax.ticklabel_format(style="plain", axis="y", useOffset=False)
        ax.grid(True, alpha=0.3)
        ax.legend(fontsize=7)

    for ax in axes[len(meta):]:
        ax.set_visible(False)

    fig.tight_layout()
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {output_path}")


# ---------------------------------------------------------------------------
# Sweep runners
# ---------------------------------------------------------------------------

def run_single_sweeps(sweeps, baselines, sim_class, gas_species, surface_species,
                      original_yaml, start_temperatures, sim_time, max_timestep,
                      output_base, tmp_yaml_dir):
    for key, sweep in sweeps.items():
        print(f"\n{'='*60}\nSingle sweep: {sweep.name}\n{'='*60}")
        out_dir = os.path.join(output_base, "single", key)
        for val in sweep.values():
            sd = val if key == "site_density" else baselines["site_density"]
            A  = val if key == "A"            else baselines["A"]
            Ea = val if key == "Ea"           else baselines["Ea"]
            print(f"  {sweep.name} = {val:.3e}")
            _run_combination(
                sd, A, Ea, original_yaml, sim_class, gas_species, surface_species,
                start_temperatures, sim_time, max_timestep,
                os.path.join(out_dir, f"sweep_{key}_{_safe_str(val)}.png"),
                f"Single sweep  {sweep.name} = {val:.3e}",
                tmp_yaml_dir,
            )


def run_pairwise_sweeps(sweeps, baselines, sim_class, gas_species, surface_species,
                        original_yaml, start_temperatures, sim_time, max_timestep,
                        output_base, tmp_yaml_dir):
    keys = list(sweeps.keys())
    for key1, key2 in itertools.combinations(keys, 2):
        sweep1, sweep2 = sweeps[key1], sweeps[key2]
        fixed_key = [k for k in keys if k not in (key1, key2)][0]
        print(f"\n{'='*60}\nPairwise sweep: {sweep1.name} × {sweep2.name}\n{'='*60}")
        out_dir = os.path.join(output_base, "pairwise", f"{key1}_x_{key2}")

        for v1, v2 in itertools.product(sweep1.values(), sweep2.values()):
            params = {key1: v1, key2: v2, fixed_key: baselines[fixed_key]}
            short = f"{key1}_{_safe_str(v1)}__{key2}_{_safe_str(v2)}"
            print(f"  {short}")
            _run_combination(
                params["site_density"], params["A"], params["Ea"],
                original_yaml, sim_class, gas_species, surface_species,
                start_temperatures, sim_time, max_timestep,
                os.path.join(out_dir, f"sweep_{short}.png"),
                (f"Pairwise sweep\n"
                 f"{sweep1.name} = {v1:.3e},  {sweep2.name} = {v2:.3e}\n"
                 f"({fixed_key} = {baselines[fixed_key]:.3e})"),
                tmp_yaml_dir,
            )


def run_triple_sweep(sweeps, baselines, sim_class, gas_species, surface_species,
                     original_yaml, start_temperatures, sim_time, max_timestep,
                     output_base, tmp_yaml_dir):
    print(f"\n{'='*60}\nTriple sweep: site_density × A × Ea\n{'='*60}")
    out_dir = os.path.join(output_base, "triple")

    combos = list(itertools.product(
        sweeps["site_density"].values(),
        sweeps["A"].values(),
        sweeps["Ea"].values(),
    ))
    for i, (sd, A, Ea) in enumerate(combos, 1):
        short = f"sd{_safe_str(sd)}__A{_safe_str(A)}__Ea{_safe_str(Ea)}"
        print(f"  [{i}/{len(combos)}] {short}")
        _run_combination(
            sd, A, Ea, original_yaml, sim_class, gas_species, surface_species,
            start_temperatures, sim_time, max_timestep,
            os.path.join(out_dir, f"sweep_{short}.png"),
            f"Triple sweep\nsite_density={sd:.3e},  A={A:.3e},  Ea={Ea:.3e}",
            tmp_yaml_dir,
        )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser():
    p = argparse.ArgumentParser(
        description="Generic sweep runner — always sweeps site_density, A, Ea.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("module", help="Path to the simulation .py file")

    mode = p.add_argument_group("Sweep modes")
    mode.add_argument("--single",      action="store_true")
    mode.add_argument("--no-single",   action="store_true")
    mode.add_argument("--pairwise",    action="store_true")
    mode.add_argument("--no-pairwise", action="store_true")
    mode.add_argument("--triple",      action="store_true")
    mode.add_argument("--no-triple",   action="store_true")
    mode.add_argument("--all",         action="store_true",
                      help="Enable all three sweep modes")

    ov = p.add_argument_group("Overrides")
    ov.add_argument("--output",   metavar="PATH", help="Output directory")
    ov.add_argument("--steps",    type=int,  metavar="N",
                    help="Steps for all sweeps")
    ov.add_argument("--temps",    type=float, nargs="+", metavar="T",
                    help="Start temperatures")
    ov.add_argument("--time",     type=float, metavar="T",
                    help="Simulation time in seconds")
    ov.add_argument("--baseline", nargs="+", metavar="KEY=VAL",
                    help="Override a baseline, e.g.: --baseline Ea=500")
    ov.add_argument("--values", nargs="+", metavar="KEY=V1,V2,V3",
                help="Fix testing values, e.g.: --values A=1e8,5e8,1e9 Ea=200,500,1000")
    return p


def _parse_baseline_overrides(entries):
    result = {}
    for entry in (entries or []):
        if "=" not in entry:
            sys.exit(f"Error: --baseline expects KEY=VAL, got: '{entry}'")
        k, v = entry.split("=", 1)
        try:
            result[k.strip()] = float(v.strip())
        except ValueError:
            sys.exit(f"Error: Invalid float in '--baseline {entry}'")
    return result

def _parse_values_overrides(entries):
    result = {}
    for entry in (entries or []):
        if "=" not in entry:
            sys.exit(f"Error: --values expects KEY=V1,V2,V3, got: '{entry}'")
        k, v = entry.split("=", 1)
        try:
            result[k.strip()] = [float(x.strip()) for x in v.split(",")]
        except ValueError:
            sys.exit(f"Error: Invalid float in '--values {entry}'")
    return result

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = build_parser()
    args   = parser.parse_args()

    print(f"Loading module: {args.module}")
    mod        = load_module(args.module)
    module_dir = os.path.dirname(os.path.abspath(args.module))

    # --- Derive simulation class from filename ---
    sim_class = get_sim_class(mod, args.module)
    print(f"  Simulation class: {sim_class.__name__}")

    # --- Read YAML path from class instance ---
    max_timestep = get_attr(mod, "MAX_TIMESTEP", DEFAULT_MAX_TIMESTEP)
    original_yaml = get_yaml_path(sim_class, module_dir, max_timestep)
    print(f"  YAML path: {original_yaml}")

    # --- Species: from module or auto-detected from YAML ---
    gas_species     = get_attr(mod, "GAS_SPECIES")
    surface_species = get_attr(mod, "SURFACE_SPECIES")

    if gas_species is None or surface_species is None:
        print("  Auto-detecting species from YAML...")
        auto_gas, auto_surf = detect_species_from_yaml(original_yaml)
        gas_species     = gas_species     or auto_gas
        surface_species = surface_species or auto_surf
        print(f"  Gas species     : {gas_species}")
        print(f"  Surface species : {surface_species}")

    # --- Sweep ranges and steps ---
    module_ranges = get_attr(mod, "SWEEP_RANGES") or {}
    SWEEPS = build_sweeps(module_ranges, steps_override=args.steps)

    # --- Sweep modes ---
    RUN_SINGLE   = get_attr(mod, "RUN_SINGLE",   False)
    RUN_PAIRWISE = get_attr(mod, "RUN_PAIRWISE", False)
    RUN_TRIPLE   = get_attr(mod, "RUN_TRIPLE",   False)

    if args.all:         RUN_SINGLE = RUN_PAIRWISE = RUN_TRIPLE = True
    if args.single:      RUN_SINGLE   = True
    if args.no_single:   RUN_SINGLE   = False
    if args.pairwise:    RUN_PAIRWISE = True
    if args.no_pairwise: RUN_PAIRWISE = False
    if args.triple:      RUN_TRIPLE   = True
    if args.no_triple:   RUN_TRIPLE   = False

    # --- Optional parameters ---
    START_TEMPERATURES = get_attr(mod, "START_TEMPERATURES", DEFAULT_TEMPERATURES)
    SIMULATION_TIME    = get_attr(mod, "SIMULATION_TIME",    DEFAULT_SIM_TIME)
    OUTPUT_BASE        = get_attr(mod, "OUTPUT_BASE",  os.path.join(module_dir, "sweeps"))
    TMP_YAML_DIR       = get_attr(mod, "TMP_YAML_DIR", os.path.join(module_dir, "_tmp_sweep"))

    if args.temps:  START_TEMPERATURES = args.temps
    if args.time:   SIMULATION_TIME    = args.time
    if args.output: OUTPUT_BASE        = os.path.abspath(args.output)

    # --- Baselines ---
    print(f"\nReading baselines from YAML: {original_yaml}")
    BASELINES = read_baselines_from_yaml(original_yaml)
    BASELINES.update(_parse_baseline_overrides(args.baseline))

    # --- specific values --- 
    values_overrides = _parse_values_overrides(args.values)
    for key, vals in values_overrides.items():
        if key in SWEEPS:
            SWEEPS[key].fixed_values = vals
            SWEEPS[key].steps = len(vals)

    # --- Summary ---
    steps = [s.steps for s in SWEEPS.values()]
    n_single   = sum(s.steps for s in SWEEPS.values())
    n_pairwise = 3 * steps[0] * steps[1]
    n_triple   = steps[0] * steps[1] * steps[2]
    total = (
        (n_single   if RUN_SINGLE   else 0)
        + (n_pairwise if RUN_PAIRWISE else 0)
        + (n_triple   if RUN_TRIPLE   else 0)
    )

    print(f"\nConfiguration")
    print(f"  Module          : {args.module}")
    print(f"  Class           : {sim_class.__name__}")
    print(f"  YAML            : {original_yaml}")
    print(f"  Gas species     : {gas_species}")
    print(f"  Surface species : {surface_species}")
    print(f"  Baselines       : {BASELINES}")
    print(f"  Temperatures    : {START_TEMPERATURES}")
    print(f"  Simulation time : {SIMULATION_TIME} s")
    print(f"  Max timestep    : {max_timestep} s")
    print(f"  Output          : {OUTPUT_BASE}")
    print(f"  Steps per sweep : {steps}")
    print(f"  Modes           : single={RUN_SINGLE}, pairwise={RUN_PAIRWISE}, triple={RUN_TRIPLE}")
    print(f"  Planned plots   : {total}  "
          f"(Single: {n_single if RUN_SINGLE else 0}, "
          f"Pairwise: {n_pairwise if RUN_PAIRWISE else 0}, "
          f"Triple: {n_triple if RUN_TRIPLE else 0})")

    if total == 0:
        print("\nNote: No sweep mode active. Use --single, --pairwise, --triple, or --all.")
        return

    shared = dict(
        baselines          = BASELINES,
        sim_class          = sim_class,
        gas_species        = gas_species,
        surface_species    = surface_species,
        original_yaml      = original_yaml,
        start_temperatures = START_TEMPERATURES,
        sim_time           = SIMULATION_TIME,
        max_timestep       = max_timestep,
        output_base        = OUTPUT_BASE,
        tmp_yaml_dir       = TMP_YAML_DIR,
    )

    if RUN_SINGLE:
        run_single_sweeps(SWEEPS, **shared)
    if RUN_PAIRWISE:
        run_pairwise_sweeps(SWEEPS, **shared)
    if RUN_TRIPLE:
        run_triple_sweep(SWEEPS, **shared)

    print("\nAll sweeps completed.")


if __name__ == "__main__":
    main()
