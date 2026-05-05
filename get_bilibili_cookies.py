"""用隐身 Playwright 访问 bilibili.com 首页 + 目标视频页，提取反爬 cookies 供 yt-dlp 使用。

用法: python get_bilibili_cookies.py <视频URL>
"""
import asyncio
import sys
from pathlib import Path

COOKIES_FILE = Path(__file__).resolve().parent / "cookies.txt"


async def main(video_url: str):
    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-setuid-sandbox",
                "--disable-infobars",
                "--disable-background-timer-throttling",
                "--disable-renderer-backgrounding",
            ],
        )

        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/131.0.0.0 Safari/537.36"
            ),
            locale="zh-CN",
            timezone_id="Asia/Shanghai",
        )

        await context.add_init_script(
            """
            Object.defineProperty(navigator, 'webdriver', { get: () => false });
            window.chrome = { runtime: {}, loadTimes: function(){}, csi: function(){} };
            Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
            Object.defineProperty(navigator, 'languages', { get: () => ['zh-CN', 'zh', 'en'] });
            Object.defineProperty(navigator, 'platform', { get: () => 'Win32' });
            Object.defineProperty(navigator, 'hardwareConcurrency', { get: () => 8 });
            Object.defineProperty(navigator, 'deviceMemory', { get: () => 8 });
            const origQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (params) =>
                params.name === 'notifications'
                    ? Promise.resolve({ state: Notification.permission, onchange: null })
                    : origQuery(params);
            delete window.callPhantom;
        """
        )

        page = await context.new_page()

        # 第1步：访问首页，获取初始 cookies + 建立 Referer 链
        print("正在访问 bilibili.com 首页...")
        resp = await page.goto(
            "https://www.bilibili.com/",
            wait_until="domcontentloaded",
            timeout=30000,
        )
        print(f"首页响应状态: {resp.status}")
        await asyncio.sleep(5)
        await page.evaluate("window.scrollTo(0, 300)")
        await asyncio.sleep(2)
        print(f"首页标题: {await page.title()}")

        # 第2步：访问目标视频页，获取页面专属 cookies
        print(f"\n正在访问视频页: {video_url}")
        try:
            resp2 = await page.goto(
                video_url,
                wait_until="domcontentloaded",
                timeout=30000,
                referer="https://www.bilibili.com/",
            )
            print(f"视频页响应状态: {resp2.status}")
            if resp2.status == 200:
                await asyncio.sleep(5)
                await page.evaluate("window.scrollTo(0, 500)")
                await asyncio.sleep(3)
                print(f"视频页标题: {await page.title()}")
            else:
                print(f"视频页非200 ({resp2.status})，跳过交互，保留已有cookies")
        except Exception as e:
            print(f"视频页访问异常: {e}，保留已有cookies")

        # 提取所有 cookies
        cookies = await context.cookies()
        print(f"\n获取到 {len(cookies)} 个 cookies")

        COOKIES_FILE.write_text(_to_netscape(cookies), encoding="utf-8")
        print(f"cookies 已写入 {COOKIES_FILE}")

        await browser.close()


def _to_netscape(cookies: list) -> str:
    lines = ["# Netscape HTTP Cookie File"]
    for c in cookies:
        domain = c.get("domain", "")
        flag = "TRUE" if domain.startswith(".") else "FALSE"
        path = c.get("path", "/")
        secure = "TRUE" if c.get("secure") else "FALSE"
        expires = c.get("expires", -1)
        expiry = str(int(expires)) if expires and expires != -1 else "0"
        name = c.get("name", "")
        value = c.get("value", "")
        lines.append(f"{domain}\t{flag}\t{path}\t{secure}\t{expiry}\t{name}\t{value}")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python get_bilibili_cookies.py <视频URL>", file=sys.stderr)
        sys.exit(1)
    asyncio.run(main(sys.argv[1]))
