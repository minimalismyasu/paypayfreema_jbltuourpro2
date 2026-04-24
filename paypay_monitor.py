from __future__ import annotations

import html
import json
import os
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable
from urllib.request import Request, urlopen

from playwright.sync_api import sync_playwright


DEFAULT_SEARCH_URL = (
    "https://paypayfleamarket.yahoo.co.jp/search/"
    "jbl%20tour%20pro2?minPrice=10000&maxPrice=15000&conditions=NEW%2CUSED10"
)
SEARCH_URL = os.getenv("PAYPAY_URL", DEFAULT_SEARCH_URL)
STATE_FILE = Path(__file__).resolve().parent / "state" / "paypay_tour_pro2.json"


@dataclass(frozen=True)
class Item:
    url: str
    title: str
    price: str

    @property
    def key(self) -> str:
        normalized_title = re.sub(r"\s+", " ", self.title).strip().casefold()
        normalized_price = re.sub(r"\s+", "", self.price)
        return f"{self.url}|{normalized_price}|{normalized_title}"


def fetch_page_text(url: str) -> tuple[str, list[Item]]:
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
            ],
        )
        context = browser.new_context(
            locale="ja-JP",
            timezone_id="Asia/Tokyo",
            viewport={"width": 1440, "height": 1600},
        )
        page = context.new_page()
        page.goto(url, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(5000)
        text = page.locator("body").inner_text(timeout=15000)

        items: list[Item] = []
        seen = set()
        links = page.locator('a[href*="/item/"]')
        for index in range(links.count()):
            link = links.nth(index)
            href = link.get_attribute("href") or ""
            img = link.locator("img[alt]").first
            title = (img.get_attribute("alt") or "").strip()
            price = extract_price(link.inner_text(timeout=5000))
            if not href or not title or not price:
                continue
            absolute_url = href if href.startswith("http") else f"https://paypayfleamarket.yahoo.co.jp{href}"
            item = Item(url=absolute_url, title=title, price=price)
            if item.key in seen:
                continue
            seen.add(item.key)
            items.append(item)

        context.close()
        browser.close()
        return text, items


def extract_price(text: str) -> str:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    for line in lines:
        if re.fullmatch(r"[0-9,]+円", line):
            return line
    return ""


def load_state(path: Path) -> dict:
    if not path.exists():
        return {"initialized": False, "seen_keys": [], "items": []}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"initialized": False, "seen_keys": [], "items": []}


def save_state(path: Path, items: Iterable[Item]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    items_list = list(items)
    payload = {
        "initialized": True,
        "seen_keys": [item.key for item in items_list],
        "items": [asdict(item) for item in items_list],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def telegram_enabled() -> bool:
    return bool(os.getenv("TELEGRAM_BOT_TOKEN")) and bool(os.getenv("TELEGRAM_CHAT_ID"))


def send_telegram(message: str) -> None:
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    chat_id = os.environ["TELEGRAM_CHAT_ID"]
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = json.dumps(
        {
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "HTML",
            "disable_web_page_preview": False,
        }
    ).encode("utf-8")
    request = Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(request, timeout=30) as response:
        response.read()


def format_message(new_items: list[Item]) -> str:
    lines = [
        "PayPayフリマで新着を見つけました。",
        "",
        f"検索: {html.escape(SEARCH_URL)}",
        "",
    ]
    for item in new_items:
        lines.append(f"・{html.escape(item.title)}")
        lines.append(f"  {html.escape(item.price)}")
        lines.append(f"  {html.escape(item.url)}")
    return "\n".join(lines)


def main() -> int:
    _, current_items = fetch_page_text(SEARCH_URL)
    previous_state = load_state(STATE_FILE)
    previous_keys = set(previous_state.get("seen_keys", []))

    if not previous_state.get("initialized", False):
        save_state(STATE_FILE, current_items)
        print(f"Seeded state with {len(current_items)} items. No notification sent.")
        return 0

    new_items = [item for item in current_items if item.key not in previous_keys]
    save_state(STATE_FILE, current_items)

    if not new_items:
        print(f"No new items. Seen {len(current_items)} items.")
        return 0

    message = format_message(new_items)
    if telegram_enabled():
        send_telegram(message)
        print(f"Sent Telegram notification for {len(new_items)} new items.")
    else:
        print(message)
        print("Telegram secrets are missing, so the message was printed instead.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
