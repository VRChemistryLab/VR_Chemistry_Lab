extends Node
# DataSynchronizer.gd (Autoload/Singleton)
#
# Pool manager: creates/manages one ReactionInstance per reaction group,
# AND maintains a registry of all connected simulation engines (each its
# own WebSocket connection).
#
# Expected scene structure:
#   DataSynchronizer (this script)
#    ├─ elementInstantiator
#    ├─ reactionGroupManager       (reaction_group_manager.gd)
#    ├─ messageRouter              (message_router.gd)
#    ├─ json parser / json writer  (stateless, shared across all engines)
#    └─ Engines                    (empty Node as container)
#        ├─ WebSocket Cantera      (WebSocketClient, e.g. ws://localhost:50505)
#        └─ <further engine nodes, name = engineId>
#
# ── Wiring up a new engine (goal: as simple as possible) ────────────────────
#   1. Add a new WebSocketClient node under "Engines", named after the
#      engineId (e.g. "WebSocket Reaktoro"), URL/port pointed at the new server.
#   2. Use that same engineId for the affected reactions in the Python/YAML
#      reaction source, then regenerate data/reaction_registry.json (see below).
#   That's it - no code anywhere else needs to be touched, as long as the
#   new server honors the same message contract (see below).
#
# ── Adding/changing a reaction ───────────────────────────────────────────────
#   Reactions are NOT defined here or anywhere else in Godot. They're defined
#   on the Python/YAML side; re-run tools/generate_reaction_registry.py
#   whenever that changes, which (re-)writes data/reaction_registry.json.
#   This script just loads that JSON at startup - see reactionRegistry below.
#
# ── Contract every connected engine must honor ──────────────────────────────
#   Incoming, the engine expects JSON with at least:
#     methodName, reactionInstanceId, reactionIds, whatReaction,
#     targetTime, temperature, amountInMol (for "init")
#   Outgoing, every response MUST echo "reactionInstanceId" back unchanged -
#   that's what all routing back to the right ServerHandler relies on.
#   "methodName": "closeSession" must clean up the session server-side.

signal dataChanged(data: Dictionary)

const ReactionInstanceScene := preload("res://backend/reaction_instance.tscn")

@export var defaultEngineId: String = "WebSocket Cantera"

# Single source of truth for "which reactions exist, which engine runs them,
# how strongly they glow" - generated JSON, see data/reaction_registry.gd
# for the exact format and tools/generate_reaction_registry.py for how it's
# produced from the Python/YAML reaction source.
@export var reactionRegistryPath: String = "res://data/reaction_registry.json"
var reactionRegistry: ReactionRegistry = ReactionRegistry.new()

# Debug flags, referenced by several scripts (server_handler, reaction_part, reaction_data)
@export var printMessagesReceivedFromServer: bool = false
@export var printMessagesSendToServer: bool = false
@export var printReactionPartsInReaction: bool = false
@export var printTemperatureEveryProcess: bool = false


const EXISTANCE_TRESHHOLD_IN_MOL: float = 0.0001

@onready var elementInstantiator: Node = $ElementInstantiator
@onready var reactionGroupManager: Node = $reactionGroupManager
@onready var messageRouter: Node = $messageRouter
@onready var jsonParser: Node = $"json parser"
@onready var jsonWriter: Node = $"json writer"
@onready var enginesContainer: Node = $Engines

var engineConnections: Dictionary = {}   # engineId(String) -> WebSocketClient(Node)
var activeReactions: Dictionary = {}     # groupId(String) -> ReactionInstance root(Node)

func _ready() -> void:
	reactionRegistry.loadFromFile(reactionRegistryPath)
	for engineNode in enginesContainer.get_children():
		var engineId = engineNode.name
		var client = _resolveClient(engineNode)
		if client == null:
			push_error("DataSynchronizer: no client script (sendMessage/getIsReady) found for engine '" + engineId + "'")
			continue
		engineConnections[engineId] = client
		client.connect("message_received", Callable(messageRouter, "onMessageFromServer"))

# The engine node itself (e.g. "WebSocket Cantera") has no script - the actual
# client API (sendMessage/getIsReady) lives on a child node ("Websocket Client").
# This resolves either layout, so it also still works if someone later puts
# the client script directly on the engine node.
func _resolveClient(engineNode: Node) -> Node:
	if engineNode.has_method("sendMessage") and engineNode.has_method("getIsReady"):
		return engineNode
	for child in engineNode.get_children():
		if child.has_method("sendMessage") and child.has_method("getIsReady"):
			return child
	return null

# ── Engine resolution, used by server_handler.gd ────────────────────────────

func getEngineConnectionForReaction(reaction: String) -> Node:
	var engineId = _resolveEngineId(reaction)
	if not engineConnections.has(engineId):
		push_error("DataSynchronizer: no engine '" + engineId + "' registered, falling back to '" + defaultEngineId + "'")
		engineId = defaultEngineId
	return engineConnections.get(engineId, null)

func _resolveEngineId(reaction: String) -> String:
	var entry := reactionRegistry.findEntry(reaction)
	var engineId: String = entry.get("engineId", "")
	return engineId if engineId != "" else defaultEngineId

# ── used by reaction_handler.gd, drives the glow effect ─────────────────────
# Rough, fixed "how violent is this reaction" value from the registry.
# 0.0 (default, no matching entry) means the reaction shouldn't glow at all.
func getReactionStrength(reaction: String) -> float:
	var entry := reactionRegistry.findEntry(reaction)
	return entry.get("reactionStrength", 0.0)

# ── called by reaction_group_manager.gd ─────────────────────────────────────

func createReactionInstance(groupId: String) -> Node:
	if activeReactions.has(groupId):
		push_warning("DataSynchronizer: createReactionInstance for already existing groupId " + groupId)
		return activeReactions[groupId]

	var instance := ReactionInstanceScene.instantiate()
	add_child(instance)

	var serverHandler := instance.get_node("server_handler")
	# Which engine will be used isn't known yet at this point (whatReaction is
	# usually still empty when a group is created) - server_handler resolves
	# this per message itself via DataSynchronizer.getEngineConnectionForReaction().
	serverHandler.jsonParser = jsonParser
	serverHandler.jsonWriter = jsonWriter
	serverHandler.reactionInstanceId = groupId

	messageRouter.registerServerHandler(serverHandler, groupId)
	activeReactions[groupId] = instance
	return instance

func removeReactionInstance(groupId: String) -> void:
	if not activeReactions.has(groupId):
		return

	var instance: Node = activeReactions[groupId]
	if is_instance_valid(instance):
		var serverHandler := instance.get_node("server_handler")
		serverHandler.requestCloseSession()
		instance.queue_free()

	messageRouter.unregisterServerHandler(groupId)
	activeReactions.erase(groupId)

# ── unchanged, used by reactionHandler.gd ───────────────────────────────────

func instantiate(world: Node, element: String) -> Node:
	return elementInstantiator.instantiate(world, element)

func setStepOfCompleteReaction(dataStep: Dictionary) -> void:
	emit_signal("dataChanged", dataStep)
