import json
import os
import urllib.parse
import urllib.request
import urllib.error
from datetime import date, timedelta


TICKERS = {
    "PLTR": {
        "name": "Palantir Technologies",
        "finnhub_symbols": ["PLTR"],
    },
    "CHWY": {
        "name": "Chewy",
        "finnhub_symbols": ["CHWY"],
    },
    "RGTI": {
        "name": "Rigetti Computing",
        "finnhub_symbols": ["RGTI"],
    },
    "CCL": {
        "name": "Carnival Corporation",
        "finnhub_symbols": ["CCL"],
    },
    "APO": {
        "name": "Apollo Global Management",
        "finnhub_symbols": ["APO"],
    },
    "BMNR": {
        "name": "Bitmine Immersion Technologies",
        "finnhub_symbols": ["BMNR"],
    },
    "INTU": {
        "name": "Intuit Inc",
        "finnhub_symbols": ["INTU"],
    },
    "NVO": {
        "name": "Novo Nordisk",
        "finnhub_symbols": ["NVO", "NOVO B.CO"],
    },
}


API_KEY = os.environ["FINNHUB_API_KEY"]

today = date.today()
end_date = today + timedelta(days=365)

events = []


# Get earnings separately for each ticker
for ticker, info in TICKERS.items():

    ticker_events_found = False

    for finnhub_symbol in info["finnhub_symbols"]:

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

            print(
                f"{ticker}: {finnhub_symbol}: "
                f"{len(ticker_events)} events found"
            )

            for event in ticker_events:
                event["calendar_ticker"] = ticker
                events.append(event)
                ticker_events_found = True

            # If this symbol worked, do not need to try another symbol
            if ticker_events_found:
                break

        except urllib.error.HTTPError as e:

            print(
                f"{ticker}: {finnhub_symbol}: "
                f"Finnhub HTTP error {e.code}"
            )

            try:
                error_message = e.read().decode()
                print(f"{ticker}: {error_message}")
            except Exception:
                pass

            # Try the next Finnhub symbol, if one exists
            continue

        except Exception as e:

            print(
                f"{ticker}: {finnhub_symbol}: "
                f"unexpected error: {e}"
            )

            # Try the next Finnhub symbol, if one exists
            continue

    if not ticker_events_found:
        print(f"{ticker}: NO earnings events found")


print(f"Total target events: {len(events)}")


def escape(text):
    """
    Escape text according to ICS formatting rules.
    """
    return (
        str(text)
        .replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\n", "\\n")
    )


ics = [
    "BEGIN:VCALENDAR",
    "VERSION:2.0",
    "PRODID:-//Personal Earnings Calendar//EN",
    "CALSCALE:GREGORIAN",
    "X-WR-CALNAME:Stock Earnings",
]


# Create calendar events
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

    uid = (
        f"{ticker}-{year}-Q{quarter}"
        "@personal-earnings-calendar"
    )

    summary = f"{ticker} Q{quarter} {year} Earnings"

    description = (
        f"{company}\n"
        f"Ticker: {ticker}\n"
        f"Timing: {timing}\n"
        f"Source: Finnhub"
    )

    end_earnings_date = (
        date.fromisoformat(earnings_date)
        + timedelta(days=1)
    )

    ics.extend([
        "BEGIN:VEVENT",
        f"UID:{uid}",
        f"DTSTART;VALUE=DATE:{earnings_date.replace('-', '')}",
        f"DTEND;VALUE=DATE:{end_earnings_date.strftime('%Y%m%d')}",
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
