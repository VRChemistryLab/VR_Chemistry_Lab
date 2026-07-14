import asyncio
import json
from utils import getAllAvailableReactions, getClassByName

MAX_TIMESTEP = 0.1  # s
STANDART_HEATING_POWER = 7  # K/s
ALL_AVAILABLE_REACTIONS = getAllAvailableReactions()


def buildResponseEnvelope(success, reactionInstanceId=None, reactionIds=None, data=None, error=None):
    """The one and only shape every message sent back to the client has.

    {
      "success": bool,
      "reactionInstanceId": str | null,
      "reactionIds": dict | null,
      "data": dict | null,     # e.g. {"dataBlockList": [...]} or {"sessionClosed": true}
      "error": {"code": str, "message": str} | null
    }

    "data" keeps using "dataBlockList" as its inner key for step/ack results,
    so that the (unchanged) Godot-side parsing of dataBlockList keeps working
    without any change on that side.
    """
    return {
        "success": success,
        "reactionInstanceId": reactionInstanceId,
        "reactionIds": reactionIds,
        "data": data,
        "error": error,
    }


def _errorResult(code, message):
    """Internal-only helper: how a ReactionSession signals a handled
    (non-exception) error up to decideWhatToCallAndCall, which then wraps
    it into a proper buildResponseEnvelope(...)."""
    return {"error": {"code": code, "message": message}}


class ReactionSession:
    """Encapsulates exactly one running Cantera reaction, including its state.
    One instance per reactionInstanceId (== group_id from Godot)."""

    def __init__(self, reactionInstanceId: str):
        self.reactionInstanceId = reactionInstanceId
        self.simulation = None
        self.heating = False
        self.temperatureInReaction = None
        self.lastTimeInReaction = 0.0
        self.amountInReaction = None  
        self.lock = asyncio.Lock() #for restricting access to the same cantera reaction

    async def initReaction(self, temperature, amountInMol=None):
        self.temperatureInReaction = float(temperature)
        if amountInMol is not None:
            self.amountInReaction = amountInMol
            return await asyncio.to_thread(
                self.simulation.init, self.temperatureInReaction, self.amountInReaction
            )
        return await asyncio.to_thread(self.simulation.init, self.temperatureInReaction)

    async def runUntilTargetTime(self, time):
        if self.heating:
            targetTime = float(time)
            elapsedTime = max(0.0, targetTime - self.lastTimeInReaction)
            self.temperatureInReaction += STANDART_HEATING_POWER * elapsedTime
            await self.initReaction(self.temperatureInReaction, self.amountInReaction)
        result = await asyncio.to_thread(self.simulation.runUntilTargetTime, float(time))
        self._setLastTimeInReaction(result)
        return result

    def _setLastTimeInReaction(self, result):
        self.lastTimeInReaction = result["dataBlockList"][-1]["timeStamp"]

    async def startHeating(self):
        self.heating = True

    async def stopHeating(self):
        self.heating = False

    def validSimulationRunning(self) -> bool:
        return self.simulation is not None

    async def decideWhatMethodToCallAndCall(self, reactionData):
        """Returns either {"dataBlockList": [...]} on success, or
        {"error": {"code": ..., "message": ...}} on a handled failure."""
        methodName = reactionData.get("methodName")
        targetTime = reactionData.get("targetTime")

        if methodName == "init":
            reactionScript = getReactionScriptFromString(reactionData.get("whatReaction"))
            if reactionScript is None:
                print("error: unknown reaction:", reactionData.get("whatReaction"))
                return _errorResult(
                    "UNKNOWN_REACTION",
                    f"no simulation found for whatReaction={reactionData.get('whatReaction')!r}",
                )
            self.simulation = reactionScript(MAX_TIMESTEP)
            temperature = reactionData.get("temperature")
            amountInMol = reactionData.get("amountInMol")
            return await self.initReaction(temperature, amountInMol)
        elif not self.validSimulationRunning():
            print("error: Simulation not initialisied")
            return _errorResult(
                "SIM_NOT_INITIALIZED", "you tried to run a simulation without initializing it"
            )
        elif methodName == "startHeatingAndRunUntilTargetTime":
            await self.startHeating()
            return await self.runUntilTargetTime(targetTime)
        elif methodName == "stopHeatingAndRunUntilTargetTime":
            await self.stopHeating()
            return await self.runUntilTargetTime(targetTime)
        elif methodName == "runUntilTargetTime":
            return await self.runUntilTargetTime(targetTime)
        else:
            print("error: unknown method:", methodName)
            return _errorResult(
                "UNKNOWN_METHOD",
                f"neither init, nor runUntilTargetTime was detected (got methodName={methodName!r})",
            )


class ReactionSessionManager:
    """Stores all concurrently running reactions, keyed by reactionInstanceId."""

    def __init__(self):
        self._sessions: dict[str, ReactionSession] = {}
        self._sessionsLock = asyncio.Lock()

    async def getOrCreateSession(self, reactionInstanceId: str) -> ReactionSession:
        async with self._sessionsLock:
            if reactionInstanceId not in self._sessions:
                self._sessions[reactionInstanceId] = ReactionSession(reactionInstanceId)
            return self._sessions[reactionInstanceId]

    async def closeSession(self, reactionInstanceId: str) -> bool:
        async with self._sessionsLock:
            existed = reactionInstanceId in self._sessions
            self._sessions.pop(reactionInstanceId, None)
            return existed

    def sessionCount(self) -> int:
        return len(self._sessions)


# One manager per running server process
sessionManager = ReactionSessionManager()


def getReactionScriptFromString(string_reaction):
    for possibleReaction in ALL_AVAILABLE_REACTIONS:
        if possibleReaction == string_reaction:
            return getSimulationClassFromString(possibleReaction)
    return None


def getSimulationClassFromString(reactionString):
    fileName = "simulation" + reactionString
    className = reactionString + "Simulation"
    return getClassByName(fileName, className)


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
    reactionIds = reactionData.get("reactionIds")

    if not reactionInstanceId:
        return buildResponseEnvelope(
            False,
            reactionIds=reactionIds,
            error={
                "code": "MISSING_REACTION_INSTANCE_ID",
                "message": "reactionInstanceId missing, cannot route to a session",
            },
        )

    # Godot notifies us that a group has been dissolved/merged ->
    # Remove the session cleanly instead of leaving it orphaned.
    if reactionData.get("methodName") == "closeSession":
        existed = await sessionManager.closeSession(reactionInstanceId)
        return buildResponseEnvelope(
            True,
            reactionInstanceId=reactionInstanceId,
            reactionIds=reactionIds,
            data={"sessionClosed": existed},
        )

    session = await sessionManager.getOrCreateSession(reactionInstanceId)

    # prevents Race Conditions
    async with session.lock:
        rawResult = await session.decideWhatMethodToCallAndCall(reactionData)

    if "error" in rawResult:
        return buildResponseEnvelope(
            False,
            reactionInstanceId=reactionInstanceId,
            reactionIds=reactionIds,
            error=rawResult["error"],
        )

    return buildResponseEnvelope(
        True,
        reactionInstanceId=reactionInstanceId,
        reactionIds=reactionIds,
        data=rawResult,  # {"dataBlockList": [...]}
    )