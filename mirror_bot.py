import asyncio
import os
import sys
from telethon import TelegramClient, events
from telethon.sessions import StringSession

# Fetch configuration strictly from Koyeb Environment Variables
API_ID = os.getenv('API_ID')
API_HASH = os.getenv('API_HASH')
SESSION_STRING = os.getenv('SESSION_STRING')
TG_RTMP_URL = os.getenv('TG_RTMP_URL')
SOURCE_CHAT = os.getenv(
    'SOURCE_CHAT', 'source_live_channel_username'
)  # Can be username or ID

# Validate presence of mandatory configuration
if not API_ID or not API_HASH or not SESSION_STRING:
  print(
      '[-] Fatal Error: Missing API_ID, API_HASH, or SESSION_STRING in environment variables!',
      file=sys.stderr,
  )
  sys.exit(1)

try:
  API_ID = int(API_ID)
except ValueError:
  print('[-] Fatal Error: API_ID must be a valid integer!', file=sys.stderr)
  sys.exit(1)

# Initialize Telethon client with StringSession optimized for headless cloud execution
client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)
active_stream_process = None


async def start_ffmpeg_mirror(source_stream_identifier, rtmp_destination):
  global active_stream_process
  if active_stream_process and active_stream_process.returncode is None:
    print('[!] Mirror process is already running.')
    return

  print(
      f'[+] Initializing silent FFmpeg pipe to destination: {rtmp_destination}'
  )

  # Advanced FFmpeg argument configuration for low-latency silent restreaming
  ffmpeg_cmd = [
      'ffmpeg',
      '-re',
      '-i',
      source_stream_identifier,
      '-c:v',
      'libx264',
      '-preset',
      'ultrafast',
      '-tune',
      'zerolatency',
      '-c:a',
      'aac',
      '-b:a',
      '128k',
      '-f',
      'flv',
      rtmp_destination,
  ]

  try:
    active_stream_process = await asyncio.create_subprocess_exec(
        *ffmpeg_cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    print(
        f'[+] Silent mirror stream active with PID {active_stream_process.pid}'
    )
  except Exception as e:
    print(f'[-] Failed to spawn FFmpeg mirror process: {e}')


@client.on(events.ChatAction)
async def handle_chat_action(event):
  try:
    # Check if the event relates to a group call or live broadcast state change
    if event.group_call:
      chat = await event.get_chat()
      chat_username = getattr(chat, 'username', str(chat.id))

      # Match against designated source chat
      if str(chat_username) == str(SOURCE_CHAT) or chat.id == int(
          SOURCE_CHAT
          if SOURCE_CHAT.lstrip('-').isdigit()
          else '0'
      ):
        print(
            f'[+] Live broadcast action detected in target source: {chat_username}'
        )

        if TG_RTMP_URL:
          # Trigger background mirroring worker task safely without blocking loop
          asyncio.create_task(
              start_ffmpeg_mirror('pipe:0', TG_RTMP_URL)
          )
        else:
          print('[-] Warning: TG_RTMP_URL environment variable is not defined.')
  except Exception as e:
    print(f'[-] Error processing live stream action event: {e}')


def main():
  print('Starting production Telegram live mirror worker for Koyeb...')
  client.start()
  print('[+] Userbot session successfully authenticated and listening silently.')
  client.run_until_disconnected()


if __name__ == '__main__':
  main()
