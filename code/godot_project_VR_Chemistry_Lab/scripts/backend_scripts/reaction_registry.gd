class_name ReactionRegistry
extends RefCounted
## Single source of truth for "which reactions exist, which engine runs them,
## how strongly they glow" - loaded at runtime from a JSON file.
##
## That JSON is NOT hand-edited in Godot. It's generated from the actual
## source of truth on the Python/YAML side (see tools/generate_reaction_registry.py)
## whenever the reaction set there changes. Re-running that one script is the
## only extra work adding/changing a reaction requires - nothing in Godot
## needs to be touched.
##
## Expected JSON shape (data/reaction_registry.json):
## {
##   "entries": [
##     { "reactionKey": "Aqueous:", "isPrefix": true,  "engineId": "WebSocket Reaktoro", "reactionStrength": 0.0 },
##     { "reactionKey": "Na",       "isPrefix": true,  "engineId": "",                   "reactionStrength": 1.0 }
##   ],
##   "aqueousReagents": ["HCl", "NaOH", "..."]
## }
##
## Fields, per entry:
##   reactionKey       whatReaction value this entry applies to.
##   isPrefix          if true, also matches every whatReaction that
##                      begins_with() reactionKey (not just exact matches).
##   engineId          node name under DataSynchronizer/Engines that should
##                      simulate this reaction. "" = use defaultEngineId.
##   reactionStrength  rough, fixed intensity used for the glow effect.
##                      0.0 = doesn't glow. 1.0 = reference/full intensity.
##
## aqueousReagents is the list of reagent names Reaktoro understands (the
## keys of REAGENT_FORMULAS in reaktoro_engine.py) - reaction_data.gd reads
## it to detect "Aqueous:..." reactions, so that list only exists once,
## on the Python side.

var entries: Array = []  # Array[Dictionary]
var aqueousReagents: Array = []  # Array[String]

## Loads/reloads entries from a JSON file. Returns false (and logs an error)
## if the file is missing or malformed - existing entries are kept in that
## case, so a bad regeneration doesn't wipe a previously working registry.
func loadFromFile(path: String) -> bool:
	if not FileAccess.file_exists(path):
		push_error("ReactionRegistry: file not found: " + path)
		return false

	var file := FileAccess.open(path, FileAccess.READ)
	if file == null:
		push_error("ReactionRegistry: could not open " + path + " (error " + str(FileAccess.get_open_error()) + ")")
		return false

	var parsed = JSON.parse_string(file.get_as_text())
	if typeof(parsed) != TYPE_DICTIONARY or not parsed.has("entries") or typeof(parsed["entries"]) != TYPE_ARRAY:
		push_error("ReactionRegistry: malformed JSON at " + path + " (expected {\"entries\": [...]})")
		return false

	entries = parsed["entries"]
	aqueousReagents = parsed.get("aqueousReagents", [])
	return true

## Returns the first entry whose reactionKey matches `reaction`, preferring
## exact matches over prefix matches. Empty Dictionary if nothing matches -
## callers should use .get(field, default) on the result, which works fine
## on an empty Dictionary too.
func findEntry(reaction: String) -> Dictionary:
	for entry in entries:
		if entry.get("reactionKey", "") == reaction:
			return entry
	for entry in entries:
		if entry.get("isPrefix", false) and entry.get("reactionKey", "") != "" and reaction.begins_with(entry["reactionKey"]):
			return entry
	return {}

func findReactionByReactants(parts: Dictionary) -> String:
	for entry in entries:
		if entry.get("isPrefix", false):
			continue
		var reactants = entry.get("reactants", [])
		if reactants.is_empty():
			continue
		var matches := true
		for reactant in reactants:
			if not parts.has(reactant):
				matches = false
				break
		if matches:
			return entry["reactionKey"]
	return ""
