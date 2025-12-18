import asyncio
import websockets
import sys

async def test_connection():
    uri = "ws://localhost:8080/ws/chat"
    try:
        async with websockets.connect(uri) as websocket:
            print(f"Successfully connected to {uri}")
            await websocket.close()
    except Exception as e:
        print(f"Failed to connect: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(test_connection())
