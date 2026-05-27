import asyncio
import os
import requests

from playwright.async_api import async_playwright
from telegram import Bot
from googletrans import Translator

BOT_TOKEN = "8807434169:AAFjQK1be1u1xjkN_0cbjsIOjy2JdPPksso"
CHANNEL_ID = "@fabrizioromanoruskiy"

TWITTER_URL = "https://x.com/gazaryan001"

CHECK_INTERVAL = 20

translator = Translator()
bot = Bot(token=BOT_TOKEN)


# =========================
# LAST TWEET STORAGE
# =========================

def save_last_tweet(tweet_id):
    with open("seen.txt", "w") as f:
        f.write(tweet_id)


def load_last_tweet():
    try:
        with open("seen.txt", "r") as f:
            return f.read().strip()
    except:
        return None


last_tweet = load_last_tweet()


# =========================
# TRANSLATION
# =========================

def translate_text(text):
    try:
        translated = translator.translate(text, dest="ru")
        return translated.text
    except Exception as e:
        print("TRANSLATE ERROR:", e)
        return text


# =========================
# TELEGRAM
# =========================

async def send_post(text, image_path=None):
    try:
        if image_path and os.path.exists(image_path):

            with open(image_path, "rb") as photo:
                await bot.send_photo(
                    chat_id=CHANNEL_ID,
                    photo=photo,
                    caption=text,
                    parse_mode="HTML"
                )

        else:
            await bot.send_message(
                chat_id=CHANNEL_ID,
                text=text,
                parse_mode="HTML"
            )

    except Exception as e:
        print("TG ERROR:", e)


# =========================
# DOWNLOAD IMAGE
# =========================

def download_image(url):

    try:
        os.makedirs("media", exist_ok=True)

        path = "media/latest.jpg"

        response = requests.get(url)

        with open(path, "wb") as f:
            f.write(response.content)

        return path

    except Exception as e:
        print("IMAGE ERROR:", e)
        return None


# =========================
# CLEAN TEXT
# =========================

def clean_tweet_text(raw_text):

    lines = raw_text.split("\n")

    cleaned = []

    for line in lines:

        line = line.strip()

        if not line:
            continue

        banned = [
            "Закреплено",
            "Pinned",
            "Quote",
            "Replying",
            "GIF",
            "ALT",
        ]

        if line in banned:
            continue

        # статистика
        if (
            "тыс." in line
            or "млн" in line
            or line.isdigit()
        ):
            continue

        # ссылки
        if "http" in line:
            continue

        # дубликаты
        if line in cleaned:
            continue

        cleaned.append(line)

    # убираем имя и username
    if len(cleaned) > 2:
        cleaned = cleaned[2:]

    text = "\n".join(cleaned[:8])

    return text


# =========================
# SCRAPING
# =========================

async def get_latest_tweet(page):

    await page.goto(
        TWITTER_URL,
        wait_until="domcontentloaded",
        timeout=60000
    )
    await context.storage_state(path="state.json")
    await page.wait_for_timeout(5000)

    articles = page.locator("article")

    count = await articles.count()

    print("ARTICLES:", count)

    if count == 0:
        return None

    first = articles.first

    raw_text = await first.inner_text()

    text = clean_tweet_text(raw_text)

    # LINKS
    links = await first.locator("a").evaluate_all(
        "els => els.map(e => e.href)"
    )

    tweet_link = None

    for link in links:
        if "/status/" in link:
            tweet_link = link
            break

    # IMAGES
    image_url = None

    images = await first.locator("img").evaluate_all(
        "els => els.map(e => e.src)"
    )

    for img in images:
        if "media" in img:
            image_url = img
            break

    return {
        "text": text,
        "url": tweet_link,
        "image": image_url
    }


# =========================
# FORMAT POST
# =========================

def build_message(original_text, translated_text, tweet_url):

    here_we_go = "HERE WE GO" in original_text.upper()

    if here_we_go:
        title = "🚨 <b>HERE WE GO!</b>"
    else:
        title = "⚡️ <b>Fabrizio Romano</b>"

    message = (
        f"{title}\n\n"
        f"{translated_text}\n\n"
        f"<a href='{tweet_url}'>Источник</a>"
    )

    return message


# =========================
# MAIN LOOP
# =========================

async def main():

    global last_tweet

    print("STARTED")

    async with async_playwright() as p:

        browser = await p.chromium.launch(
            headless=True
        )

        context = await browser.new_context(
            storage_state="state.json"
        )
        page = await context.new_page()
        input("После логина нажми Enter...")

        await context.storage_state(path="state.json")

        print("STATE SAVED")
        while True:

            try:
                print("CHECKING...")

                tweet = await get_latest_tweet(page)

                print(tweet)

                if tweet:

                    # первый запуск
                    if last_tweet is None:

                        last_tweet = tweet["url"]

                        save_last_tweet(last_tweet)

                        print("FIRST RUN SKIP")

                        await asyncio.sleep(CHECK_INTERVAL)

                        continue

                    # уже отправляли
                    if tweet["url"] == last_tweet:

                        await asyncio.sleep(CHECK_INTERVAL)

                        continue

                    # новый пост
                    last_tweet = tweet["url"]

                    save_last_tweet(last_tweet)

                    translated = translate_text(tweet["text"])

                    message = build_message(
                        tweet["text"],
                        translated,
                        tweet["url"]
                    )

                    image_path = None

                    if tweet["image"]:
                        image_path = download_image(tweet["image"])

                    await send_post(
                        message,
                        image_path
                    )

                    print("POSTED")

            except Exception as e:
                print("ERROR:", e)

            await asyncio.sleep(CHECK_INTERVAL)


asyncio.run(main())