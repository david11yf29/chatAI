import json

# Read stockapp.json
with open("stockapp.json", "r") as f:
    stock_data = json.load(f)

# Filter stocks where |changePercent| > 3 for dailyPriceChange
filtered = [
    {
        "symbol": s["symbol"],
        "name": s["name"],
        "price": s["price"],
        "changePercent": s["changePercent"]
    }
    for s in stock_data["stocks"]
    if abs(s["changePercent"]) > 3
]

# Get all stocks for diffToBuyPrice (symbol, price, diff)
diff_to_buy = [
    {
        "symbol": s["symbol"],
        "price": s["price"],
        "diff": s["diff"]
    }
    for s in stock_data["stocks"]
]

# Read email.json, update both arrays, write back
with open("email.json", "r") as f:
    email_data = json.load(f)

email_data["content"]["dailyPriceChange"] = filtered
email_data["content"]["diffToBuyPrice"] = diff_to_buy

with open("email.json", "w") as f:
    json.dump(email_data, f, indent=2)

print(f"Added {len(filtered)} stocks to dailyPriceChange")
print(f"Added {len(diff_to_buy)} stocks to diffToBuyPrice")
