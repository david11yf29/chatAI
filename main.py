from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from openai import OpenAI
from dotenv import load_dotenv
import os
import logging
import time
import uuid
from datetime import datetime
import json
import sys
import httpx
from bs4 import BeautifulSoup
import re
import yfinance as yf

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

client = OpenAI(
    api_key=os.getenv("SUPER_MIND_API_KEY"),
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
        "Authorization": f"Bearer {os.getenv('SUPER_MIND_API_KEY')}",
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

@app.put("/api/stocks")
async def update_stocks(request: StocksUpdateRequest):
    """Update stocks - fetches prices for changed symbols and persists to stockapp.json (source of truth)."""
    # Read existing data to preserve the search field and _metadata
    with open("stockapp.json", "r") as f:
        existing_data = json.load(f)

    existing_stocks = existing_data.get("stocks", [])
    updated_stocks = []

    for i, stock in enumerate(request.stocks):
        stock_dict = stock.model_dump()

        # Check if symbol changed (compare with existing)
        symbol_changed = (i >= len(existing_stocks) or
                         stock.symbol.upper() != existing_stocks[i].get("symbol", "").upper())

        if symbol_changed:
            # Fetch from yfinance for changed symbols
            symbol = stock.symbol.upper().strip()
            logger.info(f"Symbol changed at index {i}, fetching data for {symbol}")
            try:
                ticker = yf.Ticker(symbol)
                info = ticker.info
                stock_dict["name"] = info.get("longName") or info.get("shortName") or symbol

                # Get last closed price and calculate percentage change
                history = ticker.history(period="5d")
                if not history.empty:
                    stock_dict["price"] = round(float(history['Close'].iloc[-1]), 2)
                    # Get the actual date of the closed price from yfinance
                    price_date = history.index[-1].strftime("%Y-%m-%d")
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

        # Always calculate diff: percentage current price needs to drop to reach buyPrice
        price = stock_dict.get("price", 0)
        buy_price = stock_dict.get("buyPrice", 0)
        if price > 0:
            diff = round(((price - buy_price) / price) * 100, 2)
            stock_dict["diff"] = diff

        updated_stocks.append(stock_dict)

    # Update stockapp.json (SOURCE OF TRUTH)
    existing_data["stocks"] = updated_stocks
    with open("stockapp.json", "w") as f:
        json.dump(existing_data, f, indent=2)

    return {"message": "Stocks updated successfully", "stocks": updated_stocks}

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

        # Agentic Loop: Allow up to 3 turns
        max_turns = 3
        final_response = None

        for turn in range(max_turns):
            logger.info(
                f"=== Agentic Loop - Turn {turn + 1}/{max_turns} ===",
                extra={'request_id': request_id}
            )

            # Log API call configuration
            api_config = {
                "model": "gpt-5",
                "base_url": str(client.base_url),
                "messages_count": len(messages)
            }
            logger.info(
                f"Calling OpenAI API - Config: {json.dumps(api_config)}",
                extra={'request_id': request_id}
            )

            logger.debug(
                f"API Request payload - Model: gpt-5 - Messages count: {len(messages)}",
                extra={'request_id': request_id}
            )

            api_start_time = time.time()
            response = client.chat.completions.create(
                model="gpt-5",
                messages=messages,
                tools=TOOLS
            )
            api_duration = time.time() - api_start_time

            logger.debug(
                f"OpenAI API call completed - Duration: {api_duration:.3f}s",
                extra={'request_id': request_id}
            )

            # Extract response details
            message = response.choices[0].message
            response_content = message.content if message.content else ""
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

            # Check if the model wants to call a tool
            tool_calls = message.tool_calls if hasattr(message, 'tool_calls') and message.tool_calls else None

            if tool_calls:
                # Agent decided to call tools
                print(f"\n[Agent] Decided to call tool: '{tool_calls[0].function.name}'")
                logger.info(
                    f"[Agent] Decided to call tool: '{tool_calls[0].function.name}'",
                    extra={'request_id': request_id}
                )

                logger.info(
                    f"LLM requested tool call(s): {len(tool_calls)} tool(s)",
                    extra={'request_id': request_id}
                )

                # Add assistant's message with tool calls to conversation
                messages.append({
                    "role": "assistant",
                    "content": response_content,
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": tc.type,
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments
                            }
                        }
                        for tc in tool_calls
                    ]
                })

                # Execute each tool call
                for tool_call in tool_calls:
                    function_name = tool_call.function.name
                    function_args = json.loads(tool_call.function.arguments)

                    logger.info(
                        f"Executing tool - ID: {tool_call.id} - Function: {function_name} - "
                        f"Arguments: {function_args}",
                        extra={'request_id': request_id}
                    )

                    # Execute the appropriate tool function
                    if function_name == "web_search":
                        tool_start_time = time.time()
                        search_result = web_search(function_args.get("query", ""))
                        tool_duration = time.time() - tool_start_time

                        # Format tool output for logging
                        tool_output_preview = json.dumps(search_result)[:200] + "..." if len(json.dumps(search_result)) > 200 else json.dumps(search_result)

                        print(f"[System] Tool Output: '{tool_output_preview}'")
                        logger.info(
                            f"[System] Tool Output: '{tool_output_preview}'",
                            extra={'request_id': request_id}
                        )

                        logger.info(
                            f"Tool execution completed - Duration: {tool_duration:.3f}s - "
                            f"Result size: {len(json.dumps(search_result))} bytes",
                            extra={'request_id': request_id}
                        )

                        # Add tool result to conversation
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "name": function_name,
                            "content": json.dumps(search_result)
                        })

                    elif function_name == "read_page":
                        tool_start_time = time.time()
                        page_result = read_page(function_args.get("url", ""))
                        tool_duration = time.time() - tool_start_time

                        # Format tool output for logging
                        tool_output_preview = json.dumps(page_result)[:200] + "..." if len(json.dumps(page_result)) > 200 else json.dumps(page_result)

                        print(f"[System] Tool Output: '{tool_output_preview}'")
                        logger.info(
                            f"[System] Tool Output: '{tool_output_preview}'",
                            extra={'request_id': request_id}
                        )

                        logger.info(
                            f"Tool execution completed - Duration: {tool_duration:.3f}s - "
                            f"Result size: {len(json.dumps(page_result))} bytes",
                            extra={'request_id': request_id}
                        )

                        # Add tool result to conversation
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "name": function_name,
                            "content": json.dumps(page_result)
                        })

                    else:
                        logger.warning(
                            f"Unknown tool function: {function_name}",
                            extra={'request_id': request_id}
                        )

                # Continue to next turn to get LLM's response with tool results
                continue

            else:
                # No tool calls - this is the final response
                final_response = response_content

                print(f"[Agent] Final Answer: '{final_response}'")
                logger.info(
                    f"[Agent] Final Answer: '{final_response}'",
                    extra={'request_id': request_id}
                )

                logger.info(
                    f"OpenAI API response received - Duration: {api_duration:.3f}s - "
                    f"Response length: {len(response_content)} chars - "
                    f"Model: {response.model} - "
                    f"Finish reason: {finish_reason} - "
                    f"Tokens used: {response.usage.total_tokens if hasattr(response, 'usage') else 'N/A'}",
                    extra={'request_id': request_id}
                )

                # Log response preview
                response_preview = response_content[:100] + "..." if len(response_content) > 100 else response_content
                logger.debug(
                    f"Response preview: {response_preview}",
                    extra={'request_id': request_id}
                )

                # Log response structure details
                logger.debug(
                    f"Response structure - Choices count: {len(response.choices)} - "
                    f"Response ID: {response.id if hasattr(response, 'id') else 'N/A'} - "
                    f"Created: {response.created if hasattr(response, 'created') else 'N/A'}",
                    extra={'request_id': request_id}
                )

                # Exit the loop
                break

        # If we exhausted all turns without a final response
        if final_response is None:
            final_response = "I apologize, but I've reached the maximum number of tool calls. Please try rephrasing your question."
            logger.warning(
                f"Max turns ({max_turns}) reached without final response",
                extra={'request_id': request_id}
            )

        result = {
            "response": final_response,
            "finish_reason": finish_reason,
            "turns_used": turn + 1
        }

        logger.debug(
            f"Returning chat response - Size: {len(json.dumps(result))} bytes - Turns used: {turn + 1}",
            extra={'request_id': request_id}
        )

        # Print the entire message history that led to this response
        print("\n" + "=" * 80)
        print("COMPLETE MESSAGE HISTORY")
        print("=" * 80)
        for i, msg in enumerate(messages, 1):
            print(f"\n--- Message {i} ---")
            print(f"Role: {msg.get('role', 'N/A')}")

            if msg.get('role') == 'user':
                print(f"Content: {msg.get('content', 'N/A')}")

            elif msg.get('role') == 'assistant':
                print(f"Content: {msg.get('content', 'N/A')}")
                if 'tool_calls' in msg:
                    print("\nTool Calls:")
                    for tc in msg['tool_calls']:
                        print(f"  - ID: {tc.get('id', 'N/A')}")
                        print(f"    Type: {tc.get('type', 'N/A')}")
                        print(f"    Function Name: {tc.get('function', {}).get('name', 'N/A')}")
                        print(f"    Function Arguments: {tc.get('function', {}).get('arguments', 'N/A')}")

            elif msg.get('role') == 'tool':
                print(f"Tool Call ID: {msg.get('tool_call_id', 'N/A')}")
                print(f"Tool Name: {msg.get('name', 'N/A')}")
                print(f"Tool Result (preview): {msg.get('content', 'N/A')[:500]}...")

        print("\n" + "=" * 80)
        print(f"FINAL RESPONSE TO USER: {final_response}")
        print("=" * 80 + "\n")

        # Also log the full message history
        logger.info(
            f"Complete message history: {json.dumps(messages, indent=2)}",
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

    logger.info("Application startup completed successfully")
    logger.info("=" * 80)

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("=" * 80)
    logger.info("Application shutting down")
    logger.info(f"Shutdown time: {datetime.now().isoformat()}")
    logger.info("Cleanup completed")
    logger.info("=" * 80)
