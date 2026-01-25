from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse
import asyncio
from pydantic import BaseModel
from openai import OpenAI
from dotenv import load_dotenv
import os
import logging
import time
import uuid
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
import json
import sys
import httpx
from bs4 import BeautifulSoup
import re
import yfinance as yf
import smtplib
from email.message import EmailMessage
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.date import DateTrigger

load_dotenv()

# Configure logging with more detailed format
logging.basicConfig(
    level=logging.DEBUG,  # Changed to DEBUG for more verbose logging
    format='%(asctime)s - %(name)s - %(levelname)s - [%(request_id)s] - %(funcName)s:%(lineno)d - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('app.log', mode='a')  # Also log to file
    ]
)

# Create a custom filter to add request_id to log records
class RequestIdFilter(logging.Filter):
    def filter(self, record):
        if not hasattr(record, 'request_id'):
            record.request_id = 'N/A'
        return True

# Apply the filter to the root logger and all its handlers
request_id_filter = RequestIdFilter()
root_logger = logging.getLogger()
root_logger.addFilter(request_id_filter)

# Also add the filter to all existing handlers to ensure it works in subprocesses
for handler in root_logger.handlers:
    handler.addFilter(request_id_filter)

logger = logging.getLogger(__name__)

app = FastAPI()

# Global scheduler for scheduled tasks
scheduler = AsyncIOScheduler()

# SSE (Server-Sent Events) client management
sse_clients: set[asyncio.Queue] = set()

async def broadcast_sse_event(event_type: str, data: dict = None):
    """Broadcast an event to all connected SSE clients."""
    import json
    event_data = json.dumps({"type": event_type, "data": data or {}})
    message = f"event: {event_type}\ndata: {event_data}\n\n"

    # Send to all connected clients
    disconnected = set()
    for client_queue in sse_clients:
        try:
            await client_queue.put(message)
        except Exception:
            disconnected.add(client_queue)

    # Clean up disconnected clients
    for client_queue in disconnected:
        sse_clients.discard(client_queue)

    logger.info(f"Broadcast SSE event '{event_type}' to {len(sse_clients)} clients")

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Use SUPER_MIND_API_KEY or fall back to AI_BUILDER_TOKEN (injected by platform)
api_key = os.getenv("SUPER_MIND_API_KEY") or os.getenv("AI_BUILDER_TOKEN")
client = OpenAI(
    api_key=api_key,
    base_url="https://space.ai-builders.com/backend/v1"
)

# Web search function
def web_search(query: str) -> dict:
    """
    Call the internal search API to search the web.

    Args:
        query: The search query string

    Returns:
        dict: Search results from the API
    """
    url = "https://space.ai-builders.com/backend/v1/search/"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "keywords": [query],
        "max_results": 3
    }

    try:
        with httpx.Client() as http_client:
            response = http_client.post(url, json=payload, headers=headers, timeout=30.0)
            response.raise_for_status()
            return response.json()
    except Exception as e:
        logger.error(f"Error calling web search API: {e}")
        return {"error": str(e)}

# Read page function
def read_page(url: str) -> dict:
    """
    Fetch a URL and extract the main text content from the HTML.
    Strips HTML tags, scripts, and styles to return clean text.

    Args:
        url: The URL to fetch and read

    Returns:
        dict: Contains the extracted text or error message
    """
    try:
        with httpx.Client() as http_client:
            # Fetch the URL with a timeout
            response = http_client.get(url, timeout=30.0, follow_redirects=True)
            response.raise_for_status()

            # Parse HTML with BeautifulSoup
            soup = BeautifulSoup(response.text, 'html.parser')

            # Remove script and style elements
            for script in soup(['script', 'style', 'noscript']):
                script.decompose()

            # Get text content
            text = soup.get_text()

            # Clean up the text: remove extra whitespace
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            text = ' '.join(chunk for chunk in chunks if chunk)

            # Limit text length to avoid overwhelming the LLM (max 10000 chars)
            if len(text) > 10000:
                text = text[:10000] + "... (truncated)"

            logger.info(f"Successfully fetched and parsed {url} - Text length: {len(text)} chars")

            return {
                "url": url,
                "text": text,
                "length": len(text)
            }

    except Exception as e:
        logger.error(f"Error reading page {url}: {e}")
        return {"error": str(e), "url": url}


def summarize_page_content(url: str, text: str, symbol: str, name: str) -> str:
    """
    Summarize the page content using LLM to extract key news information.

    Args:
        url: The source URL
        text: The raw text content from the page
        symbol: Stock symbol for context
        name: Stock name for context

    Returns:
        str: Summarized content focusing on news relevant to the stock
    """
    try:
        summary_prompt = f"""Summarize the following article content in 2-3 concise sentences, focusing on information relevant to {symbol} ({name}) stock. Extract the key news points that could explain stock price movement.

Article from: {url}

Content:
{text[:5000]}

Provide only the summary, no additional commentary."""

        logger.info(f"[summarize_page_content] Summarizing content for {symbol} from {url}")

        summary_response = client.chat.completions.create(
            model="supermind-agent-v1",
            messages=[{"role": "user", "content": summary_prompt}]
        )

        summary = summary_response.choices[0].message.content or ""
        logger.info(f"[summarize_page_content] Summary generated for {symbol}: {summary[:200]}")

        return summary

    except Exception as e:
        logger.error(f"[summarize_page_content] Error summarizing content for {symbol}: {e}")
        # Return truncated original text as fallback
        return text[:1000] + "..." if len(text) > 1000 else text

# Tool schema for the LLM
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Search the web for current information, news, facts, and other real-time data. Use this when you need up-to-date information that you don't have in your training data.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query to find information on the web"
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_page",
            "description": "Fetch and read the content of a specific web page. Extracts the main text from the HTML, removing scripts, styles, and other non-content elements. Use this when you have a specific URL and want to read its contents.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "The URL of the web page to fetch and read"
                    }
                },
                "required": ["url"]
            }
        }
    }
]

class ChatRequest(BaseModel):
    user_message: str

class StockUpdate(BaseModel):
    symbol: str
    name: str
    price: float
    changePercent: float | None = None
    date: str
    buyPrice: float

class StocksUpdateRequest(BaseModel):
    stocks: list[StockUpdate]

class ScheduleRequest(BaseModel):
    trigger_time: str  # ISO 8601 format, e.g., "2026-01-23T07:00:00+08:00"

@app.get("/")
async def root():
    return FileResponse("static/index.html")

@app.get("/api/stocks")
async def get_stocks():
    with open("stockapp.json", "r") as f:
        data = json.load(f)
    return {"stocks": data["stocks"]}

