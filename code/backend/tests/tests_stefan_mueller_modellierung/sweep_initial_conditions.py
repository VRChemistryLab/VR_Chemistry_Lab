import cantera as ct
import matplotlib.pyplot as plt
import numpy as np
import os
import itertools
from dataclasses import dataclass


def makeToAbsolutPath(string_relativPath):
    dirname = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(dirname, string_relativPath)


# ---------------------------------------------------------------------------
# Parameter sweep configuration
# ---------------------------------------------------------------------------

@dataclass
class ParameterSweep:
    """
    Defines a sweep range for a single initial condition.

    Attributes
    ----------
    name      : human-readable label used in plot titles and filenames
    start     : first value (inclusive)
    end       : last value (inclusive)
    steps     : number of discrete levels (min 2)
    log_scale : if True, values are spaced logarithmically; otherwise linearly
    """
    name: str
    start: float
    end: float
    steps: int = 5
    log_scale: bool = False

    def values(self):
        if self.log_scale:
            return np.logspace(np.log10(self.start), np.log10(self.end), self.steps)
        else:
            return np.linspace(self.start, self.end, self.steps)


# ---------------------------------------------------------------------------
# Simulation  (mirrors the MATLAB model exactly)
# ---------------------------------------------------------------------------

class NaBrSurfaceSimulation:
    """
    Replicates the MATLAB reactor setup:
      - IdealGasReactor with Br2 + Ar gas mixture
      - Surface initialised at a separate temperature (T_surf_init)
      - ReactorSurface area = 1e5 m²  (strong gas-surface coupling)
      - Fixed time-step integration (dt = 1e-5 s by default)
      - Species names: PT (active site), Na_s, NaBr_s on the surface
    """

    def __init__(self, dt: float = 1e-5):
        self.dt = dt

    def init(self,
             yaml_path: str,
             T_gas: float,
             T_surf: float,
             br2_mole_frac: float,
             na_coverage: float,
             pt_coverage: float,
             p0: float = 1.01325e5):
        """
        Parameters
        ----------
        yaml_path      : path to na_br.yaml
        T_gas          : initial gas temperature [K]
        T_surf         : initial surface temperature [K]
        br2_mole_frac  : Br2 mole fraction in gas (rest = Ar)
        na_coverage    : initial Na_s surface coverage
        pt_coverage    : initial PT surface coverage (active sites)
        p0             : initial pressure [Pa]
        """
        ar_mole_frac = max(0.0, 1.0 - br2_mole_frac)
        x_str = f"Br2:{br2_mole_frac:.6f}, Ar:{ar_mole_frac:.6f}"

        self.gas = ct.Solution(yaml_path, "gas")
        self.gas.TPX = T_gas, p0, x_str

        self.surf = ct.Interface(yaml_path, "surface", [self.gas])
        self.surf.TP = T_surf, p0
        self.surf.coverages = {"PT": pt_coverage, "Na_s": na_coverage}

        self.reactor = ct.IdealGasReactor(self.gas)

        self.surf_reactor = ct.ReactorSurface(self.surf, self.reactor)
        self.surf_reactor.area = 1e5   # m² — matches MATLAB setArea(rs, 1e5)

        self.net = ct.ReactorNet([self.reactor])
        self.time = 0.0

    def run(self, t_end: float):
        """
        Integrate with fixed time steps (matches MATLAB for-loop with dt).
        Returns a list of result dicts, one per time step.
        """
        n = int(round(t_end / self.dt))
        results = []

        i_Br2  = self.gas.species_index("Br2")
        i_Na   = self.surf.species_index("Na_s")
        i_NaBr = self.surf.species_index("NaBr_s")

        for _ in range(n):
            self.time += self.dt
            self.net.advance(self.time)

            theta = self.surf.coverages
            results.append({
                "t":            self.time,
                "T":            self.reactor.T,
                "P":            self.reactor.thermo.P,
                "Br2":          self.gas.X[i_Br2],
                "Na_surface":   theta[i_Na],
                "NaBr_surface": theta[i_NaBr],
            })

        return results


# ---------------------------------------------------------------------------
# Plotting
# ---------------------------------------------------------------------------

