extends Node

var lastData: Array
var jsonParser: Node          # instantiated by DataSynchronizer.createReactionInstance 
var jsonWriter: Node          # instantiated by DataSynchronizer.createReactionInstance 
var reactionInstanceId: String = ""   # instantiated by DataSynchronizer.createReactionInstance (== group_id)
var reactionInitialized: String = ""
var reactionIdsInitialized: Dictionary = {}
var absolutReactionTimeInMs: float = 0: get = getCurrentAbsolutReactionTimeInMs
var serverIsBusy: bool = false
var serverIsHeating: bool = false

const SIMULATION_LOOKAHEAD_SECONDS: float = 2.0

func _ready() -> void:
	# Fallback for testing
	if jsonParser == null and has_node("json parser"):
		jsonParser = $"json parser"
	if jsonWriter == null and has_node("json writer"):
		jsonWriter = $"json writer"

func _process(delta: float) -> void:
	absolutReactionTimeInMs += delta

func getCurrentAbsolutReactionTimeInMs() -> float:
	return absolutReactionTimeInMs
	

# ── Engine resolution ─────────────────────────────────────────────────────────
func _getEngineFor(reaction: String) -> Node:
	return DataSynchronizer.getEngineConnectionForReaction(reaction)

# ── WebSocket ────────────────────────────────────────────────────────────────

func onMessageFromServer(text: String) -> void:
	serverIsBusy = false
	var dataAndReactionIds = jsonParser.getData(text)
	var newData = dataAndReactionIds[0]
	if newData == null or newData.size() <= 0:
		print("ServerHandler: new Data was null or of length 0")
		return
	if(dataAndReactionIds[1] == null or dataAndReactionIds[1].size() == 0):
		print("ServerHandler: reaction of no reactionIds was comuted")
		return

	# Acks for "init"/"closeSession" contain entries like {"initSuccess": true}
	# which have no "timeStamp" - they are not playback steps. Forwarding them
	# into the simulation-data pipeline crashes advanceReactionByTimePassed(),
	# which compares timeStamp against a float. Filter them out here, at the
	# single point where server responses enter the system.
	var simulationSteps: Array = []
	for entry in newData:
		if typeof(entry) == TYPE_DICTIONARY and entry.has("timeStamp"):
			simulationSteps.append(entry)

	if simulationSteps.is_empty():
		# Pure ack (init/closeSession) - nothing to advance playback with.
		if DataSynchronizer.printMessagesReceivedFromServer:
			print("ServerHandler: received a non-step ack, not forwarding as simulation data: " + str(newData))
		return

	dataAndReactionIds[0] = simulationSteps
	lastData = dataAndReactionIds
	if DataSynchronizer.printMessagesReceivedFromServer:
		print("ServerHandler: just received message: " + str(dataAndReactionIds))
	get_parent().setSimulationData(dataAndReactionIds)

func sendMessageToServer(message: String, engine: Node) -> void:
	if DataSynchronizer.printMessagesSendToServer:
		print("ServerHandler: now sending message: " + message)
	serverIsBusy = true
	engine.sendMessage(message)

func getLastData() -> Array:
	return lastData

# ── Reaction Init ────────────────────────────────────────────────────────────

func requestReactionInit(reaction: String, reactionIds: Dictionary, temperature: float, amountInMol: Dictionary) -> bool:
	if serverIsBusy or reactionIds.is_empty():
		return false
	if reactionInstanceId == "":
		push_error("ServerHandler: reactionInstanceId is empty, refusing to send init - message would be silently dropped by the server!")
		return false
	var engine = _getEngineFor(reaction)
	if engine == null or not engine.getIsReady():
		print("ServerHandler: tried to send reaction init, but engine connection wasn't established yet!")
		return false
	absolutReactionTimeInMs = 0
	var reactionIdsSnapshot = reactionIds.duplicate(true)
	var message = jsonWriter.getJsonFromDataForInit(reaction, reactionIds, absolutReactionTimeInMs, temperature, reactionInstanceId, amountInMol)
	sendMessageToServer(message, engine)
	reactionInitialized = reaction
	reactionIdsInitialized = reactionIdsSnapshot
	return true

