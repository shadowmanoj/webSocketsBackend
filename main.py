import asyncio
import websockets
import json

active_connections = {}

user_matches = {}

waiting_users = asyncio.Queue()


async def send_private_message(message, to_user_id):
    if to_user_id in active_connections:
        try:
            await active_connections[to_user_id].send(json.dumps(message))
        except websockets.exceptions.ConnectionClosed:
            pass


async def handle_client(websocket, path):
    try:
        user_id = path.strip('/')

        active_connections[user_id] = websocket

        if not waiting_users.empty():
            matched_user_id = await waiting_users.get()

            match_message = {
                "type": "match",
                "user": user_id,
                "matched_user": matched_user_id
            }
            await send_private_message(match_message, user_id)
            await send_private_message(match_message, matched_user_id)

            user_matches[user_id] = matched_user_id
            user_matches[matched_user_id] = user_id

        else:
            await waiting_users.put(user_id)

        while True:
            message = await websocket.recv()
            print(f"Received from {user_id}: {message}")

            matched_user_id = user_matches.get(user_id, None)
            message_data = json.loads(message)
            if matched_user_id:
                content = ""
                if message_data['type'] == 'message':
                    content = message_data['content']
                private_message = {
                    "type": message_data['type'],
                    "user": user_id,
                    "content": content
                }

                await send_private_message(private_message, matched_user_id)
                if message_data["type"] == "close":
                    user_id = active_connections.pop(matched_user_id)
                    active_connections.pop(user_id)

    except websockets.exceptions.ConnectionClosed:
        private_message = {
            "type": "close",
            "user": user_id
        }
        await send_private_message(private_message, user_id)
        pass
    finally:
        if user_id in active_connections:
            del active_connections[user_id]
            while not waiting_users.empty():
                if waiting_users.get() == user_id:
                    break
            if user_id in user_matches:
                matched_user_id = user_matches[user_id]
                del user_matches[user_id]
                del user_matches[matched_user_id]


async def main():
    server = await websockets.serve(handle_client, "localhost", 8765)
    await server.wait_closed()


if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(main())
    asyncio.get_event_loop().run_forever()
