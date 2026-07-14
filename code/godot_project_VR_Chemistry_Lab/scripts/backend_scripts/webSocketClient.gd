extends "res://addons/websocket/WebSocket.gd"

# Emitted whenever a raw text message arrives from the server.
# DataSynchronizer connects to this to forward messages to messageRouter.
signal message_received(text: String)

var websocket_node
var isReadyForSending: bool = false
var _receiveBuffer: String = ""

func _ready():
	websocket_node = self.get_parent()
	websocket_node.connect("connected", Callable(self, "_on_connected"))
	websocket_node.connect("connect_failed", Callable(self, "_on_connect_failed"))
	websocket_node.connect("received", Callable(self, "_on_data_received"))
	websocket_node.connect("closed", Callable(self, "_on_closed"))

func _on_connected(url):
	print("Connected to ", websocket_node.name, " server with: ", url)
	isReadyForSending = true

func _on_connect_failed():
	print("Connection failed!")
	isReadyForSending = false

func _on_closed(was_clean, reason):
	print("Connection closed, clean:", was_clean, "reason:", reason)
	isReadyForSending = false

func _on_data_received(data: PackedByteArray):
	_receiveBuffer += data.get_string_from_utf8()
	for message in _extractCompleteJsonObjects():
		emit_signal("message_received", message)

# The websocket addon has, in practice, sometimes delivered two distinct
# server responses concatenated into a single "received" call with no
# separator between them (e.g. "...}{..." - a step response immediately
# followed by a closeSession ack). Since every server message is exactly one
# JSON object, matching top-level braces reliably finds message boundaries
# no matter how the transport chunked or merged the bytes. As a side effect
# this also handles the opposite case - a single message split across two
# receive calls - by keeping whatever isn't a complete object yet buffered
# for the next call, instead of emitting a truncated/garbled message.
func _extractCompleteJsonObjects() -> Array:
	var messages: Array = []
	var depth := 0
	var start := -1
	var inString := false
	var escapeNext := false
	var i := 0
	while i < _receiveBuffer.length():
		var c := _receiveBuffer[i]
		if start == -1:
			if c == "{":
				start = i
				depth = 1
				inString = false
				escapeNext = false
			i += 1
			continue
		if inString:
			if escapeNext:
				escapeNext = false
			elif c == "\\":
				escapeNext = true
			elif c == "\"":
				inString = false
			i += 1
			continue
		if c == "\"":
			inString = true
		elif c == "{":
			depth += 1
		elif c == "}":
			depth -= 1
			if depth == 0:
				messages.append(_receiveBuffer.substr(start, i - start + 1))
				start = -1
		i += 1
	# Keep only the not-yet-complete tail (an in-progress object, or nothing).
	_receiveBuffer = _receiveBuffer.substr(start) if start != -1 else ""
	return messages

func sendMessage(message: String):
	websocket_node.send_string(message)

func getIsReady() -> bool:
	return isReadyForSending
