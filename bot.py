import discord
from discord.ext import commands
import aiohttp
import os
import asyncio
import json
import io

with open('conf.json', 'r') as f:
    config = json.load(f)

TOKEN = config["token"]
API_KEY = config["api_key"]

intents = discord.Intents.all()
bot = commands.Bot(command_prefix='!', intents=intents)

async def check_document_status(api_key, document_id, document_key):
    status_url = f"https://api.deepl.com/v2/document/{document_id}"
    headers = {
        "Authorization": f"DeepL-Auth-Key {api_key}",
        "Content-Type": "application/json"
    }
    data = {
        "document_key": document_key
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(status_url, headers=headers, json=data) as response:
            status_data = await response.json()
            return status_data["status"]

async def translate_with_deepl(api_key, file_path, target_language):
    upload_url = "https://api.deepl.com/v2/document"
    headers = {
        "Authorization": f"DeepL-Auth-Key {api_key}"
    }

    data = {
        "target_lang": target_language
    }
    
    async with aiohttp.ClientSession() as session:
        with open(file_path, 'rb') as file:
            multipart = aiohttp.MultipartWriter()
            part = multipart.append(file)
            part.set_content_disposition('form-data', name='file', filename = os.path.basename(file_path))
            for key, value in data.items():
                multipart.append(value, {'Content-Disposition': f'form-data; name="{key}"'})
            
            async with session.post(upload_url, headers = headers, data = multipart) as response:
                upload_response_json = await response.json()

    if "document_id" in upload_response_json:
        document_id = upload_response_json["document_id"]
        document_key = upload_response_json["document_key"]
        
        while True:
            status = await check_document_status(api_key, document_id, document_key)
            if status == "done":
                break
            await asyncio.sleep(20)
        
        download_url = f"https://api.deepl.com/v2/document/{document_id}/result"
        download_data = {
            "document_key": document_key
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(download_url, headers = headers, json = download_data) as response:
                if response.status == 200:
                    translated_file_name = "translated_" + os.path.basename(file_path)
                    
                    byte_buffer = io.BytesIO()
                    while True:
                        chunk = await response.content.read(8192)
                        if not chunk:
                            break
                        byte_buffer.write(chunk)
                    
                    byte_buffer.seek(0)
                    return translated_file_name, byte_buffer
                else:
                    json_response = await response.json()
                    raise Exception("Translation failed:", json_response)
    else:
        raise Exception("Translation failed:", upload_response_json)

@bot.event
async def on_ready():
    print(f'{bot.user} 에 로그인하였습니다!')

@bot.command()
async def translate(ctx, target_language = "KO"):
    if not ctx.message.attachments:
        await ctx.send("파일을 첨부해주세요.")
        return
    
    await ctx.send("Translate Start")

    attachment = ctx.message.attachments[0]
    file_path = f"./{attachment.filename}"
    await attachment.save(file_path)

    try:
        translated_file_name, byte_buffer = await translate_with_deepl(API_KEY, file_path, target_language)
        await ctx.send(f"번역이 완료되었습니다.", file = discord.File(byte_buffer, filename = translated_file_name))
    except Exception as e:
        await ctx.send(str(e))
    os.remove(file_path)

bot.run(TOKEN)