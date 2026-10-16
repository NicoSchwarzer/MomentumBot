
using cAlgo.API;
using cAlgo.API.Internals;
using System;

namespace cAlgo.Robots
{
    public partial class MomentumBot : Robot
    {
        private const string BotLabel = "BTC_Momentum_1m_7m";


        private double volumeInUnits;

        protected override void OnStart()
        {
            volumeInUnits =
                Symbol.QuantityToVolumeInUnits(VolumeInLots);

            volumeInUnits = Symbol.NormalizeVolumeInUnits(
                volumeInUnits, RoundingMode.Down);

            Print("Started on {0}", SymbolName);
            Print("Volume units: {0}", volumeInUnits);
        }

        protected override void OnBarClosed()
        {
            int requiredBars = Math.Max(
                LowerMomentumMinutes, HigherMomentumMinutes);

            if (Bars.Count <= requiredBars)
                return;

            double pNow = Bars.ClosePrices.Last(0);
            double pShort =
                Bars.ClosePrices.Last(LowerMomentumMinutes);
            double pLong =
                Bars.ClosePrices.Last(HigherMomentumMinutes);

            if (pShort <= 0 || pLong <= 0)
                return;

            double momentumShort = pNow / pShort - 1.0;
            double momentumLong = pNow / pLong - 1.0;

            Print("Short momentum: {0:P5}, Long momentum: {1:P5}",
                momentumShort, momentumLong);

            TradeType target;

            if (momentumShort > 0 && momentumLong > 0)
                target = TradeType.Buy;
            else if (momentumShort < 0 && momentumLong < 0)
                target = TradeType.Sell;
            else
                return;

            var positions = Positions.FindAll(BotLabel, SymbolName);

            foreach (var existing in positions)
            {
                if (existing.TradeType == target)
                    return;
            }

            TradeResult result = ExecuteMarketOrder(
                target,
                SymbolName,
                volumeInUnits,
                BotLabel,
                StopLossPips,
                TakeProfitPips);

            if (!result.IsSuccessful)
            {
                Print("Order failed: {0}", result.Error);
                return;
            }

            Position position = result.Position;

            Print("Opened {0}", target);
            Print("Entry: {0}", position.EntryPrice);
            Print("SL: {0}", position.StopLoss);
            Print("TP: {0}", position.TakeProfit);
            Print("Pip size: {0}", Symbol.PipSize);
            Print("Tick size: {0}", Symbol.TickSize);
        }
    }
}
