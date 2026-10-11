
import json
import time
from pathlib import Path
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd

from twisted.internet import reactor
from ctrader_open_api import Client, Protobuf, TcpProtocol, EndPoints
import ctrader_open_api.messages.OpenApiMessages_pb2 as OA
import ctrader_open_api.messages.OpenApiCommonMessages_pb2 as OACommon




import json
from pathlib import Path
from datetime import datetime, timedelta, timezone

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
OUTPUT_FILE = DATA_DIR / "btcusd_m1.csv"

SYMBOL_ID = 128
PRICE_SCALE = 100000.0
CHUNK_DAYS = 6

END_TIME = datetime.now(timezone.utc)
START_TIME = END_TIME - timedelta(days=365)

# Set True to start a fresh download.
OVERWRITE_OUTPUT = True

if OVERWRITE_OUTPUT and OUTPUT_FILE.exists():
    OUTPUT_FILE.unlink()

with open(CREDENTIALS_FILE, encoding="utf-8") as f:
    cfg = json.load(f)

ACCOUNT_ID = int(cfg["accountId"])


# ============================================================
# CLIENT AND TASKS
# ============================================================

client = Client(
    EndPoints.PROTOBUF_DEMO_HOST,
    EndPoints.PROTOBUF_PORT,
    TcpProtocol,
)

tasks = []
start = START_TIME

while start < END_TIME:
    end = min(start + timedelta(days=CHUNK_DAYS), END_TIME)
    tasks.append((
        int(start.timestamp() * 1000),
        int(end.timestamp() * 1000),
    ))
    start = end

task_index = 0


# ============================================================
# ERROR HANDLING
# ============================================================

def stop_with_error(message):
    print(f"\nERROR: {message}")
    if reactor.running:
        reactor.stop()


def on_request_failed(failure):
    stop_with_error(str(failure))


# ============================================================
# REQUEST CANDLES
# ============================================================

def request_next_window():
    global task_index

    if task_index >= len(tasks):
        print("\nDownload completed.")
        print(f"Output: {OUTPUT_FILE}")

        if OUTPUT_FILE.exists():
            df = pd.read_csv(OUTPUT_FILE)
            if not df.empty:
                df["timestamp"] = pd.to_datetime(
                    df["timestamp"], utc=True
                )
                df = df.drop_duplicates("timestamp")
                df = df.sort_values("timestamp")
                df.to_csv(OUTPUT_FILE, index=False)

                print(f"Total candles: {len(df):,}")
                print(f"First candle: {df['timestamp'].min()}")
                print(f"Last candle:  {df['timestamp'].max()}")

        if reactor.running:
            reactor.stop()
        return

    start_ms, end_ms = tasks[task_index]

    print(
        f"\n[{task_index + 1}/{len(tasks)}] "
        f"{datetime.fromtimestamp(start_ms / 1000, timezone.utc)} "
        f"to {datetime.fromtimestamp(end_ms / 1000, timezone.utc)}"
    )

    request_candles(start_ms, end_ms)


def request_candles(start_ms, end_ms):
    req = OA.ProtoOAGetTrendbarsReq()
    req.ctidTraderAccountId = ACCOUNT_ID
    req.symbolId = SYMBOL_ID

    # Obtain the M1 enum value from this installed protobuf version.
    period_field = req.DESCRIPTOR.fields_by_name["period"]
    req.period = (
        period_field.enum_type.values_by_name["M1"].number
    )

    req.fromTimestamp = int(start_ms)
    req.toTimestamp = int(end_ms)

    client.send(req).addCallbacks(
        lambda message: on_candles_received(
            message, start_ms, end_ms
        ),
        on_request_failed,
    )


def on_candles_received(message, start_ms, end_ms):
    global task_index

    response = Protobuf.extract(message)

    if isinstance(response, OA.ProtoOAErrorRes):
        stop_with_error(f"cTrader API error: {response}")
        return

    if not isinstance(response, OA.ProtoOAGetTrendbarsRes):
        stop_with_error(
            f"Unexpected response: {type(response).__name__}"
        )
        return

    bars = list(response.trendbar)
    print(f"Received {len(bars):,} candles.")

    rows = []

    for bar in bars:
        # cTrader trendbar timestamps are UTC minutes since epoch.
        timestamp = pd.to_datetime(
            int(bar.utcTimestampInMinutes) * 60,
            unit="s",
            utc=True,
        )

        low = float(bar.low) / PRICE_SCALE
        open_price = (
            float(bar.low) + float(bar.deltaOpen)
        ) / PRICE_SCALE
        high = (
            float(bar.low) + float(bar.deltaHigh)
        ) / PRICE_SCALE
        close = (
            float(bar.low) + float(bar.deltaClose)
        ) / PRICE_SCALE

        row = {
            "timestamp": timestamp,
            "open": open_price,
            "high": high,
            "low": low,
            "close": close,
        }

        if hasattr(bar, "volume"):
            row["volume"] = int(bar.volume)

        rows.append(row)

    if rows:
        df = pd.DataFrame(rows)
        df = df.drop_duplicates("timestamp")
        df = df.sort_values("timestamp")

        start_dt = pd.to_datetime(start_ms, unit="ms", utc=True)
        end_dt = pd.to_datetime(end_ms, unit="ms", utc=True)

        df = df[
            (df["timestamp"] >= start_dt)
            & (df["timestamp"] <= end_dt)
        ]

        if not df.empty:
            df.to_csv(
                OUTPUT_FILE,
                mode="a",
                header=not OUTPUT_FILE.exists(),
                index=False,
            )
            print(
                f"Saved {len(df):,} candles; "
                f"from {df['timestamp'].min()} "
                f"to {df['timestamp'].max()}"
            )
    else:
        print("No candles returned for this window.")

    # Trendbar responses in this package do not expose hasMore.
    # Continue with the next requested window.
    task_index += 1
    reactor.callLater(0.25, request_next_window)


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
        stop_with_error(
            f"Application authentication failed: {response}"
        )
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
        stop_with_error(
            f"Account authentication failed: {response}"
        )
        return

    print("Account authenticated.")
    print(f"Symbol ID: {SYMBOL_ID}")
    print(f"Start UTC: {START_TIME}")
    print(f"End UTC:   {END_TIME}")
    print(f"Windows:   {len(tasks)}")

    request_next_window()


def on_disconnected(_client, reason):
    print("Disconnected:", reason)


client.setConnectedCallback(on_connected)
client.setDisconnectedCallback(on_disconnected)


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    print("Starting BTCUSD M1 download...")
    client.startService()
    reactor.run()