@app.get("/api/stock-info/{symbol}")
async def get_stock_info(symbol: str):
    """Fetch company name based on stock symbol using the configured search source."""
    symbol = symbol.upper().strip()

    # Read the search source from stockapp.json
    with open("stockapp.json", "r") as f:
        config = json.load(f)
    search_source = config.get("search", "google finance").lower()

    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
    }

    try:
        with httpx.Client() as http_client:
            if "google" in search_source:
                # Try multiple exchanges for Google Finance
                exchanges = ["NASDAQ", "NYSE", "NYSEARCA", "BATS", "MUTF"]
                for exchange in exchanges:
                    url = f"https://www.google.com/finance/quote/{symbol}:{exchange}"
                    response = http_client.get(url, timeout=10.0, follow_redirects=True, headers=headers)

                    if response.status_code == 200:
                        soup = BeautifulSoup(response.text, 'html.parser')
                        title = soup.find('title')
                        if title:
                            title_text = title.get_text()
                            # Title format: "Company Name (SYMBOL) Price & News - Google Finance"
                            if '(' in title_text and symbol in title_text:
                                company_name = title_text.split('(')[0].strip()
                                return {"symbol": symbol, "name": company_name, "source": "google finance"}

                return {"symbol": symbol, "name": symbol, "error": "Could not find on Google Finance"}

            else:
                # Use yfinance for Yahoo Finance
                pass  # Exit the httpx client context, use yfinance below

        # Use yfinance library for Yahoo Finance
        if "yahoo" in search_source:
            try:
                ticker = yf.Ticker(symbol)
                info = ticker.info
                company_name = info.get("longName") or info.get("shortName") or symbol
                return {"symbol": symbol, "name": company_name, "source": "yahoo finance (yfinance)"}
            except Exception as yf_error:
                logger.error(f"yfinance error for {symbol}: {yf_error}")
                return {"symbol": symbol, "name": symbol, "error": f"Could not find on Yahoo Finance: {yf_error}"}

    except Exception as e:
        logger.error(f"Error fetching stock info for {symbol}: {e}")
        return {"symbol": symbol, "name": symbol, "error": str(e)}


def format_market_close_time(trading_date) -> str:
    """Convert trading date to market close time in Taiwan Time.

    US stock market closes at 4:00 PM Eastern Time, which is 5:00 AM next day in Taiwan.

    Args:
        trading_date: The trading date from yfinance (pandas Timestamp or datetime)

    Returns:
        ISO 8601 formatted string like "2026-01-17T05:00:00+08:00"
    """
    # Get the trading date as a date object
    trade_date = trading_date.date() if hasattr(trading_date, 'date') else trading_date

    # Market closes at 4:00 PM Eastern Time = 5:00 AM next day Taiwan Time
    taiwan = ZoneInfo("Asia/Taipei")
    # Add one day to get the next day, set time to 5:00 AM
    next_day = trade_date + timedelta(days=1)
    market_close = datetime(next_day.year, next_day.month, next_day.day, 5, 0, 0, tzinfo=taiwan)

    # Format as ISO 8601 with timezone offset
    return market_close.isoformat()


@app.put("/api/stocks")
async def update_stocks(request: StocksUpdateRequest):
    """Update stocks - saves symbol/buyPrice first, then fetches prices from yfinance.

    Two-phase save approach:
    1. Save symbol/buyPrice to stockapp.json FIRST (preserves user edits even if yfinance fails)
    2. Fetch prices from yfinance
    3. Final save with updated prices
    """
    # Read existing data to preserve the search field and _metadata
    with open("stockapp.json", "r") as f:
        existing_data = json.load(f)

    existing_stocks = existing_data.get("stocks", [])

    # STEP 1: Save symbol/buyPrice FIRST (before yfinance calls)
    # This ensures user edits are persisted even if yfinance fails
    preliminary_stocks = []
    for i, stock in enumerate(request.stocks):
        stock_dict = stock.model_dump()
        symbol = stock.symbol.upper().strip()
        stock_dict["symbol"] = symbol

        # Preserve existing price data if symbol unchanged
        if i < len(existing_stocks) and existing_stocks[i].get("symbol", "").upper() == symbol:
            stock_dict["price"] = existing_stocks[i].get("price", 0)
            stock_dict["changePercent"] = existing_stocks[i].get("changePercent", 0)
            stock_dict["date"] = existing_stocks[i].get("date", "")
            stock_dict["name"] = existing_stocks[i].get("name", symbol)
            stock_dict["diff"] = existing_stocks[i].get("diff", 0)
        else:
            # Symbol changed or new stock - set defaults
            stock_dict["price"] = stock_dict.get("price", 0)
            stock_dict["changePercent"] = stock_dict.get("changePercent", 0)
            stock_dict["date"] = stock_dict.get("date", "")
            stock_dict["name"] = stock_dict.get("name", symbol)
            stock_dict["diff"] = stock_dict.get("diff", 0)

        preliminary_stocks.append(stock_dict)

    # Write preliminary save (symbol/buyPrice persisted)
    existing_data["stocks"] = preliminary_stocks
    with open("stockapp.json", "w") as f:
        json.dump(existing_data, f, indent=2)
    logger.info(f"Preliminary save completed: {len(preliminary_stocks)} stocks saved to stockapp.json")

    # STEP 2: Fetch yfinance data for each stock
    updated_stocks = []
    for stock_dict in preliminary_stocks:
        symbol = stock_dict["symbol"]

        # Fetch fresh prices for stocks with valid symbols
        if symbol:
            logger.info(f"Fetching fresh data for {symbol}")
            try:
                ticker = yf.Ticker(symbol)
                info = ticker.info
                stock_dict["name"] = info.get("longName") or info.get("shortName") or symbol

                # Get last closed price and calculate percentage change
                history = ticker.history(period="2d")
                if not history.empty:
                    stock_dict["price"] = round(float(history['Close'].iloc[-1]), 2)
                    # Get the actual market close time in +08:00 timezone
                    trading_date = history.index[-1]
                    price_date = format_market_close_time(trading_date)
                    stock_dict["date"] = price_date

                    # Calculate percentage change from previous day
                    if len(history) >= 2:
                        current_close = float(history['Close'].iloc[-1])
                        previous_close = float(history['Close'].iloc[-2])
                        change_percent = ((current_close - previous_close) / previous_close) * 100
                        stock_dict["changePercent"] = round(change_percent, 2)
                    else:
                        stock_dict["changePercent"] = None

                    logger.info(f"Fetched price for {symbol}: {stock_dict['price']} (date: {price_date}, change: {stock_dict.get('changePercent')}%)")
            except Exception as e:
                logger.error(f"yfinance error for {symbol}: {e}")

        # Always calculate diff: percentage difference from buy price (negative = above buy price)
        price = stock_dict.get("price", 0)
        buy_price = stock_dict.get("buyPrice", 0)

        # If buyPrice is 0 (user didn't input any value), default to price * 0.9
        if buy_price == 0 and price > 0:
            buy_price = round(price * 0.9, 2)
            stock_dict["buyPrice"] = buy_price
            logger.info(f"Set default buyPrice for {symbol}: {buy_price} (90% of price {price})")

        if price > 0:
            diff = round(((buy_price - price) / price) * 100, 2)
            stock_dict["diff"] = diff

        updated_stocks.append(stock_dict)

    # STEP 3: Final save with updated prices
    existing_data["stocks"] = updated_stocks
    with open("stockapp.json", "w") as f:
        json.dump(existing_data, f, indent=2)
    logger.info(f"Final save completed: {len(updated_stocks)} stocks with prices saved to stockapp.json")

    return {"message": "Stocks updated successfully", "stocks": updated_stocks}


