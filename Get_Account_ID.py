
import json
import time
from pathlib import Path
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd

from twisted.internet import reactor
from ctrader_open_api import Client, Protobuf, TcpProtocol, EndPoints
import ctrader_open_api.messages.OpenApiMessages_pb2 as OA


# ============================================================
# CONFIGURATION
# ============================================================

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

CREDENTIALS_FILE = BASE_DIR / "credentials.json"

SYMBOL_ID = 128  # BTCUSD, based on your successful symbol lookup

# One year ending now (UTC)
END_TIME = datetime.now(timezone.utc)
START_TIME = END_TIME - timedelta(days=365)

# cTrader permits at most one week per historical tick request.
CHUNK_DAYS = 7

# Price scaling used by cTrader Open API.
PRICE_SCALE = 100000.0

# Set True to keep existing raw files and skip downloading.
# For an interrupted download, the code currently saves completed
# requests but does not maintain a full request-level resume index.
KEEP_EXISTING_RAW = True


# ============================================================
# LOAD CREDENTIALS
# ============================================================

with open(CREDENTIALS_FILE, encoding="utf-8") as f:
    cfg = json.load(f)

ACCOUNT_ID = int(cfg["accountId"])

client = Client(
    EndPoints.PROTOBUF_DEMO_HOST,
    EndPoints.PROTOBUF_PORT,
    TcpProtocol,
)

# Store rows as (timestamp_ms, price)
raw_ticks = {"BID": [], "ASK": []}

# A queue of (quote_type, window_start_ms, window_end_ms)
tasks = []

for start in pd.date_range(
    start=START_TIME,
    end=END_TIME,
    freq=f"{CHUNK_DAYS}D",
    inclusive="left",
):
    end = min(
        start.to_pydatetime() + timedelta(days=CHUNK_DAYS),
        END_TIME,
    )
    tasks.append(
        (
            int(start.timestamp() * 1000),
            int(end.timestamp() * 1000),
        )
    )

# Each time window is requested for BID and ASK.
tasks = [
    (quote, start_ms, end_ms)
    for start_ms, end_ms in tasks
    for quote in ("BID", "ASK")
]

task_index = 0
current_task = None
page_count = 0
request_count = 0
last_page_signature = None


# ============================================================
# HELPERS
# ============================================================

def stop_with_error(message):
    print(f"\nERROR: {message}")
    if reactor.running:
        reactor.stop()


def save_raw_ticks(quote):
    """Save the downloaded ticks for one quote type."""
    rows = raw_ticks[quote]
    if not rows:
        return

    df = pd.DataFrame(rows, columns=["timestamp_ms", quote.lower()])
    df = df.drop_duplicates(subset="timestamp_ms")
    df = df.sort_values("timestamp_ms")

    out = DATA_DIR / f"btcusd_{quote.lower()}_raw.csv"
    df.to_csv(out, index=False)
    print(f"Saved {len(df):,} {quote} ticks to {out}")


def request_next_task():
    """Start the next quote/window after the preceding one finishes."""
    global task_index, current_task, page_count, last_page_signature

    if task_index >= len(tasks):
        print("\nAll historical tick requests completed.")
        try:
            save_raw_ticks("BID")
            save_raw_ticks("ASK")
            build_one_second_data()
        except Exception as exc:
            print("Error while saving/aggregating:", repr(exc))
        finally:
            if reactor.running:
                reactor.stop()
        return

    quote, start_ms, end_ms = tasks[task_index]
    current_task = (quote, start_ms, end_ms)
    page_count = 0
    last_page_signature = None

    print(
        f"\n[{task_index + 1}/{len(tasks)}] "
        f"{quote}: "
        f"{datetime.fromtimestamp(start_ms / 1000, timezone.utc)} "
        f"to {datetime.fromtimestamp(end_ms / 1000, timezone.utc)}"
    )

    send_tick_request(start_ms, end_ms)


def send_tick_request(from_ms, to_ms):
    global request_count

    quote, original_start, original_end = current_task

    req = OA.ProtoOAGetTickDataReq()
    req.ctidTraderAccountId = ACCOUNT_ID
    req.symbolId = SYMBOL_ID
    req.type = (
        OA.ProtoOAQuoteType.BID
        if quote == "BID"
        else OA.ProtoOAQuoteType.ASK
    )
    req.fromTimestamp = int(from_ms)
    req.toTimestamp = int(to_ms)

    request_count += 1
    d = client.send(req)
    d.addCallbacks(on_ticks_received, on_request_failed)


def on_request_failed(failure):
    stop_with_error(str(failure))


