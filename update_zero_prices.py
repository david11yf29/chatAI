import yfinance as yf
import json
from datetime import datetime

# Read stockapp.json
with open("stockapp.json", "r") as f:
    data = json.load(f)

# Update stocks with price=0.0
for stock in data["stocks"]:
    if stock["price"] == 0.0:
        symbol = stock["symbol"]
        try:
            ticker = yf.Ticker(symbol)
            history = ticker.history(period="5d")
            if not history.empty:
                stock["price"] = round(float(history['Close'].iloc[-1]), 2)
                # Get the actual date of the closed price from yfinance
                price_date = history.index[-1].strftime("%Y-%m-%d")
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
