import asyncio
import os
import requests

from playwright.async_api import async_playwright
from googletrans import Translator

# =========================
# CONFIG
# =========================

BOT_TOKEN = "8807434169:AAFjQK1be1u1xjkN_0cbjsIOjy2JdPPksso"
CHANNEL_ID = "@fabrizioromanoruskiy"

TWITTER_URL = "https://x.com/FabrizioRomano"

CHECK_INTERVAL = 20

translator = Translator()


# =========================
# LAST TWEET STORAGE
# =========================

def save_last_tweet(tweet_id):

    with open("seen.txt", "w", encoding="utf-8") as f:
        f.write(tweet_id)


def load_last_tweet():

    try:

        with open("seen.txt", "r", encoding="utf-8") as f:
            return f.read().strip()

    except:
        return None


last_tweet = load_last_tweet()

# =========================
# TRANSLATION
# =========================

def translate_text(text):

    try:

        translated = translator.translate(
            text,
            dest="ru"
        )

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

            url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"

            with open(image_path, "rb") as photo:

                response = requests.post(
                    url,
                    files={"photo": photo},
                    data={
                        "chat_id": CHANNEL_ID,
                        "caption": text[:1024],
                        "parse_mode": "HTML"
                    }
                )

                print(response.text)

        else:

            url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

            response = requests.post(
                url,
                data={
                    "chat_id": CHANNEL_ID,
                    "text": text,
                    "parse_mode": "HTML",
                    "disable_web_page_preview": False
                }
            )

            print(response.text)

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

import re

import re

def clean_tweet_text(raw_text):

    lines = raw_text.split("\n")

    cleaned = []

    banned = [
        "Закреплено",
        "Pinned",
        "Replying",
        "Quote"
    ]

    for line in lines:

        line = line.strip()

        if not line:
            continue

        # мусор
        if line in banned:
            continue

        # username
        if line.startswith("@"):
            continue

        # время
        if re.match(r"^\d+[smhd]$", line):
            continue

        # просмотры/статистика
        if re.match(r"^[\d\.,]+\s?[KMB]?$", line):
            continue

        if any(
            x in line.lower()
            for x in [
                "views",
                "view",
                "reposts",
                "likes",
                "replies"
            ]
        ):
            continue

        # ссылки media
        if "pic.twitter.com" in line:
            continue

        cleaned.append(line)

    # убираем имя аккаунта
    if len(cleaned) > 0:

        if "Fabrizio Romano" in cleaned[0]:
            cleaned.pop(0)

    text = "\n".join(cleaned)

    return text.strip()
# =========================
# SCRAPING
# =========================

async def get_latest_tweet(page):

    await page.goto(
        TWITTER_URL,
        wait_until="domcontentloaded",
        timeout=60000
    )

    await page.wait_for_timeout(8000)

    await page.mouse.wheel(0, 1500)

    await page.wait_for_timeout(3000)

    articles = page.locator("article")

    count = await articles.count()

    print("ARTICLES:", count)

    if count == 0:
        return None

    latest_tweet = None
    latest_time = None

    for i in range(count):

        try:

            article = articles.nth(i)

            # время tweet
            time_element = article.locator("time")

            if await time_element.count() == 0:
                continue

            datetime_value = await time_element.get_attribute(
                "datetime"
            )

            if not datetime_value:
                continue

            # текст
            raw_text = await article.inner_text()

            # пропускаем закреп
            if "Закреплено" in raw_text or "Pinned" in raw_text:
                continue

            text = clean_tweet_text(raw_text)

            # ссылка
            links = await article.locator("a").evaluate_all(
                "els => els.map(e => e.href)"
            )

            tweet_link = None

            for link in links:

                if "/status/" in link:

                    tweet_link = link

                    break

            if not tweet_link:
                continue

            # картинки
            image_url = None

            images = await article.locator("img").evaluate_all(
                "els => els.map(e => e.src)"
            )

            for img in images:

                if "media" in img:

                    image_url = img

                    break

            # выбираем самый новый
            if (
                latest_time is None
                or datetime_value > latest_time
            ):

                latest_time = datetime_value

                latest_tweet = {
                    "text": text,
                    "url": tweet_link,
                    "image": image_url
                }

        except Exception as e:

            print("ARTICLE ERROR:", e)

    return latest_tweet
# =========================
# FORMAT POST
# =========================

def build_message(
    original_text,
    translated_text,
    tweet_url
):

    here_we_go = (
        "HERE WE GO" in original_text.upper()
    )

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
            storage_state="state.json",
            viewport={
                "width": 1400,
                "height": 1000
            },
            user_agent="Mozilla/5.0",
            locale="en-US"
        )

        page = await context.new_page()

        while True:

            try:

                print("CHECKING...")

                tweet = await get_latest_tweet(page)

                print(tweet)

                if tweet:

                    # первый запуск
                    if last_tweet is None:

                        last_tweet = tweet["url"]

                        save_last_tweet(
                            last_tweet
                        )

                        print("FIRST RUN SKIP")

                        await asyncio.sleep(
                            CHECK_INTERVAL
                        )

                        continue

                    # уже отправляли
                    if tweet["url"] == last_tweet:

                        await asyncio.sleep(
                            CHECK_INTERVAL
                        )

                        continue

                    # новый пост
                    last_tweet = tweet["url"]

                    save_last_tweet(
                        last_tweet
                    )

                    translated = translate_text(
                        tweet["text"]
                    )

                    message = build_message(
                        tweet["text"],
                        translated,
                        tweet["url"]
                    )

                    image_path = None

                    if tweet["image"]:

                        image_path = download_image(
                            tweet["image"]
                        )

                    await send_post(
                        message,
                        image_path
                    )

                    print("POSTED")

            except Exception as e:

                print("ERROR:", e)

            await asyncio.sleep(
                CHECK_INTERVAL
            )

asyncio.run(main())