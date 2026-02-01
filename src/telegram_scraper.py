import asyncio
import os
import json
from typing import List, Dict
from dotenv import load_dotenv
from datetime import datetime, timedelta, timezone, date
from telethon import TelegramClient, events

load_dotenv(".env")


from .database import init_db, insert_message_sync
# import pandas as pd




API_ID = int(os.getenv("TELEGRAM_API_ID"))
API_HASH = os.getenv("TELEGRAM_API_HASH")
PHONE_NUMBER = os.getenv("TELEPHONE_NUMBER")
SESSION_NAME = os.getenv("TELEGRAM_SESSION_NAME", "my_telegram_session")
TELEGRAM_GROUP_NAME = os.getenv("TELEGRAM_GROUP")

# Create the client instance
client = TelegramClient(session = SESSION_NAME, api_id=API_ID, api_hash=API_HASH)


async def connect_telegram_client(client: TelegramClient) -> TelegramClient:
    """
    Connects and authorizes the Telegram client.
    Args:
        client (TelegramClient): The Telegram client instance.
    Returns:
        TelegramClient: The connected and authorized Telegram client.
    """
    await client.connect()

    # Check if the user is already authorized, otherwise prompt the user to authorize the client with code
    if not await client.is_user_authorized():
        await client.send_code_request(phone=PHONE_NUMBER)
        await client.sign_in(phone=PHONE_NUMBER, code=input('Enter the code you received on Telegram: '))

    print("Telegram client connected and authorized.")
    return client


async def run_db_insert(row: Dict) -> None:
    """
    Asynchronously inserts a message row into the database.

    Args:
        row (Dict): A dictionary representing the message data to be inserted.
    """
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, insert_message_sync, row)


async def resolve_entity(client: TelegramClient, target: str):
    """
    Resolves the entity for the given group name.
    Try get_entity() first; fall back to searching dialogs by display name.

    Args:
        client (TelegramClient): The connected Telegram client.
        target (str): The name of the Telegram group.
    Returns:
        The resolved entity.
    Raises:
        ValueError: If the group with the specified name is not found.
    """
    try:
        return await client.get_entity(target)
    
    except Exception:
        async for dialog in client.iter_dialogs():
            if dialog.name == target:
                return dialog.entity
    
    raise ValueError(f"Cannot find group '{target}'.")


async def fetch_and_store_recent(client: TelegramClient, entity, start_date: date):
    """
    Fetches recent messages from the specified Telegram group and stores them in the database.

    Args:
        client (TelegramClient): The connected Telegram client.
        entity: The resolved entity for the Telegram group.
        start_date (date): The date from which to start fetching messages.
    """
    async for message in client.iter_messages(entity):
        if not message.date:
            continue

        if message.date.date() < start_date:
            break
        
        row = {
            "message_id": message.id,
            "group_id": TELEGRAM_GROUP_NAME,
            "date": message.date.strftime("%Y-%m-%d %H:%M:%S"),
            "sender_id": message.sender_id,
            "channel_id": message.peer_id.channel_id if message.peer_id and hasattr(message.peer_id, 'channel_id') else None,
            "text": message.text,
            "views": message.views,
            "replies": message.replies,
            # "raw_json": message.to_dict() if hasattr(message, 'to_dict') else None
        }

        raw_message = message.to_dict() if hasattr(message, 'to_dict') else None
        row["raw_json"] = json.loads(json.dumps(raw_message, default=str)) if raw_message else None
        
        await run_db_insert(row)

async def handle_new_message(event):
    """Telethon event handler for new messages.
    Creates a new message entry in the database upon receiving a new message.
    Args:
        event: The new message event.
    """
    message = event.message
    
    row = {
        "message_id": message.id,
        "group_id": TELEGRAM_GROUP_NAME,
        "date": message.date.strftime("%Y-%m-%d %H:%M:%S"),
        "sender_id": message.sender_id,
        "channel_id": message.peer_id.channel_id if message.peer_id and hasattr(message.peer_id, 'channel_id') else None,
        "text": message.text,
        "views": message.views,
        "replies": message.replies,
        # "raw_json": message.to_dict() if hasattr(message, 'to_dict') else None
    }

    raw_message = message.to_dict() if hasattr(message, 'to_dict') else None
    row["raw_json"] = json.loads(json.dumps(raw_message, default=str)) if raw_message else None
    
    try:
        await run_db_insert(row)
        print(f"Inserted new message {message.id} into the database.")
    except Exception as e:
        print(f"DB insertion error for message {message.id}: {e}")


async def main():
    ## Intitalize the database
    init_db()
    print("Database initialized.")

    # start/connect
    telegram_client = await connect_telegram_client(client)
    print("Telegram client is ready.")


    # Resolve the target entity
    if not TELEGRAM_GROUP_NAME:
        print("No group name specified in TELEGRAM_GROUP environment variable.")
        raise ValueError("TELEGRAM_GROUP environment variable is required.")
    
    entity = await resolve_entity(telegram_client, TELEGRAM_GROUP_NAME)

    # Fetch and store recent messages from the last 3 days
    start_date = datetime.now(tz=timezone.utc).date() - timedelta(days=3)
    await fetch_and_store_recent(
        client=telegram_client,
        entity=entity,
        start_date=start_date
    )
    print(f"Fetched and stored recent messages from {start_date} to {datetime.now(tz=timezone.utc).date()}.")

    # Register handler for specific entity
    telegram_client.add_event_handler(
        handle_new_message,
        events.NewMessage(chats=[entity])
    )
    print(f"Registered event handler for incoming messages in entity {entity.title}.")

    # Keep running and listening for new messages
    await telegram_client.run_until_disconnected()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    
    except KeyboardInterrupt:
        print("Stopped by user. Shutting down gracefully.")

    except Exception as e:
        print(f"Error: {e}")