def plotComparison(simulation_runs, output_path, title):
    """
    simulation_runs : list of (label_str, results_list)
    5-panel figure: Br2, Na_s, NaBr_s, Temperature, Pressure
    """
    fig, axes = plt.subplots(2, 3, figsize=(15, 8))
    fig.suptitle(title)
    ax_br2, ax_na, ax_nabr, ax_T, ax_p, ax_empty = axes.flat

    for label, data in simulation_runs:
        if not data:
            continue
        t    = [r["t"]            for r in data]
        br2  = [r["Br2"]          for r in data]
        na   = [r["Na_surface"]   for r in data]
        nabr = [r["NaBr_surface"] for r in data]
        T    = [r["T"]            for r in data]
        p    = [r["P"]            for r in data]

        ax_br2.plot(t, br2,  label=label)
        ax_na.plot( t, na,   label=label)
        ax_nabr.plot(t, nabr, label=label)
        ax_T.plot(  t, T,    label=label)
        ax_p.plot(  t, p,    label=label)

    ax_br2.set(title="Br₂ mole fraction",   xlabel="t [s]", ylabel="X(Br₂)")
    ax_na.set( title="Na_s coverage",        xlabel="t [s]", ylabel="θ(Na_s)")
    ax_nabr.set(title="NaBr_s coverage",     xlabel="t [s]", ylabel="θ(NaBr_s)")
    ax_T.set(  title="Reactor temperature",  xlabel="t [s]", ylabel="T [K]")
    ax_p.set(  title="Reactor pressure",     xlabel="t [s]", ylabel="P [Pa]")

    for ax in [ax_br2, ax_na, ax_nabr, ax_T, ax_p]:
        ax.ticklabel_format(style="plain", axis="y", useOffset=False)
        ax.grid(True, alpha=0.3)
        ax.legend(fontsize=7)

    ax_empty.set_visible(False)

    fig.tight_layout()
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Plot gespeichert: {output_path}")


# ---------------------------------------------------------------------------
# Filename helper
# ---------------------------------------------------------------------------

def safe_str(val: float) -> str:
    s = f"{val:.3e}".replace(".", "p").replace("e+", "ep").replace("e-", "em")
    return s


# ---------------------------------------------------------------------------
# Generic runner: simulate one condition, collect results
# ---------------------------------------------------------------------------

def _simulate(T_gas, T_surf, br2, na, pt, yaml_path, t_end, dt):
    try:
        sim = NaBrSurfaceSimulation(dt=dt)
        sim.init(yaml_path,
                 T_gas=T_gas, T_surf=T_surf,
                 br2_mole_frac=br2,
                 na_coverage=na,
                 pt_coverage=pt)
        return sim.run(t_end)
    except Exception as e:
        print(f"    Fehler: {e}")
        return None


# ---------------------------------------------------------------------------
# Sweep runners
# ---------------------------------------------------------------------------

def run_single_sweeps(sweeps, baselines, simulation_time, dt,
                      yaml_path, output_base):
    """One parameter varies; the other two stay at baseline. One plot per value."""
    for key, sweep in sweeps.items():
        print(f"\n{'='*60}\nEinzel-Sweep: {sweep.name}\n{'='*60}")
        out_dir = os.path.join(output_base, "single", key)
        os.makedirs(out_dir, exist_ok=True)

        for val in sweep.values():
            p = {k: baselines[k] for k in baselines}
            p[key] = val

            label    = f"{sweep.name} = {val:.3e}"
            title    = f"Einzel-Sweep  {sweep.name} = {val:.3e}"
            out_file = os.path.join(out_dir, f"sweep_{key}_{safe_str(val)}.png")
            print(f"  {label}")

            data = _simulate(p["T_gas"], p["T_surf"], p["br2"],
                             p["na"], p["pt"], yaml_path, simulation_time, dt)
            if data:
                plotComparison([(label, data)], out_file, title)


