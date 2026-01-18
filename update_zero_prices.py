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
            history = ticker.history(period="1d")
            if not history.empty:
                stock["price"] = round(float(history['Close'].iloc[-1]), 2)
                stock["date"] = datetime.now().strftime("%Y-%m-%d")
                print(f"Updated {symbol}: ${stock['price']}")
            else:
                print(f"No price data for {symbol}")
        except Exception as e:
            print(f"Error for {symbol}: {e}")

# Write back to stockapp.json
with open("stockapp.json", "w") as f:
    json.dump(data, f, indent=2)

print("\nDone! Check stockapp.json for updated prices.")
