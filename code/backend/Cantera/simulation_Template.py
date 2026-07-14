import cantera as ct
import numpy as np
from utils import makeToAbsolutPath

class Reactant1Reactant2Simulation:
    def __init__(self, maxTimestepInSimulation):
        self.gas = None
        self.surface = None
        self.reactor = None
        self.reservoir = None
        self.wall = None
        self.network = None
        self.time = 0.0
        self.MAX_TIMESTEP = maxTimestepInSimulation
        self.STARTIN_MOL_OF_Reactant1 = #addDataHere
        self.STARTIN_MOL_OF_Reactant2 = #addDataHere
        self.YAML_PATH = "reaction_definitions/Reactant1Reactant2.yaml"
    
    def init(self, T0, f_amountInMol=None, p0=ct.one_atm):
        amountInMol = f_amountInMol or {}
        self.STARTIN_MOL_OF_Reactant1 = amountInMol.get("Reactant1", self.STARTIN_MOL_OF_Reactant1)
        self.STARTIN_MOL_OF_Reactant2 = amountInMol.get("Reactant2", self.STARTIN_MOL_OF_Reactant2)

        self.gas = ct.Solution(makeToAbsolutPath(self.YAML_PATH), "gas")
        self.gas.TPX = T0, p0, {"Reactant2": self.STARTIN_MOL_OF_Reactant2}
        self.Reactant2_initial = self.STARTIN_MOL_OF_Reactant2

        self.surface = ct.Interface(makeToAbsolutPath(self.YAML_PATH), "surface", [self.gas])
        
        self.surface.coverages = {"Reactant1": 1} #surface is covered only by Reactant1 at first

        self.reactor = ct.IdealGasReactor(self.gas)
        self.reservoir = ct.Reservoir(self.gas)
        self.wall = ct.Wall(self.reactor, self.reservoir, A=1.0)

        self.surface_reactor = ct.ReactorSurface(self.surface, self.reactor)
        self.network = ct.ReactorNet([self.reactor])

        
        self.i_Reactant2 = self.gas.species_index("Reactant2")
        self.i_Reactant1 = self.surface.species_index("Reactant1")
        self.i_Product1 = self.surface.species_index("Product1")

        messageBack = [{"initSuccess": True, "temperature": T0}]
        return {"dataBlockList": messageBack}
    

    def runUntilTargetTime(self, t_end):
        results = []
        gas = self.gas
        reactor = self.reactor
        try:
            while self.time < t_end:
                dt = min(self.MAX_TIMESTEP, t_end-self.time)            
                self.time += dt

                self.network.advance(self.time)

                n_total = reactor.mass / gas.mean_molecular_weight 

                results.append( {
                    "timeStamp": self.time,
                    "temperature": float(self.reactor.T),
                    "pressure": float(self.reactor.thermo.P),

                    #addDataHere match reactants/products to their phases

                    # Surface
                    "amount_of_Reactant1": self.surface.coverages[self.i_Reactant1],
                    "amount_of_Product1": self.surface.coverages[self.i_Product1],

                    # gas
                    "amount_of_Reactant2": float(gas.X[self.i_Reactant2] * n_total / self.Reactant2_initial),
                } )
        except Exception as e:
            print(f"Error: {e}")
            import traceback
            traceback.print_exc()
            print(results)
        return {
            "dataBlockList": results
        }
