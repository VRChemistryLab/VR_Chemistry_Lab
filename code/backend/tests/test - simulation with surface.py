import cantera as ct
import matplotlib.pyplot as plt
import numpy as np
import os


def makeToAbsolutPath(string_relativPath):
        dirname = os.path.dirname(__file__)
        filename = os.path.join(dirname, string_relativPath)
        return filename


class NaBrSurfaceSimulation:
    def __init__(self, max_dt=1e-3, output_every=100):
        self.max_dt = max_dt
        self.output_every = output_every
        self.time = 0.0

    def init(self, T0, p0=ct.one_atm):
        self.gas = ct.Solution(makeToAbsolutPath("reaction_definitions/test_NaBr2.yaml"), "gas")
        self.gas.TPX = T0, p0, {"Br2": 0.04}

        self.surf = ct.Interface(
            makeToAbsolutPath("reaction_definitions/test_NaBr2.yaml"),
            "surface",
            [self.gas]
        )

        self.surf.coverages = {"Na": 0.4}

        self.reactor = ct.IdealGasReactor(self.gas)
        self.reservoir = ct.Reservoir(self.gas)
        self.wall = ct.Wall(self.reactor, self.reservoir, A=1.0)

        self.surface_reactor = ct.ReactorSurface(self.surf, self.reactor)
        self.net = ct.ReactorNet([self.reactor])

        self.time = 0.0

        return [{"init": True, "T": T0}]

    def run(self, t_end):
        results = []
        step_count = 0

        i_Br2 = self.gas.species_index("Br2")
        i_Na = self.surf.species_index("Na")
        i_NaBr = self.surf.species_index("NaBr")

        while self.time < t_end:
            dt = min(self.max_dt, t_end - self.time)
            self.time += dt
            step_count += 1

            self.net.advance(self.time)

            gas = self.gas
            n_total = self.reactor.mass / gas.mean_molecular_weight
            mole_fractions = gas.X

            if step_count % self.output_every == 0 or self.time >= t_end:
                results.append({
                    "t": self.time,
                    "T": self.reactor.T,
                    "P": self.reactor.thermo.P,

                    # Gas
                    "Br2": mole_fractions[i_Br2] * n_total,
                    "Br2_X": mole_fractions[i_Br2],

                    # Surface
                    "Na_surface": self.surf.coverages[i_Na],
                    "NaBr_surface": self.surf.coverages[i_NaBr],

                    # Debug: does the reaction move at all?
                    "rate": float(self.surf.net_rates_of_progress[0])
                })

        return {"dataBlockList": results}

    def printResults(self, dataBlockList):
        if not dataBlockList:
            print("Keine Daten vorhanden.")
            return

        print("\n========== SIMULATION RESULTS ==========\n")

        header = (
            f"{'t [s]':>8} | {'T [K]':>8} | {'P [Pa]':>12} | "
            f"{'Br2 [mol]':>12} | {'Na(s)':>10} | {'NaBr(s)':>10} | {'rate':>10}"
        )
        print(header)
        print("-" * len(header))

        for row in dataBlockList:
            print(
                f"{row['t']:8.4f} | "
                f"{row['T']:8.2f} | "
                f"{row['P']:12.2f} | "
                f"{row['Br2']:12.6e} | "
                f"{row['Na_surface']:10.4f} | "
                f"{row['NaBr_surface']:10.4f} | "
                f"{row['rate']:10.3e}"
            )

        print("\n========================================\n")

    def plotResults(self, dataBlockList, output_path="vergleichsGraphen/surface_simulation_results.png", title="NaBr Surface Simulation"):
        if not dataBlockList:
            print("Keine Daten zum Plotten vorhanden.")
            return

        time_values = [row["t"] for row in dataBlockList]
        temperature_values = [row["T"] for row in dataBlockList]
        pressure_values = [row["P"] for row in dataBlockList]
        delta_temperature_values = [value - temperature_values[0] for value in temperature_values]
        delta_pressure_values = [value - pressure_values[0] for value in pressure_values]
        br2_initial = dataBlockList[0]["Br2"]
        br2_pct = [row["Br2"] / br2_initial * 100 for row in dataBlockList]
        na_surface_values = [row["Na_surface"] for row in dataBlockList]
        nabr_surface_values = [row["NaBr_surface"] for row in dataBlockList]
        rate_values = [row["rate"] for row in dataBlockList]

        fig, axes = plt.subplots(2, 2, figsize=(12, 8))
        fig.suptitle(title)

        axes[0, 0].plot(time_values, delta_temperature_values, label="Delta T [K]", color="tab:red")
        axes[0, 0].set_title("Temperature Change")
        axes[0, 0].set_xlabel("t [s]")
        axes[0, 0].set_ylabel("Delta T [K]")
        axes[0, 0].ticklabel_format(style="plain", axis="y", useOffset=False)
        axes[0, 0].grid(True, alpha=0.3)

        axes[0, 1].plot(time_values, delta_pressure_values, label="Delta P [Pa]", color="tab:blue")
        axes[0, 1].set_title("Pressure Change")
        axes[0, 1].set_xlabel("t [s]")
        axes[0, 1].set_ylabel("Delta P [Pa]")
        axes[0, 1].ticklabel_format(style="plain", axis="y", useOffset=False)
        axes[0, 1].grid(True, alpha=0.3)

        axes[1, 0].plot(time_values, br2_pct, label="Br2 [%]",color="tab:orange")
        axes[1, 0].plot(time_values, na_surface_values, label="Na(s)", color="tab:green")
        axes[1, 0].plot(time_values, nabr_surface_values, label="NaBr(s)", color="tab:purple")
        axes[1, 0].set_title("Species and Surface Coverages")
        axes[1, 0].set_xlabel("t [s]")
        axes[1, 0].set_ylabel("Value")
        axes[1, 0].legend()
        axes[1, 0].grid(True, alpha=0.3)

        axes[1, 1].plot(time_values, rate_values, label="rate", color="tab:brown")
        axes[1, 1].set_title("Reaction Rate")
        axes[1, 1].set_xlabel("t [s]")
        axes[1, 1].set_ylabel("rate")
        axes[1, 1].grid(True, alpha=0.3)

        fig.tight_layout()

        full_output_path = makeToAbsolutPath(output_path)
        fig.savefig(full_output_path, dpi=150, bbox_inches="tight")
        plt.close(fig)

        print(f"Plot gespeichert unter: {full_output_path}")


    #methode zur viualisierung wie in stefans testcode
    def plotMatlab(self, dataBlockList,
                   output_path="vergleichsGraphen/matlab_style.png",
                   title_prefix=""):
        if not dataBlockList:
            print("Keine Daten zum Plotten vorhanden.")
            return

        time_values   = [row["t"]           for row in dataBlockList]
        br2_initial = dataBlockList[0]["Br2"]
        br2_values  = [row["Br2"] / br2_initial * 100 for row in dataBlockList]
        na_values     = [row["Na_surface"]  for row in dataBlockList]
        nabr_values   = [row["NaBr_surface"]for row in dataBlockList]
        T_values      = [row["T"]           for row in dataBlockList]
        P_values      = [row["P"]           for row in dataBlockList]

        fig, axes = plt.subplots(2, 3, figsize=(15, 8))
        fig.suptitle(title_prefix or "NaBr Surface Simulation (MATLAB-style)")

        plots = [
            (axes[0, 0], time_values, br2_values,  "Br₂ [%]",              "Br₂ consumption"),
            (axes[0, 1], time_values, na_values,   "Na surface coverage",  "Na consumption"),
            (axes[0, 2], time_values, nabr_values, "NaBr surface coverage","NaBr formation"),
            (axes[1, 0], time_values, T_values,    "Temperature [K]",      "Reactor temperature"),
            (axes[1, 1], time_values, P_values,    "Pressure [Pa]",        "Reactor pressure"),
        ]

        for ax, x, y, ylabel, plot_title in plots:
            ax.plot(x, y, linewidth=2)
            ax.set_xlabel("Time [s]")
            ax.set_ylabel(ylabel)
            ax.set_title(plot_title)
            ax.grid(True, alpha=0.3)

        axes[1, 2].set_visible(False)  # 6. Subplot leer lassen

        fig.tight_layout()
        full_output_path = makeToAbsolutPath(output_path)
        fig.savefig(full_output_path, dpi=150, bbox_inches="tight")
        plt.close(fig)
        print(f"Plot gespeichert unter: {full_output_path}")



