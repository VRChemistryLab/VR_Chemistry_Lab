import asyncio
import json
from reaktoro_engine import ReaktoroEquilibriumEngine

STANDARD_HEATING_POWER = 7  # K/s - matches simulation_hub.py so heating feels
                             # the same regardless of which engine a group ends up on


class ReaktoroSession:
    """Encapsulates exactly one running Reaktoro vessel, including its state.
    One instance per reactionInstanceId (== group_id from Godot). Mirrors
    simulation_hub.ReactionSession's shape/method names on purpose, so both
    engines are drop-in swappable for whatever routes to them."""

    def __init__(self, reactionInstanceId: str):
        self.reactionInstanceId = reactionInstanceId
        self.engine = ReaktoroEquilibriumEngine()
        self.heating = False
        self.temperatureInReaction = None
        self.lastTimeInReaction = 0.0
        self.amountInReaction: dict = {}
        self.lock = asyncio.Lock()  # restricts access to the same vessel

    def validSimulationRunning(self) -> bool:
        return self.temperatureInReaction is not None

    async def initReaction(self, temperature, amountInMol=None):
        self.temperatureInReaction = float(temperature)
        self.amountInReaction = dict(amountInMol or {})
        dataBlock = await asyncio.to_thread(
            self.engine.solve, self.temperatureInReaction, self.amountInReaction
        )
        dataBlock["timeStamp"] = 0.0
        self.lastTimeInReaction = 0.0
        return {"dataBlockList": [dataBlock]}

    async def runUntilTargetTime(self, time):
        targetTime = float(time)
        if self.heating:
            elapsedTime = max(0.0, targetTime - self.lastTimeInReaction)
            self.temperatureInReaction += STANDARD_HEATING_POWER * elapsedTime
        self.lastTimeInReaction = targetTime
        # Equilibrium has no state to integrate over time like an ODE does -
        # every step is a fresh solve at the (possibly heated) current
        # temperature with the reagents dosed at init.
        dataBlock = await asyncio.to_thread(
            self.engine.solve, self.temperatureInReaction, self.amountInReaction
        )
        dataBlock["timeStamp"] = targetTime
        return {"dataBlockList": [dataBlock]}

    async def startHeating(self):
        self.heating = True

    async def stopHeating(self):
        self.heating = False

    async def decideWhatMethodToCallAndCall(self, reactionData):
        methodName = reactionData.get("methodName")
        targetTime = reactionData.get("targetTime")

        if methodName == "init":
            temperature = reactionData.get("temperature")
            amountInMol = reactionData.get("amountInMol")
            return await self.initReaction(temperature, amountInMol)
        elif not self.validSimulationRunning():
            print("error3: Simulation not initialised")
            return {"error3, you tried to run a simulation without initializing it": -3}
        elif methodName == "startHeatingAndRunUntilTargetTime":
            await self.startHeating()
            return await self.runUntilTargetTime(targetTime)
        elif methodName == "stopHeatingAndRunUntilTargetTime":
            await self.stopHeating()
            return await self.runUntilTargetTime(targetTime)
        elif methodName == "runUntilTargetTime":
            return await self.runUntilTargetTime(targetTime)
        else:
            print("error6: unknown method:", methodName)
            return {"error6, neither init, nor runUntilTargetTime was detected.": -6}


class ReaktoroSessionManager:
    """Stores all concurrently running vessels, keyed by reactionInstanceId."""

    def __init__(self):
        self._sessions: dict[str, ReaktoroSession] = {}
        self._sessionsLock = asyncio.Lock()

    async def getOrCreateSession(self, reactionInstanceId: str) -> ReaktoroSession:
        async with self._sessionsLock:
            if reactionInstanceId not in self._sessions:
                self._sessions[reactionInstanceId] = ReaktoroSession(reactionInstanceId)
            return self._sessions[reactionInstanceId]

    async def closeSession(self, reactionInstanceId: str) -> bool:
        async with self._sessionsLock:
            existed = reactionInstanceId in self._sessions
            self._sessions.pop(reactionInstanceId, None)
            return existed

    def sessionCount(self) -> int:
        return len(self._sessions)


# One manager per running server process
sessionManager = ReaktoroSessionManager()


def parseReactionData(message):
    raw = json.loads(message)

    reactionData = {}
    reactionData["reactionInstanceId"] = raw.get("reactionInstanceId")
    reactionData["whatReaction"] = raw.get("whatReaction")
    reactionData["reactionIds"] = raw.get("reactionIds")
    reactionData["targetTime"] = float(raw["targetTime"]) if raw.get("targetTime") is not None else None
    reactionData["methodName"] = raw.get("methodName")
    reactionData["temperature"] = float(raw["temperature"]) if raw.get("temperature") is not None else None

    raw_amount = raw.get("amountInMol")
    if raw_amount is not None:
        reactionData["amountInMol"] = raw_amount

    return reactionData


async def decideWhatToCallAndCall(message):
    reactionData = parseReactionData(message)
    reactionInstanceId = reactionData.get("reactionInstanceId")

    if not reactionInstanceId:
        return {"error7, reactionInstanceId missing, cannot route to a session": -7}

    # Godot notifies us that a group has been dissolved/merged ->
    # remove the vessel cleanly instead of leaving it orphaned.
    if reactionData.get("methodName") == "closeSession":
        existed = await sessionManager.closeSession(reactionInstanceId)
        return {
            "reactionInstanceId": reactionInstanceId,
            "reactionIds": reactionData.get("reactionIds"),
            "sessionClosed": existed,
        }

    session = await sessionManager.getOrCreateSession(reactionInstanceId)

    # prevents race conditions on the same vessel
    async with session.lock:
        messageBack = await session.decideWhatMethodToCallAndCall(reactionData)

    messageBack["reactionInstanceId"] = reactionInstanceId
    messageBack["reactionIds"] = reactionData.get("reactionIds")
    return messageBack
