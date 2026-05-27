import asyncio
from playwright.async_api import async_playwright


async def main():

    async with async_playwright() as p:

        browser = await p.chromium.launch(
            headless=False
        )

        context = await browser.new_context(
            user_agent="Mozilla/5.0"
        )

        page = await context.new_page()

        await page.goto("https://x.com")

        print("ВОЙДИ В X АККАУНТ")

        input("После логина нажми Enter...")

        await context.storage_state(
            path="state.json"
        )

        print("STATE SAVED")

        await browser.close()


asyncio.run(main())