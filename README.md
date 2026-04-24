# PayPay Flea Market Monitor

This monitors:

`https://paypayfleamarket.yahoo.co.jp/search/jbl%20tour%20pro2?minPrice=10000&maxPrice=15000&conditions=NEW%2CUSED10`

## Local run

```powershell
pip install -r part2/requirements.txt
python -m playwright install chromium
python part2/paypay_monitor.py
```

## Telegram setup

Set these environment variables or GitHub repository secrets:

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`

## GitHub Actions

The workflow runs every 10 minutes, stores the last seen items in `part2/state/paypay_tour_pro2.json`, and pushes the updated state back to the repo.