def run_pairwise_sweeps(sweeps, baselines, simulation_time, dt,
                        yaml_path, output_base):
    """All pairwise (key1 × key2) combos; third parameter stays at baseline."""
    keys = list(sweeps.keys())
    for key1, key2 in itertools.combinations(keys, 2):
        s1, s2    = sweeps[key1], sweeps[key2]
        fixed_key = [k for k in keys if k not in (key1, key2)][0]
        print(f"\n{'='*60}\nPaarweise Sweep: {s1.name}  ×  {s2.name}\n{'='*60}")
        out_dir = os.path.join(output_base, "pairwise", f"{key1}_x_{key2}")
        os.makedirs(out_dir, exist_ok=True)

        for v1, v2 in itertools.product(s1.values(), s2.values()):
            p = {k: baselines[k] for k in baselines}
            p[key1], p[key2] = v1, v2

            short    = f"{key1}_{safe_str(v1)}__{key2}_{safe_str(v2)}"
            title    = (f"Paarweise Sweep\n"
                        f"{s1.name} = {v1:.3e},  {s2.name} = {v2:.3e}\n"
                        f"({fixed_key} = {baselines[fixed_key]:.3e})")
            out_file = os.path.join(out_dir, f"sweep_{short}.png")
            label    = f"{s1.name}={v1:.3e}  {s2.name}={v2:.3e}"
            print(f"  {short}")

            data = _simulate(p["T_gas"], p["T_surf"], p["br2"],
                             p["na"], p["pt"], yaml_path, simulation_time, dt)
            if data:
                plotComparison([(label, data)], out_file, title)


def run_triple_sweep(sweeps, simulation_time, dt, yaml_path, output_base):
    """Full cartesian product over all three sweep parameters."""
    keys = list(sweeps.keys())
    assert len(keys) == 3, "Triple sweep expects exactly 3 sweep parameters"
    k0, k1, k2 = keys
    print(f"\n{'='*60}\nTriple Sweep: {k0} × {k1} × {k2}\n{'='*60}")
    out_dir = os.path.join(output_base, "triple")
    os.makedirs(out_dir, exist_ok=True)

    vals = [sweeps[k].values() for k in keys]
    total = len(vals[0]) * len(vals[1]) * len(vals[2])
    count = 0

    for v0, v1, v2 in itertools.product(*vals):
        count += 1
        p = {k0: v0, k1: v1, k2: v2}
        # fill in any key not in sweep with baseline
        for bk, bv in BASELINES.items():
            p.setdefault(bk, bv)

        short    = f"{k0}{safe_str(v0)}__{k1}{safe_str(v1)}__{k2}{safe_str(v2)}"
        title    = (f"Triple Sweep\n"
                    f"{k0}={v0:.3e},  {k1}={v1:.3e},  {k2}={v2:.3e}")
        out_file = os.path.join(out_dir, f"sweep_{short}.png")
        label    = f"{k0}={v0:.3e} {k1}={v1:.3e} {k2}={v2:.3e}"
        print(f"  [{count}/{total}] {short}")

        data = _simulate(p["T_gas"], p["T_surf"], p["br2"],
                         p["na"], p["pt"], yaml_path, simulation_time, dt)
        if data:
            plotComparison([(label, data)], out_file, title)


def run_temperature_comparison(br2, na, pt, start_temperatures,
                                simulation_time, dt, yaml_path,
                                output_path, title,
                                T_surf=298.15):
    """
    Classic multi-curve plot: one curve per start temperature,
    all other conditions fixed.  Mirrors the original MATLAB sweep.
    """
    simulation_runs = []
    for T0 in start_temperatures:
        print(f"  T0 = {T0} K")
        data = _simulate(T0, T_surf, br2, na, pt, yaml_path, simulation_time, dt)
        if data:
            simulation_runs.append((f"{T0} K", data))

    if not simulation_runs:
        print(f"  Keine Ergebnisse für: {title}")
        return

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    plotComparison(simulation_runs, output_path, title)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Path to your na_br.yaml  (edit if needed)
YAML_PATH = makeToAbsolutPath("reaction_definitions\\na_br.yaml")

# Fixed kinetic / reactor parameters (not swept)
SURFACE_AREA   = 1e5    # m²  (large area = strong coupling, same as MATLAB)
SIMULATION_DT  = 1e-5   # s   fixed time step (same as MATLAB)
SIMULATION_TIME = 1.0   # s