@app.patch("/api/stocks/autosave")
async def autosave_stocks(request: StocksUpdateRequest):
    """Auto-save stock Symbol and Buy Price changes WITHOUT fetching prices.

    This endpoint is called automatically when user edits fields in the frontend.
    It preserves existing price data while updating only symbol and buyPrice.
    The scheduled 'Update' task will later fetch fresh prices for these stocks.
    """
    logger.info(f"[autosave_stocks] Auto-saving {len(request.stocks)} stocks")

    # Read existing data to preserve metadata and other fields
    with open("stockapp.json", "r") as f:
        existing_data = json.load(f)

    # Build a map of existing stocks by index for preserving price data
    existing_stocks = existing_data.get("stocks", [])

    updated_stocks = []
    for i, stock in enumerate(request.stocks):
        stock_dict = stock.model_dump()
        symbol = stock.symbol.upper().strip()
        stock_dict["symbol"] = symbol

        # Preserve existing price data if available (from previous updates)
        if i < len(existing_stocks):
            existing = existing_stocks[i]
            # Keep price, changePercent, date, name if not provided or if symbol unchanged
            if existing.get("symbol", "").upper() == symbol:
                stock_dict["price"] = existing.get("price", 0)
                stock_dict["changePercent"] = existing.get("changePercent", 0)
                stock_dict["date"] = existing.get("date", "")
                stock_dict["name"] = existing.get("name", symbol)
            else:
                # Symbol changed - reset price data, will be fetched by scheduled task
                stock_dict["price"] = stock_dict.get("price", 0)
                stock_dict["changePercent"] = stock_dict.get("changePercent", 0)
                stock_dict["date"] = stock_dict.get("date", "")
                stock_dict["name"] = symbol

        # Calculate diff based on current price and buyPrice
        price = stock_dict.get("price", 0)
        buy_price = stock_dict.get("buyPrice", 0)
        if price > 0:
            diff = round(((buy_price - price) / price) * 100, 2)
            stock_dict["diff"] = diff
        else:
            stock_dict["diff"] = 0

        updated_stocks.append(stock_dict)
        logger.info(f"[autosave_stocks] Saved {symbol} with buyPrice={stock_dict.get('buyPrice')}")

    # Write to stockapp.json (SOURCE OF TRUTH)
    existing_data["stocks"] = updated_stocks
    with open("stockapp.json", "w") as f:
        json.dump(existing_data, f, indent=2)

    logger.info(f"[autosave_stocks] Auto-save completed for {len(updated_stocks)} stocks")
    return {"message": "Stocks auto-saved successfully", "stocks": updated_stocks}


def _perform_update_stocks() -> dict:
    """Core logic to update stock prices from yfinance.

    Reads current stocks from stockapp.json, fetches fresh prices,
    calculates changePercent and diff values, and writes back.

    Returns:
        dict: Result with success status and count of updated stocks
    """
    # Read existing data
    with open("stockapp.json", "r") as f:
        existing_data = json.load(f)

    existing_stocks = existing_data.get("stocks", [])
    updated_stocks = []
    updated_count = 0

    for stock in existing_stocks:
        stock_dict = dict(stock)
        symbol = stock.get("symbol", "").upper().strip()

        if symbol:
            logger.info(f"[_perform_update_stocks] Fetching fresh data for {symbol}")
            try:
                ticker = yf.Ticker(symbol)
                info = ticker.info
                stock_dict["name"] = info.get("longName") or info.get("shortName") or symbol

                # Get last closed price and calculate percentage change
                history = ticker.history(period="2d")
                if not history.empty:
                    stock_dict["price"] = round(float(history['Close'].iloc[-1]), 2)
                    trading_date = history.index[-1]
                    price_date = format_market_close_time(trading_date)
                    stock_dict["date"] = price_date

                    # Calculate percentage change from previous day
                    if len(history) >= 2:
                        current_close = float(history['Close'].iloc[-1])
                        previous_close = float(history['Close'].iloc[-2])
                        change_percent = ((current_close - previous_close) / previous_close) * 100
                        stock_dict["changePercent"] = round(change_percent, 2)
                    else:
                        stock_dict["changePercent"] = None

                    updated_count += 1
                    logger.info(f"[_perform_update_stocks] Updated {symbol}: ${stock_dict['price']} (change: {stock_dict.get('changePercent')}%)")
            except Exception as e:
                logger.error(f"[_perform_update_stocks] yfinance error for {symbol}: {e}")

        # Calculate diff: percentage difference from buy price
        price = stock_dict.get("price", 0)
        buy_price = stock_dict.get("buyPrice", 0)

        if buy_price == 0 and price > 0:
            buy_price = round(price * 0.9, 2)
            stock_dict["buyPrice"] = buy_price

        if price > 0:
            diff = round(((buy_price - price) / price) * 100, 2)
            stock_dict["diff"] = diff

        updated_stocks.append(stock_dict)

    # Write updated data back to stockapp.json
    existing_data["stocks"] = updated_stocks
    with open("stockapp.json", "w") as f:
        json.dump(existing_data, f, indent=2)

    logger.info(f"[_perform_update_stocks] Completed: {updated_count} stocks updated")

    return {
        "success": True,
        "updated_count": updated_count,
        "total_stocks": len(updated_stocks)
    }


@app.delete("/api/stocks/{symbol}")
async def delete_stock(symbol: str):
    """Remove a stock from the portfolio by symbol."""
    symbol = symbol.upper().strip()

    # Read existing data
    with open("stockapp.json", "r") as f:
        data = json.load(f)

    # Filter out the stock with matching symbol
    original_count = len(data["stocks"])
    data["stocks"] = [s for s in data["stocks"] if s["symbol"].upper() != symbol]

    if len(data["stocks"]) == original_count:
        return {"message": f"Stock {symbol} not found", "success": False}

    # Save updated data back to stockapp.json
    with open("stockapp.json", "w") as f:
        json.dump(data, f, indent=2)

    return {"message": f"Stock {symbol} removed successfully", "success": True}


