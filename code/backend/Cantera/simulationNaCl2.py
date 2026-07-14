import cantera as ct
import numpy as np
from utils import makeToAbsolutPath

class NaCl2Simulation:
    def __init__(self, maxTimestepInSimulation):
        self.gas = None
        self.surface = None
        self.reactor = None
        self.reservoir = None
        self.wall = None
        self.network = None
        self.time = 0.0
        self.MAX_TIMESTEP = maxTimestepInSimulation
        self.STARTIN_MOL_OF_NA = 0.4 # the amout of a 1cm³ piece 
        self.STARTIN_MOL_OF_CL2 = 0.04 #the same as about the amout of a 2ml of Br2
        self.YAML_PATH = "reaction_definitions/NaCl2.yaml"
    
    def init(self, T0, f_amountInMol=None, p0=ct.one_atm):
        amountInMol = f_amountInMol or {}
        self.STARTIN_MOL_OF_NA = amountInMol.get("Na", self.STARTIN_MOL_OF_NA)
        self.STARTIN_MOL_OF_CL2 = amountInMol.get("Cl2", self.STARTIN_MOL_OF_CL2)

        self.gas = ct.Solution(makeToAbsolutPath(self.YAML_PATH), "gas")
        self.gas.TPX = T0, p0, {"Cl2": self.STARTIN_MOL_OF_CL2}
        self.Cl2_initial = self.STARTIN_MOL_OF_CL2

        self.surface = ct.Interface(makeToAbsolutPath(self.YAML_PATH), "surface", [self.gas])
        
        self.surface.coverages = {"Na": 1} #surface is covered only by Na at first

        self.reactor = ct.IdealGasReactor(self.gas)
        self.reservoir = ct.Reservoir(self.gas)
        self.wall = ct.Wall(self.reactor, self.reservoir, A=1.0)

        self.surface_reactor = ct.ReactorSurface(self.surface, self.reactor)
        self.network = ct.ReactorNet([self.reactor])

        
        self.i_Cl2 = self.gas.species_index("Cl2")
        self.i_Na = self.surface.species_index("Na")
        self.i_NaCl = self.surface.species_index("NaCl")

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

                    # Surface
                    "amount_of_Na": self.surface.coverages[self.i_Na],
                    "amount_of_NaCl": self.surface.coverages[self.i_NaCl],

                    # gas
                    "amount_of_Cl2": float(gas.X[self.i_Cl2] * n_total / self.Cl2_initial),
                } )
        except Exception as e:
            print(f"FEHLER: {e}")
            import traceback
            traceback.print_exc()
            print(results)
        return {
            "dataBlockList": results
        }
