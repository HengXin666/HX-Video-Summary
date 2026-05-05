"""用隐身 Playwright 访问 bilibili.com 首页，提取反爬 cookies 供 yt-dlp 使用。"""
import asyncio
import sys
from pathlib import Path

COOKIES_FILE = Path(__file__).resolve().parent / "cookies.txt"


async def main():
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

        # --- stealth 补丁 ---
        await context.add_init_script(
            """
            // 隐藏 webdriver 标记
            Object.defineProperty(navigator, 'webdriver', { get: () => false });
            // 伪造 chrome.runtime
            window.chrome = { runtime: {}, loadTimes: function(){}, csi: function(){} };
            // 伪造 plugins
            Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
            Object.defineProperty(navigator, 'languages', { get: () => ['zh-CN', 'zh', 'en'] });
            // 伪造 platform
            Object.defineProperty(navigator, 'platform', { get: () => 'Win32' });
            // 伪造 hardwareConcurrency
            Object.defineProperty(navigator, 'hardwareConcurrency', { get: () => 8 });
            // 伪造 deviceMemory
            Object.defineProperty(navigator, 'deviceMemory', { get: () => 8 });
            // 权限查询伪装
            const origQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (params) =>
                params.name === 'notifications'
                    ? Promise.resolve({ state: Notification.permission, onchange: null })
                    : origQuery(params);
            // 消除 PhantomJS 痕迹
            delete window.callPhantom;
        """
        )

        page = await context.new_page()

        # 先访问首页让 B 站设置初始 cookies
        print("正在访问 bilibili.com 首页...")
        resp = await page.goto(
            "https://www.bilibili.com/",
            wait_until="domcontentloaded",
            timeout=30000,
        )
        print(f"首页响应状态: {resp.status}")

        # 等待 JS 挑战完成（B 站 WAF 会有 JS 挑战，需要额外时间）
        await asyncio.sleep(5)

        # 额外 scroll 一下，触发更多 JS 执行
        await page.evaluate("window.scrollTo(0, 300)")
        await asyncio.sleep(2)

        # 检查页面是否正常加载（如果被拦会看到验证页面）
        title = await page.title()
        print(f"页面标题: {title}")
        if "拦截" in title or "验证" in title or "403" in title:
            print("警告: 页面可能被拦截，但 cookies 可能仍然有效", file=sys.stderr)

        # 提取所有 cookies
        cookies = await context.cookies()
        print(f"获取到 {len(cookies)} 个 cookies")

        # 写 Netscape 格式
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
    asyncio.run(main())