def get_stock_news(symbol: str, name: str, change_percent: float) -> str:
    """Fetch relevant news summary for a stock using AI chat API with web search."""
    direction = "increased" if change_percent > 0 else "decreased"

    # Load preferred news sources from email.json
    try:
        with open("email.json", "r") as f:
            email_config = json.load(f)
        news_sources = email_config.get("newsSearch", [])
    except Exception as e:
        logger.warning(f"[get_stock_news] Could not load newsSearch from email.json: {e}")
        news_sources = []

    # Build the prompt with preferred sources and movement-specific keywords
    sources_instruction = ""
    if news_sources:
        sources_list = ", ".join(news_sources)

        # Select movement-specific keywords based on direction
        if change_percent > 0:
            movement_keywords = "surge, spike, jump"
        else:
            movement_keywords = "plunge, dive, drop, tank"

        sources_instruction = f"""
PREFERRED SOURCES: Search these sites first: {sources_list}

SEARCH KEYWORDS (use these in your search):
- "{symbol} stock {movement_keywords}"
- "{symbol} after-hours news"
"""

    prompt = f"""Find news explaining why {symbol} ({name}) stock {direction} by {abs(change_percent):.2f}%.
{sources_instruction}
WORKFLOW (follow exactly):
1. Call web_search ONCE to find relevant articles
2. From the search results, pick ONE article URL that relates to the stock price movement
3. Call read_page with that URL to read the article content
4. Return a 2-3 sentence summary of the key news points

CRITICAL: After web_search, IMMEDIATELY call read_page on a relevant article URL. Do NOT search again. Just pick one article and read it.

Return ONLY the final summary. No planning text, no "I will", no "Let me" - just the news summary."""

    messages = [{"role": "user", "content": prompt}]
    final_response = ""

    logger.info(f"[get_stock_news] Starting news fetch for {symbol} with preferred sources: {news_sources}")

    try:
        # supermind-agent-v1 has built-in web search - single call handles everything
        logger.info(f"[get_stock_news] Calling supermind-agent-v1 for {symbol}")

        response = client.chat.completions.create(
            model="supermind-agent-v1",
            messages=messages
        )

        final_response = response.choices[0].message.content or ""
        logger.info(f"[get_stock_news] Response for {symbol}: {final_response[:200] if final_response else 'EMPTY'}")

    except Exception as e:
        logger.error(f"[get_stock_news] Exception for {symbol}: {e}", exc_info=True)
        final_response = ""

    # Clean up thinking/planning text from the response
    if final_response:
        lines = final_response.split('\n')
        cleaned_lines = []
        for line in lines:
            line_lower = line.lower().strip()
            # Skip empty lines and lines that look like thinking/planning text
            if not line.strip():
                continue
            if any(phrase in line_lower for phrase in [
                'i will', 'i\'ll', 'let me', 'proceeding', 'reading article',
                'opening article', 'now reading', 'searching for', 'looking for',
                'reading the', 'opening the', 'attempting to', 'trying',
                'will return', 'continuing', 'finalizing', 'returning only',
                'now attempting', 'searching again'
            ]):
                continue
            cleaned_lines.append(line)
        final_response = '\n'.join(cleaned_lines).strip()
        logger.info(f"[get_stock_news] Cleaned response for {symbol}: {final_response[:200] if final_response else 'EMPTY'}")

    return final_response


async def _perform_update_email() -> dict:
    """Core logic to update email.json with dailyPriceChange and needToDropUntilBuyPrice from stockapp.json.

    Returns:
        dict: Result with success status and counts
    """
    # Read stockapp.json
    with open("stockapp.json", "r") as f:
        stock_data = json.load(f)

    # Filter stocks where |changePercent| > 3 for dailyPriceChange
    filtered = []
    for s in stock_data["stocks"]:
        if abs(s.get("changePercent", 0) or 0) > 3:
            logger.info(f"Fetching news for {s['symbol']}...")
            news = get_stock_news(s["symbol"], s["name"], s["changePercent"])
            filtered.append({
                "symbol": s["symbol"],
                "name": s["name"],
                "price": s["price"],
                "changePercent": s["changePercent"],
                "date": s.get("date", ""),
                "news": news
            })

    # Get all stocks for needToDropUntilBuyPrice (symbol, price, diff, date)
    diff_to_buy = [
        {
            "symbol": s["symbol"],
            "price": s["price"],
            "diff": s.get("diff", 0),
            "date": s.get("date", "")
        }
        for s in stock_data["stocks"]
    ]

    # Read email.json, update both arrays, write back
    with open("email.json", "r") as f:
        email_data = json.load(f)

    email_data["content"]["dailyPriceChange"] = filtered
    email_data["content"]["needToDropUntilBuyPrice"] = diff_to_buy

    with open("email.json", "w") as f:
        json.dump(email_data, f, indent=2)

    return {
        "success": True,
        "dailyPriceChangeCount": len(filtered),
        "needToDropUntilBuyPriceCount": len(diff_to_buy)
    }


@app.post("/api/update-email")
async def update_email():
    """Update email.json with dailyPriceChange and needToDropUntilBuyPrice from stockapp.json."""
    result = await _perform_update_email()
    return result

# ============================================================================
# Apple-Inspired Email Template Helper Functions
# ============================================================================

def format_price(price: float) -> str:
    """Format price as $X,XXX.XX"""
    return f"${price:,.2f}"


def format_change_percent(change: float) -> tuple[str, str]:
    """Return (formatted_string, color) for daily price change."""
    if change >= 0:
        return f"+{change:.2f}%", "#34c759"  # Apple Green
    else:
        return f"{change:.2f}%", "#ff3b30"  # Apple Red


def format_diff_percent(diff: float) -> tuple[str, str]:
    """Return (formatted_string, color) for diff to buy price.
    Negative = price above buy price (red, not ideal to buy)
    Positive = price below buy price (green, good to buy)
    """
    if diff >= 0:
        return f"+{diff:.1f}%", "#34c759"  # Apple Green (below buy price - good to buy)
    else:
        return f"{diff:.1f}%", "#ff3b30"  # Apple Red (above buy price - not ideal)


def parse_news_headlines(news_string: str) -> list[str]:
    """Parse '- headline' format into list of headlines."""
    if not news_string:
        return []
    headlines = []
    for line in news_string.strip().split('\n'):
        line = line.strip()
        if line.startswith('- '):
            headlines.append(line[2:])
        elif line:
            headlines.append(line)
    return headlines


def generate_stock_card_html(stock: dict) -> str:
    """Generate HTML for a Daily Price Change stock card."""
    symbol = stock.get("symbol", "")
    name = stock.get("name", "")
    price = stock.get("price", 0)
    change_percent = stock.get("changePercent", 0)
    news = stock.get("news", "")

    formatted_price = format_price(price)
    change_str, change_color = format_change_percent(change_percent)
    headlines = parse_news_headlines(news)

    # Build news section HTML
    news_html = ""
    if headlines:
        news_items = "".join([
            f'''<tr>
                <td style="padding: 8px 0 8px 16px; font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Display', 'Helvetica Neue', Helvetica, Arial, sans-serif; font-size: 14px; color: #1d1d1f; line-height: 1.5; border-left: 3px solid #0071e3;">
                    {headline}
                </td>
            </tr>'''
            for headline in headlines[:3]
        ])
        news_html = f'''
        <tr>
            <td colspan="2" style="padding-top: 16px;">
                <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">
                    <tr>
                        <td style="padding-bottom: 8px; font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Display', 'Helvetica Neue', Helvetica, Arial, sans-serif; font-size: 12px; font-weight: 600; color: #86868b; text-transform: uppercase; letter-spacing: 0.5px;">
                            Latest News
                        </td>
                    </tr>
                    {news_items}
                </table>
            </td>
        </tr>'''

    return f'''
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color: #f5f5f7; border-radius: 12px; margin-bottom: 16px;">
        <tr>
            <td style="padding: 24px;">
                <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">
                    <tr>
                        <td style="vertical-align: top;">
                            <span style="font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Display', 'Helvetica Neue', Helvetica, Arial, sans-serif; font-size: 20px; font-weight: 600; color: #1d1d1f;">{symbol}</span>
                            <br>
                            <span style="font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Display', 'Helvetica Neue', Helvetica, Arial, sans-serif; font-size: 14px; color: #86868b;">{name}</span>
                        </td>
                        <td style="text-align: right; vertical-align: top;">
                            <span style="font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Display', 'Helvetica Neue', Helvetica, Arial, sans-serif; font-size: 28px; font-weight: 500; color: #1d1d1f;">{formatted_price}</span>
                            <br>
                            <span style="font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Display', 'Helvetica Neue', Helvetica, Arial, sans-serif; font-size: 17px; font-weight: 500; color: {change_color};">{change_str}</span>
                        </td>
                    </tr>
                    {news_html}
                </table>
            </td>
        </tr>
    </table>'''