def plotTemperatureComparison(simulation_runs, output_path="vergleichsGraphen/surface_temperature_comparison.png"):
    fig, axes = plt.subplots(2, 2, figsize=(12, 8))
    fig.suptitle("NaBr Surface Simulation Comparison")

    for start_temperature, dataBlockList in simulation_runs:
        time_values = [row["t"] for row in dataBlockList]
        temperature_values = [row["T"] for row in dataBlockList]
        pressure_values = [row["P"] for row in dataBlockList]
        br2_initial = dataBlockList[0]["Br2"]
        br2_values = [row["Br2"] / br2_initial * 100 for row in dataBlockList]
        na_surface_values = [row["Na_surface"] for row in dataBlockList]
        nabr_surface_values = [row["NaBr_surface"] for row in dataBlockList]

        delta_temperature_values = [value - temperature_values[0] for value in temperature_values]
        delta_pressure_values = [value - pressure_values[0] for value in pressure_values]

        label = f"{start_temperature} K"
        axes[0, 0].plot(time_values, delta_temperature_values, label=label)
        axes[0, 1].plot(time_values, delta_pressure_values, label=label)
        axes[1, 0].plot(time_values, br2_values, label=label)
        axes[1, 1].plot(time_values, nabr_surface_values, label=label)

    axes[0, 0].set_title("Temperature Change")
    axes[0, 0].set_xlabel("t [s]")
    axes[0, 0].set_ylabel("Delta T [K]")
    axes[0, 0].ticklabel_format(style="plain", axis="y", useOffset=False)
    axes[0, 0].grid(True, alpha=0.3)
    axes[0, 0].legend()

    axes[0, 1].set_title("Pressure Change")
    axes[0, 1].set_xlabel("t [s]")
    axes[0, 1].set_ylabel("Delta P [Pa]")
    axes[0, 1].ticklabel_format(style="plain", axis="y", useOffset=False)
    axes[0, 1].grid(True, alpha=0.3)
    axes[0, 1].legend()

    axes[1, 0].set_title("Br2 Amount")
    axes[1, 0].set_xlabel("t [s]")
    axes[1, 0].set_ylabel("Br2 [%]")
    axes[1, 0].grid(True, alpha=0.3)
    axes[1, 0].legend()

    axes[1, 1].set_title("NaBr Surface Coverage")
    axes[1, 1].set_xlabel("t [s]")
    axes[1, 1].set_ylabel("NaBr(s)")
    axes[1, 1].grid(True, alpha=0.3)
    axes[1, 1].legend()

    fig.tight_layout()

    full_output_path = makeToAbsolutPath(output_path)
    fig.savefig(full_output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)

    print(f"Vergleichsplot gespeichert unter: {full_output_path}")



simulation_time = 60.0
#start_temperatures = [600, 800, 1000, 1200, 1400]
start_temperatures = [350]
simulation_runs = []

for start_temperature in start_temperatures:
    sim = NaBrSurfaceSimulation()
    sim.init(start_temperature)
    result = sim.run(simulation_time)
    simulation_runs.append((start_temperature, result["dataBlockList"]))

    #output_name = f"surface_simulation_results_{start_temperature}K_{simulation_time}s.png"
    #title = f"NaBr Surface Simulation ({start_temperature} K, {simulation_time}s)"
    #sim.plotResults(result["dataBlockList"], output_name, title)

plotTemperatureComparison(simulation_runs)
sim.plotMatlab(result["dataBlockList"],
               output_path="vergleichsGraphen/matlab_style_350K - 1min, realistische Stoffmengen zu Beginn.png",
               title_prefix="NaBr Simulation 350 K")