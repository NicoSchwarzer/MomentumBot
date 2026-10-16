# BTC/USD Double Momentum Trading Bot

A quantitative trading project exploring short-term momentum in the BTC/USD market using Python, C#, and cTrader.

The repository combines historical market-data retrieval, exploratory time-series analysis, and automated trading implementations. The core strategy uses momentum measured over different time horizons to identify potential short-term trading opportunities.

> **Disclaimer:** This project is intended for educational and research purposes. It is experimental software, not financial advice. Backtested or historical performance does not guarantee future results. Automated trading can result in substantial financial losses.

## Table of Contents

- [Overview](#overview)
- [Trading Strategy](#trading-strategy)
- [Repository Structure](#repository-structure)
- [Getting Started](#getting-started)
- [Historical Data Retrieval](#historical-data-retrieval)
- [Exploratory Analysis](#exploratory-analysis)
- [Running the Trading Bot](#running-the-trading-bot)
- [Risk Management and Limitations](#risk-management-and-limitations)
- [Future Improvements](#future-improvements)

## Overview

The project investigates whether combining momentum signals from different time horizons can provide useful trading signals for BTC/USD.

The main components are:

- **Data acquisition:** Retrieve historical market data through the cTrader Open API.
- **Quantitative analysis:** Explore price dynamics, autocorrelation, and momentum signals using Python and Jupyter notebooks.
- **Automated execution:** Implement a rule-based momentum strategy as a cTrader cBot in Python and C#.
- **Strategy evaluation:** Provide a foundation for backtesting, parameter selection, and further development of quantitative trading strategies.

## Trading Strategy

### Double Momentum

The strategy combines short-term and longer-term momentum to identify directional market movements.

For a closing price \(P_t\), define the relative momentum over a lookback period of \(k\) minutes as

\[
M_t^{(k)} = \frac{P_t}{P_{t-k}} - 1.
\]

The current Python implementation uses two lookback periods:

- Short-term momentum: 1 minute
- Longer-term momentum: 7 minutes

### Trading Rules

| Short-term momentum | Longer-term momentum | Signal |
|---|---|---|
| Positive | Positive | Buy / long |
| Negative | Negative | Sell / short |
| Mixed or zero | Any other value | No new signal |

The bot evaluates the signal using closed candles. When both momentum signals agree, it determines the desired trade direction. When the signals disagree or either is zero, the bot does not generate a new directional signal.

The intended principle is straightforward: enter in the direction of the market when price movements over both time horizons agree.

**Important:** The exact order and position-management behavior depends on the implementation. Review the relevant source file before assuming that the Python and C# versions behave identically.

## Repository Structure

```text
MomentumBot/
├── Data_Retrieval.py
├── Get_Account_ID.py
├── DoubleMomentumAnalysis.ipynb
├── cTraderExperiments.ipynb
├── MomentumBot.py
├── MomentumBotC.cs
├── config.json
└── README.md
```

### Main Files

| File | Description |
|---|---|
| `Data_Retrieval.py` | Retrieves historical BTC/USD candle data using the cTrader Open API. |
| `Get_Account_ID.py` | Contains functionality related to retrieving account or market data; check the current implementation before running it. |
| `DoubleMomentumAnalysis.ipynb` | Notebook for exploratory time-series analysis and momentum calculations. |
| `cTraderExperiments.ipynb` | Notebook for experimenting with cTrader-related functionality. |
| `MomentumBot.py` | Python implementation of the double-momentum cTrader trading bot. |
| `MomentumBotC.cs` | C# implementation of the trading bot. |
| `config.json` | Configuration file; inspect its contents before use and never store secrets in a public repository. |

## Getting Started

### Prerequisites

You will need:

- Python installed locally for the research and data-retrieval scripts.
- A Python environment compatible with the dependencies used by the project.
- A cTrader account and access to the cTrader Open API for data retrieval.
- cTrader with the appropriate cBot development environment for automated execution.
- Git to clone the repository.

### 1. Clone the Repository

```bash
git clone https://github.com/NicoSchwarzer/MomentumBot.git
cd MomentumBot
```

### 2. Create a Python Environment

Using Conda:

```bash
conda create -n momentum-bot python=3.11
conda activate momentum-bot
```

Install the core analysis and API dependencies:

```bash
python -m pip install pandas numpy matplotlib seaborn statsmodels ctrader-open-api Twisted jupyter
```

Depending on your Python and cTrader API versions, additional dependencies or compatibility adjustments may be necessary.

## Historical Data Retrieval

The project uses the cTrader Open API to retrieve historical market data.

Before running any data-retrieval script:

1. Review the script to identify the required API credentials and account configuration.
2. Configure the credentials locally using the format expected by the script.
3. Verify the requested symbol and date range.
4. Confirm that the API application and account are authorized.

Run the candle-data retrieval script:

```bash
python Data_Retrieval.py
```

The script is intended to retrieve historical BTC/USD one-minute candles. Check the source code for the current output path, symbol configuration, and date range.

Before using the resulting data for research, validate:

- Timestamp format and timezone.
- Missing candles and duplicate observations.
- OHLC price consistency.
- Data coverage and the presence of stale or incomplete observations.

### API Credentials

Never commit API client secrets, access tokens, passwords, or other authentication material to GitHub.

If a script requires credentials, keep them in a local configuration file and exclude that file from version control. If credentials have already been exposed, revoke or rotate them.

## Exploratory Analysis

The repository includes Jupyter notebooks for investigating market data and momentum behavior.

Start Jupyter with:

```bash
jupyter notebook
```

Open `DoubleMomentumAnalysis.ipynb` and execute its cells in order.

The analysis can be used to investigate:

- Price changes and their statistical properties.
- Autocorrelation and short-term market dynamics.
- Momentum over different lookback periods.
- The relationship between momentum signals and subsequent price movements.
- The sensitivity of results to parameter choices.

A positive historical relationship between a signal and price movements is not sufficient evidence of a profitable trading strategy. Evaluation should account for transaction costs, execution constraints, and out-of-sample performance.

## Running the Trading Bot

The repository contains both Python and C# implementations intended for the cTrader environment.

### Python

1. Open `MomentumBot.py` in the appropriate cTrader Python cBot workflow.
2. Review the configured symbol, momentum lookback periods, order volume, and protective orders.
3. Build or launch the bot in cTrader.
4. Attach it to a BTC/USD one-minute chart.
5. Test it in a demo environment before considering live execution.

The strategy's lookback periods are expressed in candles. Using a one-minute chart is therefore important if the intention is to calculate one-minute and seven-minute momentum.

### C#

Open `MomentumBotC.cs` in the appropriate cTrader Automate development environment.

Before running the C# version, verify its parameters and compare its signal generation, order execution, and position management with the Python implementation.

For official documentation, see the [cTrader cBots documentation](https://help.ctrader.com/cbots/).

## Risk Management and Limitations

This project is experimental. Several practical issues should be addressed before using the strategy with real capital.

### Trading Costs

Profitability may be materially affected by:

- Bid-ask spreads.
- Broker commissions and overnight financing, where applicable.
- Slippage and execution latency.
- Rejected orders and minimum order-distance restrictions.

A strategy that appears profitable before costs may be unprofitable after realistic execution costs.

### Stop Loss and Take Profit

Verify the configured stop-loss and take-profit distances against the broker's BTC/USD contract specifications. cTrader order parameters may be denominated in pips, and pip size varies by instrument.

Very tight protective orders may be rejected, triggered by ordinary market noise, or overwhelmed by transaction costs.

### Position Management

Confirm how the bot handles existing positions, opposing signals, failed orders, and repeated signals. Do not assume that a new signal automatically closes an existing position unless the implementation explicitly does so.

### Backtesting and Validation

A robust evaluation should include:

- Chronological training, validation, and test periods.
- Strict prevention
