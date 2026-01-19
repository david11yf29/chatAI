import json
import os
from openai import OpenAI

# Initialize OpenAI client for AI chat API
client = OpenAI(
    api_key=os.getenv("SUPER_MIND_API_KEY"),
    base_url="https://space.ai-builders.com/backend/v1"
)


def get_stock_news(symbol: str, name: str, change_percent: float) -> str:
    """Fetch relevant news headlines for a stock using AI chat API."""
    direction = "increased" if change_percent > 0 else "decreased"
    prompt = f"Search the web and find 3 recent news headlines about {symbol} ({name}) that could potentially explain why the stock {direction} by {abs(change_percent):.2f}%. Proceed automatically without asking for permission. Return only the headlines as a brief bulleted list."

    response = client.chat.completions.create(
        model="gpt-5",
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content or ""


# Read stockapp.json
with open("stockapp.json", "r") as f:
    stock_data = json.load(f)

# Filter stocks where |changePercent| > 3 for dailyPriceChange
filtered = []
for s in stock_data["stocks"]:
    if abs(s["changePercent"]) > 3:
        print(f"Fetching news for {s['symbol']}...")
        news = get_stock_news(s["symbol"], s["name"], s["changePercent"])
        filtered.append({
            "symbol": s["symbol"],
            "name": s["name"],
            "price": s["price"],
            "changePercent": s["changePercent"],
            "news": news
        })

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
