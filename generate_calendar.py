import csv
import io
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


FINNHUB_API_KEY = os.environ["FINNHUB_API_KEY"]
ALPHA_VANTAGE_API_KEY = os.environ["ALPHA_VANTAGE_API_KEY"]

today = date.today()
end_date = today + timedelta(days=365)

events = []


def get_finnhub_events(ticker, symbols):
    """
    Try each Finnhub symbol until one returns earnings events.
    Returns a list of events, or an empty list.
    """

    for finnhub_symbol in symbols:

        params = urllib.parse.urlencode({
            "from": today.isoformat(),
            "to": end_date.isoformat(),
            "symbol": finnhub_symbol,
            "token": FINNHUB_API_KEY,
        })

        url = (
            "https://finnhub.io/api/v1/calendar/earnings?"
            + params
        )

        try:
            with urllib.request.urlopen(url) as response:
                data = json.load(response)

            ticker_events = data.get("earningsCalendar", [])

            print(
                f"{ticker}: {finnhub_symbol}: "
                f"{len(ticker_events)} events found"
            )

            if ticker_events:
                for event in ticker_events:
                    event["calendar_ticker"] = ticker

                return ticker_events

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

        except Exception as e:

            print(
                f"{ticker}: {finnhub_symbol}: "
                f"unexpected error: {e}"
            )

    return []


def get_alpha_vantage_event(ticker):
    """
    Fallback to Alpha Vantage if Finnhub has no earnings events.

    Alpha Vantage's Earnings Calendar endpoint returns CSV data.
    We use the first upcoming report date for the requested ticker.
    """

    print(f"{ticker}: checking Alpha Vantage fallback...")

    params = urllib.parse.urlencode({
        "function": "EARNINGS_CALENDAR",
        "symbol": ticker,
        "horizon": "12month",
        "apikey": ALPHA_VANTAGE_API_KEY,
    })

    url = (
        "https://www.alphavantage.co/query?"
        + params
    )

    try:
        with urllib.request.urlopen(url) as response:
            raw_data = response.read().decode("utf-8")

        # Alpha Vantage can return an informational/error message
        # instead of CSV, so check that first.
        if (
            raw_data.startswith("{")
            or "Thank you for using Alpha Vantage" in raw_data
            or "Error Message" in raw_data
        ):
            print(f"{ticker}: Alpha Vantage returned:")
            print(raw_data[:500])
            return None

        reader = csv.DictReader(io.StringIO(raw_data))

        rows = list(reader)

        # Keep only rows with a valid future report date.
        valid_rows = []

        for row in rows:
            report_date = row.get("reportDate", "").strip()

            if not report_date:
                continue

            try:
                parsed_date = date.fromisoformat(report_date)
            except ValueError:
                continue

            if parsed_date >= today:
                valid_rows.append(row)

        if not valid_rows:
            print(f"{ticker}: Alpha Vantage: no future earnings found")
            return None

        # Sort chronologically and use the earliest upcoming event.
        valid_rows.sort(
            key=lambda row: row["reportDate"]
        )

        row = valid_rows[0]

        earnings_date = row["reportDate"]

        event = {
            "calendar_ticker": ticker,
            "symbol": ticker,
            "date": earnings_date,
            "quarter": "",
            "year": earnings_date[:4],
            "hour": "",
            "source": "Alpha Vantage fallback",
        }

        print(
            f"{ticker}: Alpha Vantage fallback found "
            f"{earnings_date}"
        )

        return event

    except urllib.error.HTTPError as e:

        print(
            f"{ticker}: Alpha Vantage HTTP error {e.code}"
        )

        try:
            print(e.read().decode())
        except Exception:
            pass

        return None

    except Exception as e:

        print(
            f"{ticker}: Alpha Vantage unexpected error: {e}"
        )

        return None


# ============================================================
# GET EARNINGS
# ============================================================

for ticker, info in TICKERS.items():

    ticker_events = get_finnhub_events(
        ticker,
        info["finnhub_symbols"],
    )

    if ticker_events:

        events.extend(ticker_events)

    else:

        print(
            f"{ticker}: no events from Finnhub. "
            f"Using fallback."
        )

        fallback_event = get_alpha_vantage_event(ticker)

        if fallback_event:
            events.append(fallback_event)


print(f"Total target events: {len(events)}")


# ============================================================
# ICS HELPERS
# ============================================================

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


# ============================================================
# CREATE CALENDAR EVENTS
# ============================================================

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

    if quarter:
        quarter_label = f"Q{quarter}"
    else:
        quarter_label = "Earnings"

    timing = {
        "bmo": "Before market open",
        "amc": "After market close",
        "dmh": "During market hours",
    }.get(hour, "Time not specified")

    uid = (
        f"{ticker}-{earnings_date}"
        "@personal-earnings-calendar"
    )

    if quarter and year:
        summary = (
            f"{ticker} Q{quarter} {year} Earnings"
        )
    else:
        summary = (
            f"{ticker} Earnings"
        )

    source = event.get(
        "source",
        "Finnhub"
    )

    description = (
        f"{company}\n"
        f"Ticker: {ticker}\n"
        f"Timing: {timing}\n"
        f"Source: {source}"
    )

    end_earnings_date = (
        date.fromisoformat(earnings_date)
        + timedelta(days=1)
    )

    ics.extend([
        "BEGIN:VEVENT",
        f"UID:{uid}",
        f"DTSTART;VALUE=DATE:{earnings_date.replace('-', '')}",
        (
            "DTEND;VALUE=DATE:"
            f"{end_earnings_date.strftime('%Y%m%d')}"
        ),
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


# ============================================================
# WRITE ICS FILE
# ============================================================

with open(
    "earnings.ics",
    "w",
    encoding="utf-8"
) as f:
    f.write(
        "\r\n".join(ics)
        + "\r\n"
    )


print("Calendar generated successfully.")