def generate_diff_card_html(stock: dict) -> str:
    """Generate HTML for a Need to Drop Until Buy Price stock card."""
    symbol = stock.get("symbol", "")
    price = stock.get("price", 0)
    diff = stock.get("diff", 0)

    formatted_price = format_price(price)
    diff_str, diff_color = format_diff_percent(diff)

    return f'''
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color: #f5f5f7; border-radius: 12px; margin-bottom: 12px;">
        <tr>
            <td style="padding: 20px 24px;">
                <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">
                    <tr>
                        <td style="vertical-align: middle;">
                            <span style="font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Display', 'Helvetica Neue', Helvetica, Arial, sans-serif; font-size: 17px; font-weight: 600; color: #1d1d1f;">{symbol}</span>
                            <span style="font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Display', 'Helvetica Neue', Helvetica, Arial, sans-serif; font-size: 17px; color: #86868b; margin-left: 12px;">{formatted_price}</span>
                        </td>
                        <td style="text-align: right; vertical-align: middle;">
                            <span style="display: inline-block; padding: 6px 12px; background-color: {diff_color}; color: #ffffff; font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Display', 'Helvetica Neue', Helvetica, Arial, sans-serif; font-size: 14px; font-weight: 600; border-radius: 6px;">{diff_str}</span>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>'''


def generate_stock_email_html():
    """Generate Apple-inspired HTML email content with stock portfolio sections from email.json."""
    # Load email content from email.json
    with open("email.json", "r") as f:
        email_config = json.load(f)

    content = email_config.get("content", {})
    daily_price_change = content.get("dailyPriceChange", [])
    diff_to_buy_price = content.get("needToDropUntilBuyPrice", [])

    # Generate Daily Price Change cards
    daily_change_cards = ""
    if daily_price_change:
        daily_change_cards = "".join(generate_stock_card_html(stock) for stock in daily_price_change)
    else:
        daily_change_cards = '''
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color: #f5f5f7; border-radius: 12px;">
            <tr>
                <td style="padding: 32px; text-align: center; font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Display', 'Helvetica Neue', Helvetica, Arial, sans-serif; font-size: 15px; color: #86868b;">
                    No significant price changes today
                </td>
            </tr>
        </table>'''

    # Generate Need to Drop Until Buy Price cards
    diff_cards = ""
    if diff_to_buy_price:
        diff_cards = "".join(generate_diff_card_html(stock) for stock in diff_to_buy_price)
    else:
        diff_cards = '''
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color: #f5f5f7; border-radius: 12px;">
            <tr>
                <td style="padding: 32px; text-align: center; font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Display', 'Helvetica Neue', Helvetica, Arial, sans-serif; font-size: 15px; color: #86868b;">
                    No stocks in portfolio
                </td>
            </tr>
        </table>'''

    # Get current date for footer
    current_date = datetime.now().strftime("%B %d, %Y")

    return f'''<!DOCTYPE html>
<html lang="en" xmlns="http://www.w3.org/1999/xhtml" xmlns:v="urn:schemas-microsoft-com:vml" xmlns:o="urn:schemas-microsoft-com:office:office">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta http-equiv="X-UA-Compatible" content="IE=edge">
    <meta name="x-apple-disable-message-reformatting">
    <title>Stock Tracker Report</title>
    <!--[if mso]>
    <noscript>
        <xml>
            <o:OfficeDocumentSettings>
                <o:PixelsPerInch>96</o:PixelsPerInch>
            </o:OfficeDocumentSettings>
        </xml>
    </noscript>
    <![endif]-->
</head>
<body style="margin: 0; padding: 0; background-color: #ffffff; font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Display', 'Helvetica Neue', Helvetica, Arial, sans-serif;">
    <!-- Outer wrapper table for centering -->
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color: #ffffff;">
        <tr>
            <td align="center" style="padding: 40px 20px;">
                <!-- Main container - max-width 600px -->
                <table role="presentation" width="600" cellpadding="0" cellspacing="0" border="0" style="max-width: 600px; width: 100%;">

                    <!-- Header Section -->
                    <tr>
                        <td align="center" style="padding: 0 0 48px 0;">
                            <!-- Stock Tracker Icon -->
                            <table role="presentation" cellpadding="0" cellspacing="0" border="0">
                                <tr>
                                    <td style="padding-bottom: 16px;">
                                        <div style="width: 56px; height: 56px; background: linear-gradient(135deg, #0071e3 0%, #40a9ff 100%); border-radius: 12px; display: inline-block; text-align: center; line-height: 56px;">
                                            <span style="font-size: 28px; color: #ffffff;">&#x1F4C8;</span>
                                        </div>
                                    </td>
                                </tr>
                            </table>
                            <h1 style="margin: 0; font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Display', 'Helvetica Neue', Helvetica, Arial, sans-serif; font-size: 32px; font-weight: 600; color: #1d1d1f; letter-spacing: -0.5px;">
                                Stock Tracker
                            </h1>
                            <p style="margin: 8px 0 0 0; font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Display', 'Helvetica Neue', Helvetica, Arial, sans-serif; font-size: 17px; color: #86868b; font-weight: 400;">
                                Daily Portfolio Report
                            </p>
                        </td>
                    </tr>

                    <!-- Divider -->
                    <tr>
                        <td style="padding: 0 0 40px 0;">
                            <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">
                                <tr>
                                    <td style="border-bottom: 1px solid #d2d2d7;"></td>
                                </tr>
                            </table>
                        </td>
                    </tr>

                    <!-- Daily Price Change Section -->
                    <tr>
                        <td style="padding: 0 0 40px 0;">
                            <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color: #0071e3; border-radius: 8px; margin-bottom: 24px;">
                                <tr>
                                    <td style="padding: 16px 20px;">
                                        <h2 style="margin: 0; font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Display', 'Helvetica Neue', Helvetica, Arial, sans-serif; font-size: 24px; font-weight: 600; color: #ffffff;">
                                            Daily Price Change
                                        </h2>
                                        <p style="margin: 4px 0 0 0; font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Display', 'Helvetica Neue', Helvetica, Arial, sans-serif; font-size: 15px; color: rgba(255,255,255,0.8);">
                                            Stocks with significant movements
                                        </p>
                                    </td>
                                </tr>
                            </table>
                            {daily_change_cards}
                        </td>
                    </tr>

                    <!-- Divider -->
                    <tr>
                        <td style="padding: 0 0 40px 0;">
                            <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">
                                <tr>
                                    <td style="border-bottom: 1px solid #d2d2d7;"></td>
                                </tr>
                            </table>
                        </td>
                    </tr>

                    <!-- Need to Drop Until Buy Price Section -->
                    <tr>
                        <td style="padding: 0 0 48px 0;">
                            <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color: #0071e3; border-radius: 8px; margin-bottom: 24px;">
                                <tr>
                                    <td style="padding: 16px 20px;">
                                        <h2 style="margin: 0; font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Display', 'Helvetica Neue', Helvetica, Arial, sans-serif; font-size: 24px; font-weight: 600; color: #ffffff;">
                                            Need to Drop Until Buy Price
                                        </h2>
                                        <p style="margin: 4px 0 0 0; font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Display', 'Helvetica Neue', Helvetica, Arial, sans-serif; font-size: 15px; color: rgba(255,255,255,0.8);">
                                            Distance from target buy prices
                                        </p>
                                    </td>
                                </tr>
                            </table>
                            {diff_cards}
                        </td>
                    </tr>

                    <!-- Divider -->
                    <tr>
                        <td style="padding: 0 0 40px 0;">
                            <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">
                                <tr>
                                    <td style="border-bottom: 1px solid #d2d2d7;"></td>
                                </tr>
                            </table>
                        </td>
                    </tr>

                    <!-- Footer Section -->
                    <tr>
                        <td align="center" style="padding: 0;">
                            <p style="margin: 0; font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Display', 'Helvetica Neue', Helvetica, Arial, sans-serif; font-size: 14px; font-weight: 600; color: #1d1d1f;">
                                Stock Tracker Report
                            </p>
                            <p style="margin: 8px 0 0 0; font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Display', 'Helvetica Neue', Helvetica, Arial, sans-serif; font-size: 13px; color: #86868b;">
                                Generated on {current_date}
                            </p>
                        </td>
                    </tr>

                </table>
            </td>
        </tr>
    </table>
</body>
</html>'''

