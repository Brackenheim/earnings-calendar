import json
import os
import urllib.parse
import urllib.request
import urllib.error
from datetime import date, timedelta

TICKERS = {
    "PLTR": {
        "name": "Palantir Technologies",
        "finnhub_symbol": "PLTR",
    },
    "CHWY": {
        "name": "Chewy",
        "finnhub_symbol": "CHWY",
    },
    "RGTI": {
        "name": "Rigetti Computing",
        "finnhub_symbol": "RGTI",
    },
    "CCL": {
        "name": "Carnival Corporation",
        "finnhub_symbol": "CCL",
    },
    "APO": {
        "name": "Apollo Global Management",
        "finnhub_symbol": "APO",
    },
    "NVO": {
        "name": "Novo Nordisk",
        "finnhub_symbol": "NOVO B.CO",
    },
}

API_KEY = os.environ["FINNHUB_API_KEY"]

today = date.today()
end_date = today + timedelta(days=365)

events = []

# Get earnings separately for each ticker
for ticker, info in TICKERS.items():
    finnhub_symbol = info["finnhub_symbol"]

    params = urllib.parse.urlencode({
        "from": today.isoformat(),
        "to": end_date.isoformat(),
        "symbol": finnhub_symbol,
        "token": API_KEY,
    })

    url = "https://finnhub.io/api/v1/calendar/earnings?" + params

    try:
        with urllib.request.urlopen(url) as response:
            data = json.load(response)

        ticker_events = data.get("earningsCalendar", [])

        if ticker == "NVO":
            print("NVO Finnhub response:", json.dumps(data, indent=2))

        print(f"{ticker}: {len(ticker_events)} events found")

        for event in ticker_events:
            if event.get("symbol") == finnhub_symbol:
                event["calendar_ticker"] = ticker
                events.append(event)

except urllib.error.HTTPError as e:
    print(f"{ticker}: Finnhub HTTP error {e.code}")
    print(f"{ticker}: {e.read().decode()}")

except Exception as e:
    print(f"{ticker}: unexpected error: {e}")

print(f"Total target events: {len(events)}")


def escape(text):
    return (
        str(text)
        .replace("\\", "\\\\")
        .replace(",", "\\,")
        .replace(";", "\\;")
        .replace("\n", "\\n")
    )


ics = [
    "BEGIN:VCALENDAR",
    "VERSION:2.0",
    "PRODID:-//Personal Earnings Calendar//EN",
    "CALSCALE:GREGORIAN",
    "X-WR-CALNAME:Stock Earnings",
]


for event in events:
    ticker = event.get("calendar_ticker", event.get("symbol"))

    if ticker not in TICKERS:
        continue

    earnings_date = event.get("date")

    if not earnings_date:
        continue

    company = TICKERS[ticker]["name"]
    quarter = event.get("quarter", "")
    year = event.get("year", "")
    hour = event.get("hour", "")

    timing = {
        "bmo": "Before market open",
        "amc": "After market close",
        "dmh": "During market hours",
    }.get(hour, "Time not specified")

    uid = f"{ticker}-{year}-Q{quarter}@personal-earnings-calendar"

    summary = f"{ticker} Q{quarter} {year} Earnings"

    description = (
        f"{company}\n"
        f"Ticker: {ticker}\n"
        f"Timing: {timing}\n"
        f"Source: Finnhub"
    )

    ics.extend([
        "BEGIN:VEVENT",
        f"UID:{uid}",
        f"DTSTART;VALUE=DATE:{earnings_date.replace('-', '')}",
        f"DTEND;VALUE=DATE:{(date.fromisoformat(earnings_date) + timedelta(days=1)).strftime('%Y%m%d')}",
        f"SUMMARY:{escape(summary)}",
        f"DESCRIPTION:{escape(description)}",

        "BEGIN:VALARM",
        "TRIGGER:-P1D",
        "ACTION:DISPLAY",
        f"DESCRIPTION:{escape(summary)} tomorrow",
        "END:VALARM",

        "BEGIN:VALARM",
        "TRIGGER:-PT1H",
        "ACTION:DISPLAY",
        f"DESCRIPTION:{escape(summary)} in 1 hour",
        "END:VALARM",

        "END:VEVENT",
    ])


ics.append("END:VCALENDAR")

with open("earnings.ics", "w", encoding="utf-8") as f:
    f.write("\r\n".join(ics) + "\r\n")

print("Calendar generated successfully.")
