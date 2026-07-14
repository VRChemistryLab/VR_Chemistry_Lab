import asyncio
import websockets
import json
from reaktoro_hub import decideWhatToCallAndCall

# Different port from the Cantera server (50505) - the two run as separate
# processes in separate environments (native libs conflict, see ONBOARDING.md),
# and Godot's DataSynchronizer already supports one WebSocketClient per engine.
PORT = 50506

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
            output = {"error1, output is none": -1}
            print("error1, output is none")
        string_outputAsJson = json.dumps(output, indent=2)
    except Exception as e:
        string_outputAsJson = json.dumps({"error2": str(e)})

    try:
        async with send_lock:
            await websocket.send(string_outputAsJson)
    except websockets.ConnectionClosed:
        pass


async def main():
    print(f"Python WebSocket server (Reaktoro) running on ws://localhost:{PORT}")
    async with websockets.serve(handle_websocket, "localhost", PORT):
        await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(main())
