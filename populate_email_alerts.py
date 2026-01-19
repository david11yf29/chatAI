import json

# Read stockapp.json
with open("stockapp.json", "r") as f:
    stock_data = json.load(f)

# Filter stocks where |changePercent| > 3
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

# Read email.json, update dailyPriceChange, write back
with open("email.json", "r") as f:
    email_data = json.load(f)

email_data["content"]["dailyPriceChange"] = filtered

with open("email.json", "w") as f:
    json.dump(email_data, f, indent=2)

print(f"Added {len(filtered)} stocks to dailyPriceChange")
