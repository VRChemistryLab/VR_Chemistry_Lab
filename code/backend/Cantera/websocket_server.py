import asyncio
import websockets
import json
from simulation_hub import decideWhatToCallAndCall, buildResponseEnvelope

PORT = 50505

# Keep strong references to in-flight tasks. Without this, asyncio may
# garbage-collect a task mid-execution since create_task() only holds a
# weak reference internally.
_background_tasks: set[asyncio.Task] = set()


async def handle_websocket(websocket):
    # Serializes all writes to this connection - websockets.send() is not
    # safe to call concurrently from multiple tasks on the same connection;
    # interleaved sends can corrupt/merge frames on the wire.
    send_lock = asyncio.Lock()
    try:
        while True:
            message = await websocket.recv()
            if isinstance(message, bytes):
                message = message.decode("utf-8")

            task = asyncio.create_task(_processAndRespond(websocket, message, send_lock))
            _background_tasks.add(task)
            task.add_done_callback(_background_tasks.discard)
    except websockets.ConnectionClosed:
        print("Client disconnected")


async def _processAndRespond(websocket, message, send_lock):
    try:
        output = await decideWhatToCallAndCall(message)
        if output is None:
            output = buildResponseEnvelope(
                False,
                error={"code": "NULL_OUTPUT", "message": "internal handler returned no output"},
            )
            print("error: internal handler returned no output")
        string_outputAsJson = json.dumps(output, indent=2)
    except Exception as e:
        string_outputAsJson = json.dumps(
            buildResponseEnvelope(False, error={"code": "INTERNAL_ERROR", "message": str(e)})
        )

    try:
        # Serialize the actual write so two nearly-simultaneous responses
        # (e.g. an init ack and a closeSession ack for a just-merged group)
        # can never interleave into one corrupted/concatenated payload.
        async with send_lock:
            await websocket.send(string_outputAsJson)
    except websockets.ConnectionClosed:
        pass


async def main():
    print(f"Python WebSocket server (Cantera) running on ws://localhost:{PORT}")
    async with websockets.serve(handle_websocket, "localhost", PORT):
        await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(main())