def on_ticks_received(message):
    global page_count, last_page_signature, task_index

    response = Protobuf.extract(message)

    if isinstance(response, OA.ProtoOAErrorRes):
        stop_with_error(f"cTrader returned an API error: {response}")
        return

    if not isinstance(response, OA.ProtoOAGetTickDataRes):
        stop_with_error(
            f"Unexpected response type: {type(response).__name__}"
        )
        return

    quote, original_start, original_end = current_task
    ticks = list(response.tickData)

    if not ticks:
        print("No ticks returned for this page.")
        task_index += 1
        request_next_task()
        return

    # cTrader encodes the first timestamp as an absolute Unix
    # timestamp in milliseconds; subsequent timestamps are relative
    # differences. Decode and then sort chronologically.
    timestamp_ms = int(ticks[0].timestamp)
    page_rows = []

    for i, tick in enumerate(ticks):
        if i > 0:
            timestamp_ms += int(tick.timestamp)

        price = float(tick.tick) / PRICE_SCALE
        page_rows.append((timestamp_ms, price))

    # Remove out-of-window values and duplicate timestamps.
    page_rows = [
        (ts, price)
        for ts, price in page_rows
        if original_start <= ts <= original_end
    ]

    if page_rows:
        signature = (
            min(ts for ts, _ in page_rows),
            max(ts for ts, _ in page_rows),
            len(page_rows),
        )

        if signature == last_page_signature:
            stop_with_error(
                "The API returned the same page twice. "
                "Stopping to avoid an infinite pagination loop."
            )
            return

        last_page_signature = signature
        raw_ticks[quote].extend(page_rows)

    page_count += 1
    print(
        f"  Page {page_count}: {len(page_rows):,} ticks; "
        f"hasMore={response.hasMore}"
    )

    if response.hasMore:
        # Historical tick data is returned newest-first. Continue
        # from just before the oldest tick in this response.
        oldest_ms = min(ts for ts, _ in page_rows) if page_rows else None

        if oldest_ms is None or oldest_ms <= original_start:
            stop_with_error(
                "More data exists, but pagination cannot move further "
                "back within this time window."
            )
            return

        # Keep the request inside the original window.
        send_tick_request(original_start, oldest_ms - 1)
        return

    # Completed this quote/window. Periodically persist the raw data.
    if task_index % 4 == 3:
        save_raw_ticks("BID")
        save_raw_ticks("ASK")

    task_index += 1
    request_next_task()


def build_one_second_data():
    """Merge bid/ask ticks and create a one-second quote dataset."""
    bid_file = DATA_DIR / "btcusd_bid_raw.csv"
    ask_file = DATA_DIR / "btcusd_ask_raw.csv"

    if not bid_file.exists() or not ask_file.exists():
        print("Cannot aggregate: raw bid/ask files are missing.")
        return

    bid = pd.read_csv(bid_file)
    ask = pd.read_csv(ask_file)

    if bid.empty or ask.empty:
        print("Cannot aggregate: one or both raw datasets are empty.")
        return

    bid["timestamp"] = pd.to_datetime(
        bid["timestamp_ms"], unit="ms", utc=True
    )
    ask["timestamp"] = pd.to_datetime(
        ask["timestamp_ms"], unit="ms", utc=True
    )

    bid = (
        bid.drop_duplicates("timestamp")
        .sort_values("timestamp")
        .set_index("timestamp")[["bid"]]
    )
    ask = (
        ask.drop_duplicates("timestamp")
        .sort_values("timestamp")
        .set_index("timestamp")[["ask"]]
    )

    # Align each quote to the one-second grid by taking the last
    # observed quote within each second.
    bid_1s = bid.resample("1s").last()
    ask_1s = ask.resample("1s").last()

    # Forward-fill within each series to carry forward the last
    # observed quote. A later refinement can add quote-age limits.
    quotes = bid_1s.join(ask_1s, how="outer").sort_index()
    quotes = quotes.ffill()

    quotes["mid"] = (quotes["bid"] + quotes["ask"]) / 2
    quotes["spread"] = quotes["ask"] - quotes["bid"]

    # Keep only rows where both sides have been observed at least once.
    quotes = quotes.dropna(subset=["bid", "ask"])

    # The first valid row may have an old quote carried forward.
    # We'll examine quote ages before using this dataset for trading.
    output_file = DATA_DIR / "btcusd_1s.csv"
    quotes.to_csv(output_file, index_label="timestamp")

    print("\nAggregation completed.")
    print(f"Rows: {len(quotes):,}")
    print(f"Start: {quotes.index.min()}")
    print(f"End:   {quotes.index.max()}")
    print(f"Saved: {output_file}")


# ============================================================
# AUTHENTICATION
# ============================================================

def on_connected(_client):
    print("Connected to cTrader.")

    req = OA.ProtoOAApplicationAuthReq()
    req.clientId = cfg["clientId"]
    req.clientSecret = cfg["clientSecret"]

    client.send(req).addCallbacks(
        on_application_authenticated,
        on_request_failed,
    )


def on_application_authenticated(message):
    response = Protobuf.extract(message)

    if isinstance(response, OA.ProtoOAErrorRes):
        stop_with_error(f"Application authentication failed: {response}")
        return

    print("Application authenticated.")

    req = OA.ProtoOAAccountAuthReq()
    req.ctidTraderAccountId = ACCOUNT_ID
    req.accessToken = cfg["accessToken"]

    client.send(req).addCallbacks(
        on_account_authenticated,
        on_request_failed,
    )


def on_account_authenticated(message):
    response = Protobuf.extract(message)

    if isinstance(response, OA.ProtoOAErrorRes):
        stop_with_error(f"Account authentication failed: {response}")
        return

    print("Account authenticated.")
    print(f"Downloading approximately one year for symbol ID {SYMBOL_ID}.")
    request_next_task()


def on_disconnected(_client, reason):
    print("Disconnected:", reason)


client.setConnectedCallback(on_connected)
client.setDisconnectedCallback(on_disconnected)

if __name__ == "__main__":
    print(f"UTC start: {START_TIME}")
    print(f"UTC end:   {END_TIME}")
    print(f"Time windows: {len(tasks) // 2}")
    print("Starting download...")
    client.startService()
    reactor.run()
