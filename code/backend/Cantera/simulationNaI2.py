import cantera as ct
import numpy as np
from utils import makeToAbsolutPath

class NaI2Simulation:
    def __init__(self, maxTimestepInSimulation):
        self.gas = None
        self.surface = None
        self.reactor = None
        self.reservoir = None
        self.wall = None
        self.network = None
        self.time = 0.0
        self.MAX_TIMESTEP = maxTimestepInSimulation
        self.STARTIN_MOL_OF_Na = 0.4
        self.STARTIN_MOL_OF_I2 = 0.04
        self.YAML_PATH = "reaction_definitions/NaI2.yaml"
    
    def init(self, T0, f_amountInMol=None, p0=ct.one_atm):
        amountInMol = f_amountInMol or {}
        self.STARTIN_MOL_OF_Na = amountInMol.get("Na", self.STARTIN_MOL_OF_Na)
        self.STARTIN_MOL_OF_I2 = amountInMol.get("I2", self.STARTIN_MOL_OF_I2)

        self.gas = ct.Solution(makeToAbsolutPath(self.YAML_PATH), "gas")
        self.gas.TPX = T0, p0, {"I2": self.STARTIN_MOL_OF_I2}
        self.I2_initial = self.STARTIN_MOL_OF_I2

        self.surface = ct.Interface(makeToAbsolutPath(self.YAML_PATH), "surface", [self.gas])
        
        self.surface.coverages = {"Na": 1} #surface is covered only by Na at first

        self.reactor = ct.IdealGasReactor(self.gas)
        self.reservoir = ct.Reservoir(self.gas)
        self.wall = ct.Wall(self.reactor, self.reservoir, A=1.0)

        self.surface_reactor = ct.ReactorSurface(self.surface, self.reactor)
        self.network = ct.ReactorNet([self.reactor])

        
        self.i_I2 = self.gas.species_index("I2")
        self.i_Na = self.surface.species_index("Na")
        self.i_NaI = self.surface.species_index("NaI")

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
                    "amount_of_Na": self.surface.coverages[self.i_Na],
                    "amount_of_NaI": self.surface.coverages[self.i_NaI],

                    # gas
                    "amount_of_I2": float(gas.X[self.i_I2] * n_total / self.I2_initial),
                } )
        except Exception as e:
            print(f"Error: {e}")
            import traceback
            traceback.print_exc()
            print(results)
        return {
            "dataBlockList": results
        }
