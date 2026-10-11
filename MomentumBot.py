import clr

clr.AddReference("cAlgo.API")

from cAlgo.API import *

class MomentumBot:

    def on_start(self):
        # Strategy settings
        self.label = "BTC_Momentum_1m_7m"
        self.lower_momentum_minutes = 1
        self.higher_momentum_minutes = 7

        # Position size (example: 0.01 lots)
        self.volume_in_lots = 0.01
        self.volume = api.Symbol.QuantityToVolumeInUnits(
            self.volume_in_lots
        )
        self.volume = api.Symbol.NormalizeVolumeInUnits(
            self.volume, RoundingMode.Down
        )

        # Stop loss and take profit in pips
        self.stop_loss_pips = 0.2
        self.take_profit_pips = 0.2

        api.Print("Momentum bot started on " + api.SymbolName)
        api.Print("Volume in units: " + str(self.volume))

    def on_bar_closed(self):
        # Ensure enough candles are available
        if api.Bars.Count <= self.higher_momentum_minutes:
            return

        close = api.Bars.ClosePrices

        # Latest closed candle and historical prices
        p_now = close.Last(0)
        p_short = close.Last(self.lower_momentum_minutes)
        p_long = close.Last(self.higher_momentum_minutes)

        if p_short <= 0 or p_long <= 0:
            return

        # Calculate relative momentum
        momentum_short = p_now / p_short - 1
        momentum_long = p_now / p_long - 1

        api.Print(
            "1m momentum: {:.5%}, 7m momentum: {:.5%}".format(
                momentum_short, momentum_long
            )
        )

        # Both momentums must agree
        if momentum_short > 0 and momentum_long > 0:
            target = TradeType.Buy
        elif momentum_short < 0 and momentum_long < 0:
            target = TradeType.Sell
        else:
            # Mixed signals: keep the existing position
            return

        # Find positions opened by this bot on this symbol
        positions = api.Positions.FindAll(
            self.label, api.SymbolName
        )

        # If already holding the desired direction, do nothing
        for position in positions:
            if position.TradeType == target:
                return

        # Close positions in the opposite direction
        for position in positions:
            result = api.ClosePosition(position)

            if not result.IsSuccessful:
                api.Print(
                    "Could not close existing position. "
                    "Skipping new order."
                )
                return

        # Open a market order with SL and TP
        result = api.ExecuteMarketOrder(
            target,
            api.SymbolName,
            self.volume,
            self.label,
            self.stop_loss_pips,
            self.take_profit_pips
        )

        if result.IsSuccessful:
            api.Print(
                "Opened {} position. SL={} pips, TP={} pips".format(
                    target,
                    self.stop_loss_pips,
                    self.take_profit_pips
                )
            )
        else:
            api.Print("Order failed: " + str(result.Error))