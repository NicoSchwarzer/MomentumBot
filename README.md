# BTC/USD Double Momentum Trading Strategy

A Python-based research and trading project for exploring a double-momentum strategy on BTC/USD using cTrader. The project includes historical market-data retrieval through the cTrader Open API, exploratory time-series analysis in a Jupyter notebook, and a cTrader Python cBot that trades when short- and longer-term momentum agree.

> **Risk warning:** This project is experimental and is not financial advice. Automated trading can lose money. Test thoroughly with historical data and a demo account before considering live use. Stop-loss/take-profit distances, spread, commissions, slippage, contract specifications, and broker restrictions can materially affect results.

## Project structure

```text
.
├── Get_Account_ID.py
├── Data_Retrieval.py
├── DoubleMomentumAnalysis.ipynb
├── MomentumBot.py
├── credentials.json          # Create locally; do not commit
└── data/
    └── btcusd_m1.csv          # Created by Data_Retrieval.py
```

### Files

- **`Get_Account_ID.py`** — despite its filename, the uploaded version is a historical tick-data downloader. It requests BID and ASK ticks through the cTrader Open API, saves raw quote data, and attempts to aggregate quotes to a one-second dataset. It expects a local `credentials.json` file.
- **`Data_Retrieval.py`** — downloads approximately one year of BTC/USD one-minute candles and saves them to `data/btcusd_m1.csv`.
- **`DoubleMomentumAnalysis.ipynb`** — notebook for data checks, autoregressive/time-series analysis, momentum calculations, and comparisons across momentum lookback periods.
- **`MomentumBot.py`** — cTrader Python cBot implementing the double-momentum signal and submitting market orders with configured stop loss and take profit.

## Strategy

For closing price \(P_t\), define the \(k\)-minute relative momentum as

\[
M_t^{(k)} = \frac{P_t}{P_{t-k}} - 1.
\]

The current bot uses a **1-minute** and a **7-minute** lookback:

- **Buy / long:** both momentum values are positive.
- **Sell / short:** both momentum values are negative.
- **Mixed or zero signals:** do not open a new trade; an existing position is left unchanged.

The cBot evaluates the signal on a closed bar. Attach it to a **BTC/USD one-minute chart** so that the bar offsets correspond to minutes.

The uploaded bot currently configures:
- Position size: `0.01` lots (example setting; verify it is valid for your broker).
- Stop loss: `0.2` pips.
- Take profit: `0.2` pips.
- Order type: market orders.
- Position management: positions are identified by the bot label and symbol; an opposite position is closed before a new position is opened.

**Important:** cTrader expects stop-loss and take-profit distances in pips for the market-order call. A setting of `0.2` pips may be below the symbol's allowed minimum distance or smaller than the spread and trading costs. Verify BTC/USD pip size, volume units, minimum volume, stop-distance rules, and account currency with your broker. Do not assume that a 0.2-pip target means a $0.20 or $1.00 profit/loss.

## Requirements

The research and data-retrieval scripts use Python and several third-party packages, including:

- `pandas`
- `numpy`
- `matplotlib`
- `seaborn`
- `statsmodels`
- `ctrader-open-api`
- `Twisted`

Install the research/API dependencies in your chosen Python environment. For example:

```bash
python -m pip install pandas numpy matplotlib seaborn statsmodels ctrader-open-api
```

If Twisted is not installed automatically as a dependency:

```bash
python -m pip install Twisted
```

The cTrader cBot runs inside cTrader's Python/cAlgo environment and may have different runtime/API requirements from the standalone Open API scripts. Follow the requirements of your installed cTrader version.

## cTrader Open API credentials

The data-retrieval scripts read credentials from a local file named `credentials.json` in the project root. Create it locally with the fields expected by the scripts:

```json
{
  "clientId": "YOUR_CLIENT_ID",
  "clientSecret": "YOUR_CLIENT_SECRET",
  "accessToken": "YOUR_ACCESS_TOKEN",
  "accountId": "YOUR_ACCOUNT_ID"
}
```

Use valid credentials from your cTrader Open API application and account. The scripts shown here use the **cTrader demo endpoint**. Confirm the account and environment before running any request.

**Never commit `credentials.json`, access tokens, client secrets, or other authentication material to GitHub.** Add it to `.gitignore` before the first commit:

```gitignore
credentials.json
data/
__pycache__/
.ipynb_checkpoints/
.venv/
.env
```

If credentials have already been committed, removing the file in a later commit is not enough: revoke/rotate the exposed credentials and remove the secret from the repository history.

## Getting started

### 1. Clone the repository

```bash
git clone <YOUR_REPOSITORY_URL>
cd <YOUR_REPOSITORY_DIRECTORY>
```

### 2. Create and activate a Python environment

With Conda:

```bash
conda create -n btc-momentum python=3.11
conda activate btc-momentum
python -m pip install pandas numpy matplotlib seaborn statsmodels ctrader-open-api Twisted jupyter
```

Choose a Python version compatible with the installed cTrader Open API package and your environment.

### 3. Configure credentials

Create `credentials.json` in the repository root using the structure above. Ensure the file is ignored by Git.

### 4. Download one-minute candle data

Run:

```bash
python Data_Retrieval.py
```

The script requests approximately one year of BTC/USD M1 candles and writes:

```text
data/btcusd_m1.csv
```

The output includes a timestamp and OHLC columns (`open`, `high`, `low`, `close`); a volume column is included if it is available in the API response. Timestamps are written in UTC.

### 5. Run the research notebook

Start Jupyter:

```bash
jupyter notebook
```

Open `DoubleMomentumAnalysis.ipynb` and run the cells in order. The notebook contains data-quality checks, time-series/autoregressive analysis, momentum calculations, and comparisons of mean returns for combinations of lookback periods.

Make sure the expected data file exists before running the notebook. Research results are exploratory and do not by themselves establish that a strategy is profitable after costs or out of sample.

### 6. Run the cTrader bot

Open `MomentumBot.py` in the appropriate cTrader Python cBot workflow, build/launch it in a **demo environment first**, and attach it to a BTC/USD M1 chart. Verify the symbol name, volume, pip conventions, and order protections for your broker before enabling trading.

## Data notes

- Candle data is retrieved from cTrader's Open API using a symbol ID configured in the script (`SYMBOL_ID = 128` in the uploaded version).
- The candle downloader divides the requested period into windows and appends returned bars to a CSV, then removes duplicate timestamps and sorts the output.
- The tick downloader uses separate BID and ASK requests and resamples the data to a one-second grid. Forward-filling quotes can leave stale prices in the output; inspect quote age and data coverage before using the resulting series for analysis or execution.
- Validate timestamps, duplicates, missing intervals, price scaling, and the coverage of downloaded data before drawing conclusions.

## Limitations and next steps

- The current strategy is a simple rule-based signal; it does not include a demonstrated profitability guarantee.
- The current bot leaves a position unchanged when the momentum signals disagree.
- The configured stop loss and take profit are very tight and may be rejected or overwhelmed by spread and execution costs.
- Backtests should model spread, commission, slippage, order execution, and realistic position sizing.
- Separate parameter selection from out-of-sample evaluation to reduce overfitting.
- Add explicit risk controls, such as a maximum daily loss and a maximum number of trades, before considering live deployment.

## Disclaimer

Provided for educational and research purposes only. You are responsible for validating the code, complying with broker terms, protecting credentials, and assessing the risks of any trading activity.
