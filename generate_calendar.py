import json
import os
import urllib.parse
import urllib.request
import urllib.error
from datetime import date, timedelta


# ============================================================
# TICKERS
# To add another stock later, add one entry here.
# ============================================================

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


# ============================================================
# GET EARNINGS FOR US STOCKS
# ============================================================

for ticker, info in TICKERS.items():

    # NVO is handled separately below
    if ticker == "NVO":
        continue

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


# ============================================================
# GET NVO FROM THE BROAD FINNHUB EARNINGS CALENDAR
# Direct query for NOVO B.CO returns HTTP 403, so we retrieve
# the broad calendar and filter for NOVO B.CO.
# ============================================================

nvo_params = urllib.parse.urlencode({
    "from": today.isoformat(),
    "to": end_date.isoformat(),
    "token": API_KEY,
})

nvo_url = "https://finnhub.io/api/v1/calendar/earnings?" + nvo_params

try:
    with urllib.request.urlopen(nvo_url) as response:
        nvo_data = json.load(response)

    all_events = nvo_data.get("earningsCalendar", [])

    nvo_events = [
        event
        for event in all_events
        if event.get("symbol") == "NOVO B.CO"
    ]

    print(f"NVO: {len(nvo_events)} events found via broad calendar")

    for event in nvo_events:
        event["calendar_ticker"] = "NVO"
        events.append(event)

except urllib.error.HTTPError as e:
    print(f"NVO broad calendar: Finnhub HTTP error {e.code}")
    print(f"NVO broad calendar: {e.read().decode()}")

except Exception as e:
    print(f"NVO broad calendar: unexpected error: {e}")


print(f"Total target events: {len(events)}")


# ============================================================
# ICS TEXT ESCAPING
# ============================================================

def escape(text):
    return (
        str(text)
        .replace("\\", "\\\\")
        .replace(",", "\\,")
        .replace(";", "\\;")
        .replace("\n", "\\n")
    )


# ============================================================
# BUILD ICS CALENDAR
# ============================================================

ics = [
    "BEGIN:VCALENDAR",
    "VERSION:2.0",
    "PRODID:-//Personal Earnings Calendar//EN",
    "CALSCALE:GREGORIAN",
    "X-WR-CALNAME:Stock Earnings",
]


for event in events:

    ticker = event.get("calendar_ticker")

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


# ============================================================
# WRITE earnings.ics
# ============================================================

ics.append("END:VCALENDAR")

with open("earnings.ics", "w", encoding="utf-8") as f:
    f.write("\r\n".join(ics) + "\r\n")

print("Calendar generated successfully.")
