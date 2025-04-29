import discord
import aiohttp
import asyncio
import groq
import pathlib

# Api key
client_groq = groq.Groq(api_key="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")

# Discord Bot Setup using discord.Client
intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

# Audio transcription with Groq's Whisper model
def transcribe_audio(file_path):
    with file_path.open("rb") as file:
        transcription = client_groq.audio.transcriptions.create(
            file=(str(file_path), file.read()),
            model="whisper-large-v3",
            prompt="Specify context or spelling",
            response_format="json",
            temperature=0.0
        )
        return transcription.text

# Download attachment using aiohttp and pathlib
async def download_attachment(url, save_path):
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            if response.status == 200:
                data = await response.read()
                with save_path.open("wb") as f:
                    f.write(data)
            else:
                raise Exception("Failed to download file: status " + str(response.status))

# Spliting a long message into chunks of 2000 characters.
def split_message(message, limit=2000):
    return [message[i:i+limit] for i in range(0, len(message), limit)]

# Global conversation history: maps user id (as string) to list of conversation messages.
conversation_history = {}

@client.event
async def on_ready():
    print("Logged in as " + client.user.name + " - " + str(client.user.id))

@client.event
async def on_message(message: discord.Message):
    # Ignore messages sent by the bot itself.
    if message.author == client.user:
        return

    # Content Filter for "Bad words".
    filtered_words = ["shit", "bitch", "bastard", "fuck", "bullshit", "motherfucker", "asshole", "f*ck", "nigger", "nigga"] #no racism
    if any(bad_word in message.content.lower() for bad_word in filtered_words):
        try:
            await message.delete()
        except Exception as e:
            print("Error deleting message: " + str(e))
        await message.channel.send(message.author.mention + " Shame on you!")
        return

    # Handle Audio Attachments
    for attachment in message.attachments:
        if any(attachment.filename.lower().endswith(ext) for ext in [".mp3", ".m4a", ".wav", ".ogg"]):
            file_name = "audio_" + str(attachment.id) + ".mp3"
            file_path = pathlib.Path(file_name)
            await download_attachment(attachment.url, file_path)
            try:
                transcription_text = await asyncio.to_thread(transcribe_audio, file_path)
                await message.channel.send("Transcription: " + transcription_text)
            except Exception as e:
                await message.channel.send("Error transcribing audio: " + str(e))
            finally:
                if file_path.exists():
                    file_path.unlink()
            return

    # Only respond if the bot is mentioned
    if client.user not in message.mentions:
        return

    prompt = message.content.strip()
    if not prompt:
        return

    # Retrieve conversation history for this user
    user_id = str(message.author.id)
    history = conversation_history.get(user_id, [])
    # Generate a response with the history as context.
    try:
        full_messages = history + [{"role": "user", "content": prompt}]
        completion = client_groq.chat.completions.create(
            messages=full_messages,
            model="llama-3.3-70b-versatile",
        )
        response_text = completion.choices[0].message.content
        response_text += " " + message.author.mention
    except Exception as e:
        response_text = "Error fetching response: " + str(e)

    # Append new interactions to the user's conversation history.
    history.append({"role": "user", "content": prompt})
    history.append({"role": "assistant", "content": response_text})
    conversation_history[user_id] = history

    if len(response_text) <= 2000:
        await message.channel.send(response_text)
    else:
        filename = "long_response.txt"
        long_file = pathlib.Path(filename)
        with long_file.open("w", encoding="utf-8") as f:
            f.write(response_text)
        await message.channel.send("Response too long. See attached file:", file=discord.File(str(long_file)))
        long_file.unlink()

    # Process any other commands or events if necessary.
    await client.process_commands(message)

client.run()