async def _perform_send_email() -> dict:
    """Core logic to send email using Gmail SMTP.

    Returns:
        dict: Result with status, recipients, and response details
    """
    # Load email configuration from email.json
    with open("email.json", "r") as f:
        email_config = json.load(f)

    email_to = email_config.get("to", [])
    email_subject = email_config.get("subject", "Stocker Tracker Report")

    if not email_to:
        return {"status": "error", "message": "No email addresses found in email.json"}

    # Get Gmail credentials from environment
    gmail_user = os.getenv("GMAIL_USER")
    gmail_app_password = os.getenv("GMAIL_APP_PASSWORD")

    if not gmail_user or not gmail_app_password:
        return {"status": "error", "message": "GMAIL_USER or GMAIL_APP_PASSWORD not configured"}

    # Generate email HTML content
    email_html = generate_stock_email_html()

    # Create email message
    msg = EmailMessage()
    msg["Subject"] = email_subject
    msg["From"] = gmail_user
    msg["To"] = ", ".join(email_to)
    msg.set_content("Please view this email in an HTML-capable email client.")
    msg.add_alternative(email_html, subtype="html")

    # Send via Gmail SMTP
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(gmail_user, gmail_app_password)
            smtp.send_message(msg)
        return {"status": "sent", "recipients": email_to}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.post("/api/send-test-email")
async def send_test_email():
    """Send a test email using configuration from email.json via Gmail SMTP."""
    result = await _perform_send_email()
    return result


@app.get("/api/schedule-status")
async def get_schedule_status():
    """Check if the chained execution is scheduled.

    Since all three tasks (Update, Update Email, Send Email) now run as a chain,
    when the chain is scheduled, all three indicators show as scheduled.

    Returns:
        dict: Individual status for each task:
              - update: true/false
              - updateEmail: true/false
              - sendEmail: true/false
              All three will be true/false together (they run as a chain).
    """
    try:
        with open("schedule.json", "r") as f:
            schedule_data = json.load(f)

        now = datetime.now(ZoneInfo("Asia/Taipei"))

        # Check if the chain is scheduled using the Update task's trigger_time
        # When the chain is scheduled, all three tasks run together
        chain_scheduled = False
        update_config = schedule_data.get("Update", {})
        if update_config.get("enable", False):
            trigger_time_str = update_config.get("trigger_time")
            if trigger_time_str:
                trigger_time = datetime.fromisoformat(trigger_time_str)
                if trigger_time > now:
                    chain_scheduled = True

        # All three tasks share the same scheduled status (they run as a chain)
        return {
            "update": chain_scheduled,
            "updateEmail": chain_scheduled,
            "sendEmail": chain_scheduled
        }
    except Exception as e:
        logger.error(f"Error checking schedule status: {e}")
        return {"update": False, "updateEmail": False, "sendEmail": False}


@app.post("/api/schedule")
async def update_schedule(request: ScheduleRequest):
    """Update schedule.json with trigger times based on user input.

    - "Update": user's input time
    - "Update Email": user's input time + 3 minutes
    - "Send Email": user's input time + 10 minutes
    """
    try:
        # Parse the input trigger time
        base_time = datetime.fromisoformat(request.trigger_time)

        # Calculate the three trigger times
        update_time = base_time
        update_email_time = base_time + timedelta(minutes=3)
        send_email_time = base_time + timedelta(minutes=10)

        # Read existing schedule.json to preserve other fields
        with open("schedule.json", "r") as f:
            schedule_data = json.load(f)

        # Update the trigger times (preserve enable flags)
        schedule_data["Update"]["trigger_time"] = update_time.isoformat()
        schedule_data["Update Email"]["trigger_time"] = update_email_time.isoformat()
        schedule_data["Send Email"]["trigger_time"] = send_email_time.isoformat()

        # Write back to schedule.json
        with open("schedule.json", "w") as f:
            json.dump(schedule_data, f, indent=2)

        logger.info(f"Schedule updated - Update: {update_time.isoformat()}, "
                   f"Update Email: {update_email_time.isoformat()}, "
                   f"Send Email: {send_email_time.isoformat()}")

        # Re-setup scheduled tasks with new times
        setup_scheduled_tasks()

        return {
            "success": True,
            "schedule": {
                "Update": update_time.isoformat(),
                "Update Email": update_email_time.isoformat(),
                "Send Email": send_email_time.isoformat()
            }
        }
    except ValueError as e:
        logger.error(f"Invalid trigger_time format: {e}")
        return {"success": False, "error": f"Invalid time format: {str(e)}"}
    except Exception as e:
        logger.error(f"Error updating schedule: {e}")
        return {"success": False, "error": str(e)}


