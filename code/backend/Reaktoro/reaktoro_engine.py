"""
reaktoro_engine.py
-------------------
Pure Reaktoro chemistry, no networking/asyncio here. Called from
reaktoro_hub.py, mirroring how simulationNaBr2.py is called from
simulation_hub.py.

Key difference to Cantera: there is no per-formula mechanism file. You
declare an ELEMENT space once and Reaktoro computes whatever equilibrium
those elements can reach (Gibbs-energy minimization) - any reagent
combination just works, so there is exactly one class here instead of one
simulationXYZ.py per reaction.

Everything is synchronous; reaktoro_hub.py wraps calls in asyncio.to_thread().
"""

import reaktoro as rkt

# Elements the vessel knows about - any species these elements can form is
# automatically available from the thermodynamic database.
ELEMENTS = "H O C Na Cl Ca S N K Mg Fe Cu Ba Pb"

# Display name (== ReactionPart.CHEMICAL_NAME in Godot) -> chemical formula
# Reaktoro understands. Extend this list to add new reagents - no other
# code needs to change (that's the whole point of the equilibrium approach).
REAGENT_FORMULAS = {
    # Acids
    "HCl": "HCl", "H2SO4": "H2SO4", "HNO3": "HNO3", "H3PO4": "H3PO4",
    # Bases
    "NaOH": "NaOH", "KOH": "KOH", "Ca(OH)2": "Ca(OH)2",
    # Salts
    "NaCl": "NaCl", "CaCl2": "CaCl2", "CuSO4": "CuSO4", "Na2CO3": "Na2CO3",
    "Na2SO4": "Na2SO4", "BaCl2": "BaCl2", "FeCl3": "FeCl3", "FeCl2": "FeCl2",
    "Pb(NO3)2": "Pb(NO3)2",
    # Metals / solids
    "Fe": "Fe", "Cu": "Cu", "CaCO3": "CaCO3",
    # Gases (dissolved in water)
    "CO2": "CO2", "NH3": "NH3",
}

# No "water" ReactionPart exists in the Godot scene yet, so the vessel is
# assumed to hold this much water unless amountInMol carries an explicit
# "H2O" entry (in mol). Easiest place to make this configurable later.
DEFAULT_WATER_KG = 1.0
WATER_MOLAR_MASS_KG_PER_MOL = 0.018015

EXISTANCE_THRESHOLD_MOL = 1e-9  # below this, a species is reported as absent


