import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

logger.info("BOT FILE LOADED")
import os

import aiohttp
import discord
from discord.ext import commands
from dotenv import load_dotenv
from common.constants import NOTION_CATEGORIES

# 1. 환경 변수 및 장고 설정 로드
load_dotenv()
logger.info("imports done")
token = os.getenv("DISCORD_BOT_TOKEN")
logger.debug(f"DISCORD_BOT_TOKEN set: {bool(token)}")
DJANGO_API_URL = "http://web:8000/archiver/qna/"

# 2. 봇 설정
intents = discord.Intents.default()
intents.message_content = True
intents.messages = True
intents.guilds = True
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)
logger.info("bot object created")

try:
    intents.threads = True
except AttributeError:
    logger.warning("이 버전의 라이브러리는 threads속성을 지원하지 않습니다")


@bot.event
async def on_ready():
    logger.info(f"✅ 봇 로그인 성공: {bot.user.name}")


async def call_django_api(question_text):
    async with aiohttp.ClientSession() as session:
        async with session.post(
            DJANGO_API_URL,
            json={"question_text": question_text},
            timeout=aiohttp.ClientTimeout(total=120),
        ) as resp:
            return await resp.json()


async def send_long_message(reply_target, content, prefix=""):
    """
    디스코드의 2000자 제한 떄문에 메세지 제한
    reply_target: 답장을 보낼 대상
    content: 보낼 내용
    prefix: 첫번쨰 메세지 앞에 붙을 말
    """
    full_text = f"{prefix}\n{content}" if prefix else content

    if len(full_text) <= 2000:
        await reply_target.reply(full_text)
    else:
        chunks = [full_text[i : i + 1990] for i in range(0, len(full_text), 1990)]
        await reply_target.reply(chunks[0])
        for chunk in chunks[1:]:
            await reply_target.channel.send(chunk)


@bot.event
async def on_message(message):
    logger.info(
        f"메세지: {message.content} | 채널타입: {message.channel.type} | 작성자: {message.author}"
    )
    # 봇 본인의 메시지는 무시
    if message.author == bot.user:
        return

    if message.content.startswith("!질문"):
        question_text = message.content.replace("!질문", "").strip()

        if not question_text:
            await message.reply("❓ 질문 내용을 입력해주세요")
            return

        status_msg = await message.channel.send("🤖 분석 중입니다...")

        try:
            result = await call_django_api(question_text)
            logger.debug(f"🔥 Django API 응답: {result}")

            status = result.get("status")

            if status == "similar_found":
                notion_url = result.get("notion_page_url")
                if notion_url:
                    await message.reply(f"**이미 정리된 질문입니다!**\n**노션링크** {notion_url}")
                else:
                    await message.reply("**이미 정리된 질문입니다!** 노션 게시판을 확인해주세요.")
            elif status == "new":
                ai_ans = result.get("ai_answer", "답변 생성에 실패했습니다.")
                await send_long_message(message, ai_ans, prefix="🆕 **분석 결과**")
            else:
                await message.reply(f"알수 없는 서버 응답입니다 (status: {status})")

        except Exception as e:
            await message.reply(f"❌ 서버 오류: {str(e)[:200]}")

        finally:
            await status_msg.delete()

    # 3. 봇 실행


if token:
    bot.run(token)
else:
    logger.error("디스코드 토큰이 없습니다 env 파일을 확인해주세요")
