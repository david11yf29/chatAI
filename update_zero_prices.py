import yfinance as yf
import json
from datetime import datetime
from zoneinfo import ZoneInfo


def format_market_close_time(trading_date) -> str:
    """Convert trading date to market close time in Taiwan Time.

    US stock market closes at 4:00 PM Eastern Time, which is 5:00 AM next day in Taiwan.

    Args:
        trading_date: The trading date from yfinance (pandas Timestamp or datetime)

    Returns:
        ISO 8601 formatted string like "2026-01-17T05:00:00+08:00"
    """
    from datetime import timedelta
    trade_date = trading_date.date() if hasattr(trading_date, 'date') else trading_date
    taiwan = ZoneInfo("Asia/Taipei")
    # Market closes at 4:00 PM Eastern Time = 5:00 AM next day Taiwan Time
    next_day = trade_date + timedelta(days=1)
    market_close = datetime(next_day.year, next_day.month, next_day.day, 5, 0, 0, tzinfo=taiwan)
    return market_close.isoformat()

# Read stockapp.json
with open("stockapp.json", "r") as f:
    data = json.load(f)

# Update stocks with price=0.0
for stock in data["stocks"]:
    if stock["price"] == 0.0:
        symbol = stock["symbol"]
        try:
            ticker = yf.Ticker(symbol)
            history = ticker.history(period="2d")
            if not history.empty:
                stock["price"] = round(float(history['Close'].iloc[-1]), 2)
                # Get the actual market close time in Eastern Time
                trading_date = history.index[-1]
                price_date = format_market_close_time(trading_date)
                stock["date"] = price_date

                # Calculate percentage change from previous day
                if len(history) >= 2:
                    current_close = float(history['Close'].iloc[-1])
                    previous_close = float(history['Close'].iloc[-2])
                    change_percent = ((current_close - previous_close) / previous_close) * 100
                    stock["changePercent"] = round(change_percent, 2)
                else:
                    stock["changePercent"] = None

                print(f"Updated {symbol}: ${stock['price']} (date: {price_date}, change: {stock.get('changePercent')}%)")
            else:
                print(f"No price data for {symbol}")
        except Exception as e:
            print(f"Error for {symbol}: {e}")

# Write back to stockapp.json
with open("stockapp.json", "w") as f:
    json.dump(data, f, indent=2)

print("\nDone! Check stockapp.json for updated prices.")