@app.get("/api/events")
async def sse_events():
    """Server-Sent Events endpoint for real-time updates.

    Frontend can subscribe to receive notifications when:
    - Scheduled tasks complete (stocks-updated, email-updated, email-sent)
    - Manual button actions complete
    """
    async def event_generator():
        client_queue = asyncio.Queue()
        sse_clients.add(client_queue)
        logger.info(f"SSE client connected. Total clients: {len(sse_clients)}")

        try:
            # Send initial connection event
            yield "event: connected\ndata: {\"status\": \"connected\"}\n\n"

            # Keep connection alive and send events
            while True:
                try:
                    # Wait for events with timeout (for keepalive)
                    message = await asyncio.wait_for(client_queue.get(), timeout=30.0)
                    yield message
                except asyncio.TimeoutError:
                    # Send keepalive ping
                    yield ": keepalive\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            sse_clients.discard(client_queue)
            logger.info(f"SSE client disconnected. Total clients: {len(sse_clients)}")

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@app.get("/favicon.ico")
async def favicon():
    from fastapi.responses import Response
    return Response(status_code=204)

@app.middleware("http")
async def log_requests(request: Request, call_next):
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id

    # Extract client information
    client_ip = request.client.host if request.client else "unknown"
    user_agent = request.headers.get("user-agent", "unknown")
    content_type = request.headers.get("content-type", "unknown")

    logger.info(
        f"Incoming request: {request.method} {request.url.path}",
        extra={'request_id': request_id}
    )

    logger.debug(
        f"Request details - Client IP: {client_ip} - User-Agent: {user_agent} - "
        f"Content-Type: {content_type} - Query params: {dict(request.query_params)}",
        extra={'request_id': request_id}
    )

    # Log request headers (excluding sensitive ones)
    safe_headers = {k: v for k, v in request.headers.items()
                   if k.lower() not in ['authorization', 'cookie', 'x-api-key']}
    logger.debug(
        f"Request headers: {json.dumps(safe_headers)}",
        extra={'request_id': request_id}
    )

    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time

    logger.info(
        f"Request completed: {request.method} {request.url.path} - "
        f"Status: {response.status_code} - Duration: {process_time:.3f}s",
        extra={'request_id': request_id}
    )

    logger.debug(
        f"Response details - Status: {response.status_code} - "
        f"Content-Type: {response.headers.get('content-type', 'unknown')}",
        extra={'request_id': request_id}
    )

    response.headers["X-Request-ID"] = request_id
    response.headers["X-Process-Time"] = str(process_time)

    return response

@app.get("/hello/{input}")
async def hello(input: str, request: Request):
    request_id = getattr(request.state, 'request_id', 'N/A')

    logger.info(
        f"Hello endpoint called with input: {input}",
        extra={'request_id': request_id}
    )

    logger.debug(
        f"Processing hello request - Input length: {len(input)} chars",
        extra={'request_id': request_id}
    )

    response_data = {"message": f"Hello, World {input}"}

    logger.debug(
        f"Returning hello response: {json.dumps(response_data)}",
        extra={'request_id': request_id}
    )

    return response_data

@app.post("/chat")
async def chat(chat_request: ChatRequest, request: Request):
    request_id = getattr(request.state, 'request_id', 'N/A')

    logger.info(
        f"Chat request received - Message length: {len(chat_request.user_message)} chars",
        extra={'request_id': request_id}
    )

    # Log message preview (first 100 chars)
    message_preview = chat_request.user_message[:100] + "..." if len(chat_request.user_message) > 100 else chat_request.user_message
    logger.debug(
        f"User message preview: {message_preview}",
        extra={'request_id': request_id}
    )

    try:
        # Initialize conversation history
        messages = [
            {"role": "user", "content": chat_request.user_message}
        ]

        # Log API call configuration
        api_config = {
            "model": "supermind-agent-v1",
            "base_url": str(client.base_url),
            "messages_count": len(messages)
        }
        logger.info(
            f"Calling supermind-agent-v1 API - Config: {json.dumps(api_config)}",
            extra={'request_id': request_id}
        )

        api_start_time = time.time()
        # supermind-agent-v1 has built-in web search - no tools parameter needed
        response = client.chat.completions.create(
            model="supermind-agent-v1",
            messages=messages
        )
        api_duration = time.time() - api_start_time

        logger.debug(
            f"supermind-agent-v1 API call completed - Duration: {api_duration:.3f}s",
            extra={'request_id': request_id}
        )

        # Extract response details
        message = response.choices[0].message
        final_response = message.content if message.content else ""
        finish_reason = response.choices[0].finish_reason if hasattr(response.choices[0], 'finish_reason') else 'N/A'

        # Log token usage details
        if hasattr(response, 'usage'):
            token_details = {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens
            }
            logger.info(
                f"Token usage - {json.dumps(token_details)}",
                extra={'request_id': request_id}
            )

        print(f"[Agent] Final Answer: '{final_response}'")
        logger.info(
            f"[Agent] Final Answer: '{final_response}'",
            extra={'request_id': request_id}
        )

        logger.info(
            f"supermind-agent-v1 response received - Duration: {api_duration:.3f}s - "
            f"Response length: {len(final_response)} chars - "
            f"Model: {response.model} - "
            f"Finish reason: {finish_reason} - "
            f"Tokens used: {response.usage.total_tokens if hasattr(response, 'usage') else 'N/A'}",
            extra={'request_id': request_id}
        )

        result = {
            "response": final_response,
            "finish_reason": finish_reason
        }

        logger.debug(
            f"Returning chat response - Size: {len(json.dumps(result))} bytes",
            extra={'request_id': request_id}
        )

        # Print the user message and response
        print("\n" + "=" * 80)
        print(f"USER: {chat_request.user_message}")
        print(f"RESPONSE: {final_response}")
        print("=" * 80 + "\n")

        # Log the message
        logger.info(
            f"Chat completed - User: {chat_request.user_message[:100]}... Response: {final_response[:100]}...",
            extra={'request_id': request_id}
        )

        return result

    except Exception as e:
        error_details = {
            "error_type": type(e).__name__,
            "error_message": str(e),
            "user_message_length": len(chat_request.user_message)
        }

        logger.error(
            f"Error during chat processing: {json.dumps(error_details)}",
            extra={'request_id': request_id}
        )

        logger.error(
            f"Full error traceback for {type(e).__name__}",
            extra={'request_id': request_id},
            exc_info=True
        )

        # Log additional context for specific error types
        if "timeout" in str(e).lower():
            logger.error(
                f"Timeout error detected - API call may have taken too long",
                extra={'request_id': request_id}
            )
        elif "api" in str(e).lower() or "key" in str(e).lower():
            logger.error(
                f"API/Authentication error detected - Check API key and configuration",
                extra={'request_id': request_id}
            )

        raise


# ============================================================================
# Scheduled Task Functions
# ============================================================================

async def scheduled_update_email():
    """Wrapper for scheduled Update Email execution with logging."""
    logger.info("=" * 60)
    logger.info("SCHEDULED TASK: Update Email - Starting")
    logger.info("=" * 60)

    try:
        result = await _perform_update_email()
        logger.info(f"SCHEDULED TASK: Update Email - Completed successfully: {result}")
        # Notify frontend that email content was updated
        await broadcast_sse_event("email-updated", result)
    except Exception as e:
        logger.error(f"SCHEDULED TASK: Update Email - Failed with error: {e}")
        raise