class ReaktoroEquilibriumEngine:
    """One instance per ReaktoroSession (== per reactionInstanceId). Builds
    the ChemicalSystem/EquilibriumSolver once and re-solves it on every
    init()/step() call with whatever reagents are currently present."""

    def __init__(self):
        self._db = None
        self._system = None
        self._solver = None
        self._lastGasMol: dict[str, float] = {}

    def ensureBuilt(self):
        """Expensive (loads the thermo database) - call once, off the event loop."""
        if self._system is not None:
            return
        self._db = rkt.SupcrtDatabase("supcrtbl")

        solution = rkt.AqueousPhase(rkt.speciate(ELEMENTS))
        solution.setActivityModel(rkt.ActivityModelHKF())

        gasPhase = rkt.GaseousPhase("H2O(g) CO2(g) H2(g) O2(g) N2(g)")
        gasPhase.setActivityModel(rkt.ActivityModelPengRobinson())

        mineralPhase = rkt.MineralPhases()  # Reaktoro picks which ones form

        self._system = rkt.ChemicalSystem(self._db, solution, gasPhase, mineralPhase)
        specs = rkt.EquilibriumSpecs(self._system)
        specs.temperature()
        specs.pressure()
        self._solver = rkt.EquilibriumSolver(specs)
        self._specs = specs

    def solve(self, temperatureInKelvin: float, amountInMol: dict) -> dict:
        """amountInMol: {displayName: molAmount}, exactly what
        reaction_data.gd's getReactionAmountInMol() sends today for Cantera."""
        self.ensureBuilt()

        waterKg = DEFAULT_WATER_KG
        reagents = dict(amountInMol or {})
        if "H2O" in reagents:
            waterKg = reagents.pop("H2O") * WATER_MOLAR_MASS_KG_PER_MOL

        state = rkt.ChemicalState(self._system)
        state.temperature(float(temperatureInKelvin), "K")
        state.pressure(1.0, "bar")
        state.set("H2O", waterKg / WATER_MOLAR_MASS_KG_PER_MOL, "mol")

        for displayName, mol in reagents.items():
            formula = REAGENT_FORMULAS.get(displayName)
            if formula is None:
                continue  # not a known Reaktoro reagent, e.g. a Cantera-only chemical
            try:
                state.add(formula, float(mol), "mol")
            except Exception:
                pass  # species not representable in this element space - skip

        conditions = rkt.EquilibriumConditions(self._specs)
        conditions.temperature(float(temperatureInKelvin), "K")
        conditions.pressure(1.0, "bar")

        result = self._solver.solve(state, conditions)
        if not result.succeeded():
            raise RuntimeError("Reaktoro equilibrium solver did not converge")

        return self._buildDataBlock(state, temperatureInKelvin)

    # ------------------------------------------------------------------
    # Response shaping
    # ------------------------------------------------------------------

    def _buildDataBlock(self, state: "rkt.ChemicalState", temperatureInKelvin: float) -> dict:
        aqProps = rkt.AqueousProps(state)
        pH = float(aqProps.pH())

        precipitateAmounts: dict[str, float] = {}
        gasAmounts: dict[str, float] = {}
        for species in self._system.species():
            name = species.name()
            n = float(state.speciesAmount(name, "mol"))
            if n <= EXISTANCE_THRESHOLD_MOL:
                continue
            if name.endswith("(g)"):
                gasAmounts[name[:-3]] = n
            elif not name.endswith("(aq)") and name != "H2O":
                precipitateAmounts[name] = n

        currentGasTotal = sum(gasAmounts.values())
        previousGasTotal = sum(self._lastGasMol.values())
        bubbleRate = max(0.0, currentGasTotal - previousGasTotal)
        self._lastGasMol = dict(gasAmounts)

        dataBlock = {
            "timeStamp": None,  # filled in by the caller (init: 0.0, step: targetTime)
            "temperature": float(temperatureInKelvin),
            "pH": round(pH, 4),
            # render contract, same idea as ONBOARDING.md's `render` block -
            # unused by today's pipeline, ready for VFX to bind against later
            "render": {
                "fluid_color": _phToColor(pH),
                "cloudiness": min(1.0, sum(precipitateAmounts.values()) / 0.05),
                "glow": _temperatureGlow(temperatureInKelvin),
                "bubble_rate": round(bubbleRate, 6),
                "pressure_atm": 1.0 + max(0.0, currentGasTotal) * 0.1,
            },
        }
        # amount_of_<X> is the one convention reaction_handler.gd actually reads -
        # this is what makes new precipitates spawn as real 3D ReactionParts,
        # exactly like amount_of_NaBr does for the Cantera reaction today.
        for name, mol in precipitateAmounts.items():
            dataBlock[f"amount_of_{name}"] = round(mol, 8)
        # Gases stay out of amount_of_* on purpose - dissolved gas isn't
        # something you can pick up as a physical object. bubble_rate above
        # is the intended signal for a bubble-emitter VFX.
        for name, mol in gasAmounts.items():
            dataBlock[f"gas_mol_{name}"] = round(mol, 8)

        return dataBlock


def _phToColor(pH: float) -> list:
    """Maps pH 0-14 to an RGB color, universal-indicator style."""
    pH = max(0.0, min(14.0, pH))
    if pH < 3:
        t = pH / 3.0
        return [1.0, t * 0.3, 0.0]
    elif pH < 6:
        t = (pH - 3) / 3.0
        return [1.0, 0.3 + t * 0.7, 0.0]
    elif pH < 8:
        t = (pH - 6) / 2.0
        return [1.0 - t, 1.0, 0.0]
    elif pH < 11:
        t = (pH - 8) / 3.0
        return [0.0, 1.0 - t * 0.5, t]
    else:
        t = (pH - 11) / 3.0
        return [t * 0.5, 0.0, 1.0]


def _temperatureGlow(temperatureInKelvin: float) -> float:
    """0 at room temperature (~298 K), 1 at ~500 K above that - heat glow VFX."""
    roomTemperature = 298.15
    if temperatureInKelvin <= roomTemperature:
        return 0.0
    return min(1.0, (temperatureInKelvin - roomTemperature) / 500.0)