# ── Reaction Steps ───────────────────────────────────────────────────────────

func requestStartHeatingAndReactionStep(reaction: String, reactionIds: Dictionary) -> bool:
	if serverIsBusy or reactionIds.is_empty():
		return false
	assert(isReactionInitialized(reaction, reactionIds))
	get_parent().setJustStartedHeating(false)
	var engine = _getEngineFor(reaction)
	var message = jsonWriter.getJsonFromDataForReaction(reaction, reactionIds, _getBufferedTargetTime(), "startHeatingAndRunUntilTargetTime", reactionInstanceId)
	sendMessageToServer(message, engine)
	return true

func requestStopHeatingAndReactionStep(reaction: String, reactionIds: Dictionary) -> bool:
	if serverIsBusy or reactionIds.is_empty():
		return false
	if not isReactionInitialized(reaction, reactionIds):
		print("ServerHandler: requested to stop heating and reaction step, but reaction was: ", reactionInitialized)
		return false
	get_parent().setJustStoppedHeating(false)
	var engine = _getEngineFor(reaction)
	var message = jsonWriter.getJsonFromDataForReaction(reaction, reactionIds, _getBufferedTargetTime(), "stopHeatingAndRunUntilTargetTime", reactionInstanceId)
	sendMessageToServer(message, engine)
	return true

func requestReactionStep(reaction: String, reactionIds: Dictionary) -> bool:
	if serverIsBusy or reactionIds.is_empty():
		return false
	assert(isReactionInitialized(reaction, reactionIds))
	var engine = _getEngineFor(reaction)
	var message = jsonWriter.getJsonFromDataForReaction(reaction, reactionIds, _getBufferedTargetTime(), "runUntilTargetTime", reactionInstanceId)
	sendMessageToServer(message, engine)
	return true

func _getBufferedTargetTime() -> float:
	return absolutReactionTimeInMs + SIMULATION_LOOKAHEAD_SECONDS

# ── Session-Lifecycle ────────────────────────────────────────────────────────

func requestCloseSession() -> void:
	_sendCloseSessionForCurrentReaction()

func _sendCloseSessionForCurrentReaction() -> void:
	if reactionInitialized == "":
		return
	var engine = _getEngineFor(reactionInitialized)
	if engine == null or not engine.getIsReady():
		return
	var message = jsonWriter.getJsonFromDataForReaction( reactionInitialized, reactionIdsInitialized, absolutReactionTimeInMs, "closeSession", reactionInstanceId)
	# intentionally NOT via sendMessageToServer()/serverIsBusy - during final
	# teardown no one waits for a response anymore, and during formula switching
	# (see resetReactionInitialized) this should not block the next request.
	engine.sendMessage(message)

# ── State ────────────────────────────────────────────────────────────────────

func isReactionInitialized(reaction: String, reactionIds: Dictionary) -> bool:
	return reactionInitialized == reaction and _reactionIdsMatch(reactionIdsInitialized, reactionIds)

func _reactionIdsMatch(expectedIds: Dictionary, actualIds: Dictionary) -> bool:
	if expectedIds.size() != actualIds.size():
		return false
	for chemicalName in expectedIds.keys():
		if not actualIds.has(chemicalName):
			return false
		if int(expectedIds.get(chemicalName)) != int(actualIds.get(chemicalName)):
			return false
	return true

func hasInitializedReaction() -> bool:
	return reactionInitialized != "" and not reactionIdsInitialized.is_empty()

func getInitializedReaction() -> String:
	return reactionInitialized

func resetReactionInitialized() -> void:
	# Important: if the old reactionInitialized
	# ran on a DIFFERENT engine than the new one (e.g. formula switches
	# from a cantera to a reactoro reaction), the old session must be
	# explicitly closed there - otherwise it will become orphaned forever,
	# because removeReactionInstance() only triggers when the whole group is torn down.
	_sendCloseSessionForCurrentReaction()
	reactionInitialized = ""
	reactionIdsInitialized = {}
	absolutReactionTimeInMs = 0.0