async def scheduled_send_email():
    """Wrapper for scheduled Send Email execution with logging."""
    logger.info("=" * 60)
    logger.info("SCHEDULED TASK: Send Email - Starting")
    logger.info("=" * 60)

    try:
        result = await _perform_send_email()
        logger.info(f"SCHEDULED TASK: Send Email - Completed successfully: {result}")
        # Notify frontend that email was sent
        await broadcast_sse_event("email-sent", result)
    except Exception as e:
        logger.error(f"SCHEDULED TASK: Send Email - Failed with error: {e}")
        raise


async def scheduled_update_stocks():
    """Wrapper for scheduled Update (stock prices) execution with logging."""
    logger.info("=" * 60)
    logger.info("SCHEDULED TASK: Update - Starting")
    logger.info("=" * 60)

    try:
        result = _perform_update_stocks()
        logger.info(f"SCHEDULED TASK: Update - Completed successfully: {result}")
        # Notify frontend that stocks were updated
        await broadcast_sse_event("stocks-updated", result)
    except Exception as e:
        logger.error(f"SCHEDULED TASK: Update - Failed with error: {e}")
        raise


async def scheduled_chain_execution():
    """Master orchestrator that chains Update Tracker -> Update News -> Send Email.

    Each task is executed sequentially with 5-second delays between them.
    If one task fails, the chain continues to the next task.
    """
    logger.info("=" * 60)
    logger.info("SCHEDULED CHAIN: Starting chained execution")
    logger.info("=" * 60)

    # Task 1: Update Tracker
    logger.info("SCHEDULED CHAIN: Task 1/3 - Update Tracker - Starting")
    try:
        result = _perform_update_stocks()
        logger.info(f"SCHEDULED CHAIN: Task 1/3 - Update Tracker - Completed: {result}")
        await broadcast_sse_event("stocks-updated", result)
    except Exception as e:
        logger.error(f"SCHEDULED CHAIN: Task 1/3 - Update Tracker - Failed: {e}")

    logger.info("SCHEDULED CHAIN: Waiting 5 seconds before next task...")
    await asyncio.sleep(5)

    # Task 2: Update News
    logger.info("SCHEDULED CHAIN: Task 2/3 - Update News - Starting")
    try:
        result = await _perform_update_email()
        logger.info(f"SCHEDULED CHAIN: Task 2/3 - Update News - Completed: {result}")
        await broadcast_sse_event("email-updated", result)
    except Exception as e:
        logger.error(f"SCHEDULED CHAIN: Task 2/3 - Update News - Failed: {e}")

    logger.info("SCHEDULED CHAIN: Waiting 5 seconds before next task...")
    await asyncio.sleep(5)

    # Task 3: Send Email
    logger.info("SCHEDULED CHAIN: Task 3/3 - Send Email - Starting")
    try:
        result = await _perform_send_email()
        logger.info(f"SCHEDULED CHAIN: Task 3/3 - Send Email - Completed: {result}")
        await broadcast_sse_event("email-sent", result)
    except Exception as e:
        logger.error(f"SCHEDULED CHAIN: Task 3/3 - Send Email - Failed: {e}")

    logger.info("=" * 60)
    logger.info("SCHEDULED CHAIN: All tasks completed")
    logger.info("=" * 60)


def setup_scheduled_tasks():
    """Read schedule.json and schedule a chained job for all tasks.

    This function schedules a single chained job that executes:
    Update Tracker -> (5s delay) -> Update News -> (5s delay) -> Send Email

    The chain starts at the "Update" task's trigger_time. The other task times
    in schedule.json are ignored since tasks now run sequentially.
    """
    logger.info("Setting up scheduled tasks from schedule.json...")

    # Remove all existing scheduled jobs to allow clean rescheduling
    # Include both old individual job IDs and new chained job ID for backward compatibility
    job_ids = [
        "update_stocks_scheduled",
        "update_email_scheduled",
        "send_email_scheduled",
        "chained_execution_scheduled"
    ]
    for job_id in job_ids:
        existing_job = scheduler.get_job(job_id)
        if existing_job:
            scheduler.remove_job(job_id)
            logger.info(f"Removed existing scheduled job: {job_id}")

    try:
        with open("schedule.json", "r") as f:
            schedule_data = json.load(f)
    except FileNotFoundError:
        logger.warning("schedule.json not found - no scheduled tasks will be configured")
        return
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse schedule.json: {e}")
        return

    now = datetime.now(ZoneInfo("Asia/Taipei"))

    # Use the "Update" task's trigger_time as the chain start time
    # The chain will run all three tasks sequentially with 5-second delays
    update_config = schedule_data.get("Update", {})
    if update_config.get("enable", False):
        trigger_time_str = update_config.get("trigger_time")
        if trigger_time_str:
            trigger_time = datetime.fromisoformat(trigger_time_str)
            if trigger_time > now:
                scheduler.add_job(
                    scheduled_chain_execution,
                    trigger=DateTrigger(run_date=trigger_time),
                    id="chained_execution_scheduled",
                    replace_existing=True
                )
                logger.info(f"Scheduled chained execution (Update Tracker -> Update News -> Send Email) for {trigger_time_str}")
            else:
                logger.warning(f"Skipping chained execution - trigger time {trigger_time_str} has already passed")
    else:
        logger.info("Chained execution is disabled (Update task is disabled in schedule.json)")

    # Log summary of all scheduled jobs
    scheduled_jobs = scheduler.get_jobs()
    if scheduled_jobs:
        logger.info(f"Total scheduled jobs: {len(scheduled_jobs)}")
        for job in scheduled_jobs:
            logger.info(f"  - Job '{job.id}' scheduled for {job.next_run_time}")
    else:
        logger.info("No jobs currently scheduled")


@app.on_event("startup")
async def startup_event():
    logger.info("=" * 80)
    logger.info("Application starting up")
    logger.info("=" * 80)

    # Log environment details
    logger.info(f"Python version: {sys.version}")
    logger.info(f"Working directory: {os.getcwd()}")
    logger.info(f"Process ID: {os.getpid()}")

    # Log API configuration
    logger.info(f"OpenAI base URL: {client.base_url}")
    api_key = os.getenv('SUPER_MIND_API_KEY')
    if api_key:
        logger.info(f"API key configured: Yes (length: {len(api_key)} chars, starts with: {api_key[:8]}...)")
    else:
        logger.warning("API key configured: No - API calls will fail!")

    # Log logging configuration
    logger.info(f"Logging level: {logging.getLogger().level}")
    logger.info(f"Log file: app.log")

    # Log FastAPI configuration
    logger.info(f"FastAPI version: {FastAPI.__version__ if hasattr(FastAPI, '__version__') else 'unknown'}")

    # Setup and start APScheduler for scheduled tasks
    setup_scheduled_tasks()
    scheduler.start()
    logger.info("APScheduler started")

    logger.info("Application startup completed successfully")
    logger.info("=" * 80)

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("=" * 80)
    logger.info("Application shutting down")
    logger.info(f"Shutdown time: {datetime.now().isoformat()}")

    # Shutdown APScheduler
    scheduler.shutdown(wait=False)
    logger.info("APScheduler stopped")

    logger.info("Cleanup completed")
    logger.info("=" * 80)
