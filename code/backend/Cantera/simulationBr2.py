import cantera as ct
from utils import makeToAbsolutPath

class Br2Simulation:
    def __init__(self, maxTimestepInSimulation):
        self.gas = None
        self.reactor = None
        self.network = None
        self.time = 0.0
        self.MAX_TIMESTEP = maxTimestepInSimulation
        self.current_power = 0.0 #watt
        self.STARTIN_MOL_OF_BR2 = 1.0

    def init(self, f_startTemperature, f_amountInMol=None):
        previous_time = self.time
        amountInMol = f_amountInMol or {}
        self.STARTIN_MOL_OF_BR2 = amountInMol.get("Br2", self.STARTIN_MOL_OF_BR2)

        self.gas = ct.Solution(makeToAbsolutPath('reaction_definitions\\Br2.yaml'))

        # set initial coditions
        self.gas.TPX = f_startTemperature, ct.one_atm, "Br2:1"
        self.i_Br2 = self.gas.species_index("Br2")

        #creating the reactor
        self.reactor = ct.IdealGasReactor(self.gas, energy="on")
        self.reactor.volume = self.STARTIN_MOL_OF_BR2 * ct.gas_constant * f_startTemperature / ct.one_atm
        self.network = ct.ReactorNet([self.reactor])

        #set own variables
        self.time = previous_time

        messageBack = [{"initSuccess": True, "temperature": self.reactor.T}]
        return {"dataBlockList": messageBack}

    def runUntilTargetTime(self, targetTime):
        data = []
        gas = self.gas
        reactor = self.reactor

    
        while self.time < targetTime:
            timestep = targetTime-self.time
            dt = min(self.MAX_TIMESTEP, timestep)

            self.time += dt
            self.network.advance(self.time)

            n_total = reactor.mass / gas.mean_molecular_weight
            data.append( {
                "timeStamp": self.time,
                "temperature": float(self.reactor.T),
                "pressure": float(self.reactor.thermo.P),
                "amount_of_Br2": float(gas.X[self.i_Br2] * n_total)
            } )
        return {
            "dataBlockList": data
        }