# Output directory
OUTPUT_BASE = makeToAbsolutPath("vergleichsGraphen\sweeps_initial")

# Baseline values used when a parameter is NOT currently being swept
BASELINES = {
    "T_gas":  350.0,    # K  — gas initial temperature  (MATLAB: 350 K)
    "T_surf": 298.15,   # K  — surface initial temp      (MATLAB: 298.15 K)
    "br2":    0.9,      # mole fraction Br2              (MATLAB: Br2:0.9, Ar:0.1)
    "na":     0.95,     # Na_s initial coverage          (MATLAB: Na_s:0.95)
    "pt":     0.05,     # PT  initial coverage           (MATLAB: PT:0.05)
}

# Sweep definitions — three parameters to vary
SWEEPS = {
    "T_gas": ParameterSweep(
        name="Gas-Starttemperatur T_gas [K]",
        start=300.0,
        end=1200.0,
        steps=5,
        log_scale=False,
    ),
    "br2": ParameterSweep(
        name="Anfangsmenge Br2 [Molenbruch]",
        start=0.1,
        end=1.0,
        steps=5,
        log_scale=False,
    ),
    "na": ParameterSweep(
        name="Anfangsbedeckung Na_s",
        start=0.05,
        end=0.95,
        steps=5,
        log_scale=False,
    ),
}

# Which sweep modes to run
RUN_SINGLE   = True    #  3 × 5      =  15 plots
RUN_PAIRWISE = False   #  3 × 25     =  75 plots
RUN_TRIPLE   = False   #  5³         = 125 plots

# Classic temperature comparison (all T_gas in one figure, fixed br2/na/pt)
RUN_TEMP_COMPARISON = True
START_TEMPERATURES  = [300, 500, 700, 900, 1200]   # K


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    steps = [s.steps for s in SWEEPS.values()]
    n_single   = sum(s.steps for s in SWEEPS.values())
    n_pairwise = 3 * steps[0] * steps[1]
    n_triple   = steps[0] * steps[1] * steps[2]
    total = (n_single   if RUN_SINGLE          else 0) + \
            (n_pairwise if RUN_PAIRWISE         else 0) + \
            (n_triple   if RUN_TRIPLE           else 0) + \
            (1          if RUN_TEMP_COMPARISON  else 0)
    print(f"Geplante Plots: {total}  "
          f"(Einzel: {n_single if RUN_SINGLE else 0}, "
          f"Paarweise: {n_pairwise if RUN_PAIRWISE else 0}, "
          f"Triple: {n_triple if RUN_TRIPLE else 0}, "
          f"Temperaturvergleich: {1 if RUN_TEMP_COMPARISON else 0})")
    print(f"YAML: {YAML_PATH}\n")

    if RUN_TEMP_COMPARISON:
        print(f"\n{'='*60}\nTemperatur-Vergleich (alle T_gas in einem Plot)\n{'='*60}")
        run_temperature_comparison(
            br2=BASELINES["br2"],
            na=BASELINES["na"],
            pt=BASELINES["pt"],
            start_temperatures=START_TEMPERATURES,
            simulation_time=SIMULATION_TIME,
            dt=SIMULATION_DT,
            yaml_path=YAML_PATH,
            output_path=os.path.join(OUTPUT_BASE, "temperature_comparison.png"),
            title=(f"Temperaturvergleich  "
                   f"Br2={BASELINES['br2']:.2f}, Na_s={BASELINES['na']:.2f}, "
                   f"PT={BASELINES['pt']:.2f}"),
            T_surf=BASELINES["T_surf"],
        )

    if RUN_SINGLE:
        run_single_sweeps(SWEEPS, BASELINES, SIMULATION_TIME, SIMULATION_DT,
                          YAML_PATH, OUTPUT_BASE)

    if RUN_PAIRWISE:
        run_pairwise_sweeps(SWEEPS, BASELINES, SIMULATION_TIME, SIMULATION_DT,
                            YAML_PATH, OUTPUT_BASE)

    if RUN_TRIPLE:
        run_triple_sweep(SWEEPS, SIMULATION_TIME, SIMULATION_DT,
                         YAML_PATH, OUTPUT_BASE)

    print("\nAlle Sweeps abgeschlossen.")
