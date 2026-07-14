import cantera as ct
from utils import makeToAbsolutPath

class NaSimulation:
    def __init__(self, maxTimestepInSimulation):
        self.gas = None
        self.reactor = None
        self.network = None
        self.time = 0.0
        self.MAX_TIMESTEP = maxTimestepInSimulation
        self.current_power = 0.0 #watt
        self.STARTIN_MOL_OF_NA = 1.0
    
    def init(self, f_startTemperature, f_amountInMol=None):
        previous_time = self.time
        amountInMol = f_amountInMol or {}
        self.STARTIN_MOL_OF_NA = amountInMol.get("Na", self.STARTIN_MOL_OF_NA)

        # loading data
        self.gas = ct.Solution(makeToAbsolutPath('reaction_definitions\\Na.yaml'))

        # set initial coditions
        self.gas.TPX = f_startTemperature, ct.one_atm, "Na:1"
        self.i_Na = self.gas.species_index("Na")

        #creating the reactor
        self.reactor = ct.IdealGasReactor(self.gas, energy="on")
        self.reactor.volume = self.STARTIN_MOL_OF_NA * ct.gas_constant * f_startTemperature / ct.one_atm
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

            data.append({
                "timeStamp": self.time,
                "temperature": float(self.reactor.T),
                "pressure": float(reactor.thermo.P),
                "amount_of_Na": float(gas.X[self.i_Na] * n_total)
            })
        return {"dataBlockList": data}
