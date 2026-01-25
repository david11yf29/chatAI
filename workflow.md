# Stock Tracker Button Workflows

> **📌 CANONICAL REFERENCE**
> This document is the **source of truth** for understanding button workflows in the Stock Tracker application.
>
> - **Last Updated:** 2026-01-25 (Implemented chained execution: Update → Update Email → Send Email run sequentially with 5s delays)
> - **Maintainer:** Update this file whenever button logic changes in the code
> - **Files to watch:** `static/js/app.js`, `main.py`, `static/index.html`
>
> If the code and this document conflict, let me know the conflict first, and after I solve the conflict, please update this document first due to this document is the source of truth before any implementation, and then you can start the actual implementation.

---

This document describes the detailed workflow for each of the four main buttons in the Stock Tracker application.

---

## Button 1: "Add" Button

### UI Location
- **File:** `static/index.html` (line 18)
- **Button ID:** `add-btn`
- **Style:** Green button in table header

### Event Handler
- **File:** `static/js/app.js`
- **Handler Registration:** Line 249
- **Function:** `addStock()` (lines 46-65)

### Workflow Steps

1. **Click Event Triggered**
   - User clicks the green "Add" button

2. **Create New Stock Object**
   - A new empty stock object is created with default values:
     ```javascript
     {
         symbol: "",
         name: "New Stock",
         price: 0,
         changePercent: 0,
         date: "",
         buyPrice: 0,
         diff: 0
     }
     ```

3. **Update Local Array**
   - New stock object is pushed to `currentStocks` array

4. **Re-render UI**
   - `renderStocks(currentStocks)` is called to redraw the table with the new row

5. **Auto-focus Input**
   - The symbol input field of the new row is automatically focused for user input

6. **User Input Handling**
   - **Symbol Input:** As user types, text is converted to uppercase and stored
   - **Buy Price Input:** Value is parsed as float and stored

### Side Effects
- Visual: New empty table row appears
- Memory: New stock object added to `currentStocks` array
- UI: Symbol input field receives focus
- **No API call** - This is purely client-side
- **Auto-save on input** - As user types, changes are auto-saved after 500ms debounce (see Auto-Save Feature below)

---

## Auto-Save Feature

### Purpose
Automatically saves Symbol and Buy Price changes when the user finishes editing a field (on blur event). This ensures the scheduled "Update" task picks up the latest user edits.

### Implementation

#### Frontend (`static/js/app.js`)
- **Function:** `autoSaveStocks()` - Sends current stocks to auto-save endpoint
- **Function:** `debouncedAutoSave()` - Debounces saves (500ms delay) to avoid excessive API calls
- **Event Listeners:** `input` events on `.symbol-input` and `.buy-price-input` fields (saves as user types)

#### Backend (`main.py`)
- **Endpoint:** `PATCH /api/stocks/autosave`
- **Function:** `autosave_stocks()` - Saves Symbol and Buy Price WITHOUT fetching prices from yfinance

### Workflow Steps

1. **User edits Symbol or Buy Price field**
   - `input` event updates `currentStocks` array in memory
   - `input` event also triggers `debouncedAutoSave()`

2. **After 500ms of no typing (debounce delay)**
   - `autoSaveStocks()` sends `PATCH /api/stocks/autosave`
   - Request body: `{ "stocks": currentStocks }`

4. **Backend processes request**
   - Reads existing `stockapp.json` to preserve price data
   - Updates Symbol and Buy Price from request
   - Preserves existing `price`, `changePercent`, `date`, `name` if symbol unchanged
   - Recalculates `diff` based on current price and new buy price
   - Writes to `stockapp.json`

5. **Frontend receives response**
   - Updates `currentStocks` with response data (preserves price info)

### Key Behavior
- **Saves as you type:** Auto-save triggers on every keystroke (debounced), not just when leaving the field
- **Preserves price data:** If the symbol hasn't changed, existing price/changePercent/date/name are preserved
- **Resets price data:** If symbol changes, price data is reset (will be fetched by scheduled Update task)
- **No loading overlay:** Auto-save happens silently in background
- **Debounced:** Multiple rapid edits only trigger one save after 500ms of no typing

### Integration with Scheduled Tasks
When the scheduled "Update" task runs:
1. It reads `stockapp.json` which now contains the auto-saved Symbol/Buy Price
2. Fetches fresh prices from yfinance for those symbols
3. Writes updated prices back to `stockapp.json`

This ensures user edits are picked up by scheduled tasks without requiring manual "Update" button click.

---

## Button 2: "Update" Button

### UI Location
- **File:** `static/index.html` (line 30)
- **Button ID:** `update-btn`
- **Style:** Blue button in actions section

### Event Handler
- **File:** `static/js/app.js`
- **Handler Registration:** Line 250
- **Function:** `saveStocks()` (lines 129-171)

### Workflow Steps

#### Phase 1: UI Feedback (Immediate)

1. **Click Event Triggered**
   - User clicks the blue "Update" button

2. **Show Loading Overlay**
   - `setLoading(true)` displays semi-transparent overlay with spinner
   - Freezes UI interaction

3. **Disable Button**
   - Button is disabled to prevent duplicate submissions

4. **Update Button Text**
   - Text changes from "Update" to "Saving..."

#### Phase 2: Frontend API Call

5. **HTTP PUT Request Initiated**
   - **Endpoint:** `/api/stocks`
   - **Method:** PUT
   - **Headers:** `Content-Type: application/json`
   - **Body:** `{ "stocks": currentStocks }`

#### Phase 3: Backend Processing (`main.py` lines 339-440)

**Two-Phase Save Approach:** Symbol/buyPrice are saved FIRST before yfinance calls, ensuring user edits are persisted even if yfinance fails partway through.

##### Step 1: Preliminary Save (Symbol/BuyPrice)

6. **Read Existing Data**
   - Loads current `stockapp.json` (source of truth)
   - Extracts existing stocks to compare

7. **Build Preliminary Stocks List**
   - For each stock in the request:
     - Normalize symbol to uppercase
     - If symbol unchanged from existing data, preserve existing price data (price, changePercent, date, name, diff)
     - If symbol changed or new stock, set defaults

8. **Write Preliminary Save**
   - Writes symbol/buyPrice to `stockapp.json` immediately
   - **Benefit:** User edits are now persisted even if yfinance calls fail

##### Step 2: Fetch yfinance Data

9. **Process Each Stock**
   - For each stock with a valid symbol:

   10. **Fetch Live Price Data from yfinance**
       - Creates ticker object: `yf.Ticker(symbol)`
       - Retrieves company info: `longName`, `shortName`, or symbol fallback

   11. **Get Historical Price Data**
       - Fetches 2-day history: `ticker.history(period="2d")` (sufficient for previous day's close)
       - Extracts last closing price from history
       - Gets the market close time as ISO 8601 datetime with Taiwan timezone (e.g., "2026-01-17T05:00:00+08:00")

   12. **Calculate Daily Change Percent**
       - Compares current close vs previous close
       - Formula: `((current - previous) / previous) * 100`

13. **Set Default Buy Price (if not provided)**
    - If `buyPrice` is 0 (user didn't input any value):
    - Formula: `buyPrice = price * 0.9`
    - Example: If price is $37.04, default buyPrice = $33.34
    - This gives a 10% discount target as the default buy price

14. **Calculate Need to Drop Until Buy Price**
    - For all stocks:
    - Formula: `diff = ((buyPrice - price) / price) * 100`
    - Negative diff = above buy price
    - Positive diff = below buy price (good opportunity)

##### Step 3: Final Save

15. **Persist to Database**
    - Writes updated stocks array with prices to `stockapp.json`
    - Preserves other fields like `search`, `_metadata`

16. **Return Response**
    - Returns success message with updated stocks array

#### Phase 4: Frontend Updates

15. **Response Received**
    - Frontend checks if response is `ok` (status 200-299)

16. **Re-fetch from Server**
    - Calls `fetchStocks()` via `GET /api/stocks`
    - Ensures UI shows data from source of truth

17. **UI Re-render**
    - `renderStocks(currentStocks)` displays updated data with fresh prices

#### Phase 5: Success Feedback

18. **Hide Loading Overlay**
    - `setLoading(false)` removes the overlay

19. **Show Success Message**
    - Button text changes to "Saved!"

20. **Auto-reset (after 1500ms)**
    - Button text reverts to "Update"
    - Button re-enabled

### API Endpoints Called
1. `PUT /api/stocks` - Saves stocks with price updates
2. `GET /api/stocks` - Retrieves fresh stock data after save

### External Services
- **yfinance** - Fetches live stock prices from Yahoo Finance

### Database Operations
- **Read:** `stockapp.json`
- **Write:** `stockapp.json`

### Error Handling
- Loading overlay is hidden
- Button text changes to "Error!"
- Auto-reset after 1500ms
- Error logged to console

---

## Button 3: "Update Email" Button

### UI Location
- **File:** `static/index.html` (line 31)
- **Button ID:** `update-email-btn`
- **Style:** Teal/cyan button in actions section

### Event Handler
- **File:** `static/js/app.js`
- **Handler Registration:** Line 251
- **Function:** `updateEmail()` (lines 173-208)

### Workflow Steps

#### Phase 1: UI Feedback (Immediate)

1. **Click Event Triggered**
   - User clicks the teal "Update Email" button

2. **Show Loading Overlay**
   - `setLoading(true)` displays overlay with spinner

3. **Disable Button**
   - Button is disabled to prevent duplicate submissions

4. **Update Button Text**
   - Text changes from "Update Email" to "Updating..."

#### Phase 2: Frontend API Call

5. **HTTP POST Request Initiated**
   - **Endpoint:** `/api/update-email`
   - **Method:** POST
   - **No Request Body**

#### Phase 3: Backend Processing (`main.py` lines 560-605)

6. **Load Stock Data**
   - Reads `stockapp.json` to get current portfolio

7. **Filter Significant Price Changes**
   - For each stock where `|changePercent| > 3`:

   8. **Fetch News via AI (`get_stock_news()` function, lines 394-557)**

      a. **Determine Price Direction**
         - Whether price increased or decreased

      b. **Load Preferred News Sources**
         - Reads `email.json` to get `newsSearch` array
         - Example: `["https://www.investors.com/", "https://seekingalpha.com/"]`

      c. **Build AI Prompt**
         - Creates instruction to find relevant news
         - Prioritizes preferred sources
         - Instructs AI to search → read → summarize

      d. **Agentic Loop (max 4 turns)**

         **For each turn:**

         i. **Call OpenAI Chat API**
            - Model: `gpt-5`
            - Messages: Conversation history with tools

         ii. **Execute `web_search` Tool (if AI requests)**
             - API: `https://space.ai-builders.com/backend/v1/search/`
             - Headers: Authorization with `SUPER_MIND_API_KEY`
             - Payload: `{"keywords": [query], "max_results": 3}`
             - Returns: Search results with article URLs
             - **Date Filtering:** LLM should filter out news articles that were created/published/updated before the `date` field in `email.json`, since news explaining stock price movements should be published after the market closes on that day

         iii. **Execute `read_page` Tool (if AI requests)**
              - Fetches full article content via HTTP GET
              - Extracts main text using BeautifulSoup
              - Calls LLM again to summarize the article
              - Returns concise 2-3 sentence summary

         iv. **Add Tool Results to Conversation**
             - Appends results back to message history
             - Continues loop for next AI turn

         v. **Get Final Response**
            - When AI stops calling tools, captures final summary

      e. **Cleanup Response Text**
         - Removes thinking/planning text patterns
         - Returns clean summary only

9. **Collect All Stocks for Diff Section**
   - Creates array of ALL stocks (not just those with price changes)
   - Includes distance from buy price and market close time for each:
     ```python
     {
         "symbol": s["symbol"],
         "price": s["price"],
         "diff": s.get("diff", 0),
         "date": s.get("date", "")
     }
     ```

10. **Update email.json**
    - **dailyPriceChange:** Array of stocks with >3% change + AI-generated news + date
    - **needToDropUntilBuyPrice:** All stocks with buy price comparison + date

11. **Return Response**
    - Returns JSON with counts:
      ```python
      {
          "success": True,
          "dailyPriceChangeCount": len(filtered),
          "needToDropUntilBuyPriceCount": len(diff_to_buy)
      }
      ```

#### Phase 4: Success Feedback

12. **Hide Loading Overlay**
    - `setLoading(false)` removes the overlay

13. **Show Success Message**
    - Button text changes to "Updated!"

14. **Auto-reset (after 1500ms)**
    - Button text reverts to "Update Email"
    - Button re-enabled

### API Endpoints Called
1. `POST /api/update-email` - Triggers news generation

### External Services
1. **OpenAI Chat Completions** - AI-powered news analysis
2. **AI Builder Search API** - Web search for news articles
3. **Various News Sites** - Full article content via HTTP GET

### Database Operations
- **Read:** `stockapp.json`, `email.json`
- **Write:** `email.json` (updates `content.dailyPriceChange` and `content.needToDropUntilBuyPrice`)

### Error Handling
- Loading overlay is hidden
- Button text changes to "Error!"
- Auto-reset after 1500ms
- Error logged to console

---

## Button 4: "Send Email" Button

### UI Location
- **File:** `static/index.html` (line 32)
- **Button ID:** `send-email-btn`
- **Style:** Orange button in actions section

### Event Handler
- **File:** `static/js/app.js`
- **Handler Registration:** Line 252
- **Function:** `sendEmail()` (lines 210-245)

### Workflow Steps

#### Phase 1: UI Feedback (Immediate)

1. **Click Event Triggered**
   - User clicks the orange "Send Email" button

2. **Show Loading Overlay**
   - `setLoading(true)` displays overlay with spinner

3. **Disable Button**
   - Button is disabled to prevent duplicate submissions

4. **Update Button Text**
   - Text changes from "Send Email" to "Sending..."

#### Phase 2: Frontend API Call

5. **HTTP POST Request Initiated**
   - **Endpoint:** `/api/send-test-email`
   - **Method:** POST
   - **No Request Body**

#### Phase 3: Backend Processing (`main.py` lines 918-958)

6. **Load Email Configuration**
   - Reads `email.json` for template and recipients
   - Extracts: `from`, `to`, `subject`, `content`

7. **Validate Recipients**
   - Checks that recipient list is not empty
   - Uses default sender if not configured

8. **Verify Gmail Credentials**
   - Checks for `GMAIL_USER` and `GMAIL_APP_PASSWORD` in environment variables
   - Fails fast if credentials missing

9. **Generate Email HTML (`generate_stock_email_html()` function, lines 739-916)**

   a. **Load Email Content**
      - Reads `email.json` to get current content
      - Extracts `dailyPriceChange` and `needToDropUntilBuyPrice` arrays

   b. **Generate Daily Price Change Section**
      - For each stock in `dailyPriceChange`:
        - Calls `generate_stock_card_html()` (lines 649-707)
        - Generates Apple-inspired HTML card with:
          - Symbol and company name
          - Current price formatted as `$X,XXX.XX`
          - Daily change % with color (green for +, red for -)
          - Latest news (up to 3 headlines)
      - If no price changes: displays "No significant price changes today"

   c. **Generate Need to Drop Until Buy Price Section**
      - For each stock in `needToDropUntilBuyPrice`:
        - Calls `generate_diff_card_html()` (lines 710-736)
        - Generates card with:
          - Symbol and current price
          - Diff to buy price with color-coded badge
          - Green: below buy price (good opportunity)
          - Red: above buy price (overpriced)
      - If no stocks: displays "No stocks in portfolio"

   d. **Generate Complete HTML Email**
      - Creates full HTML email template with:
        - Apple-inspired design
        - Header with Stock Tracker branding
        - Daily Price Change section
        - Need to Drop Until Buy Price section
        - Footer with generation date
      - Uses inline CSS for email client compatibility
      - Responsive design for mobile devices

10. **Send via Gmail SMTP**
    - **Server:** `smtp.gmail.com:465` (SSL)
    - **Authentication:** Gmail App Password
    - **Process:**
      - Create EmailMessage with subject, from (GMAIL_USER), to (comma-joined recipients)
      - Set plain text fallback and HTML content
      - Connect via SMTP_SSL and send message

11. **Return Response**
    - On success: Returns status with recipients
    - On error: Returns error message from SMTP exception

#### Phase 4: Success Feedback

12. **Response Received & Logged**
    - Data logged to console

13. **Hide Loading Overlay**
    - `setLoading(false)` removes the overlay

14. **Show Success Message**
    - Button text changes to "Sent!"

15. **Auto-reset (after 1500ms)**
    - Button text reverts to "Send Email"
    - Button re-enabled

### API Endpoints Called
1. `POST /api/send-test-email` - Triggers email sending

### External Services
- **Gmail SMTP** (`smtp.gmail.com:465`)
  - Requires: `GMAIL_USER` and `GMAIL_APP_PASSWORD` environment variables
  - Sends formatted HTML email to configured recipients via SSL connection

### Database Operations
- **Read:** `email.json` (configuration and content)
- **No Write** - This is a read-only operation

### Error Handling
- Loading overlay is hidden
- Button text changes to "Error!"
- Auto-reset after 1500ms
- Error logged to console

---

## Scheduled Task Execution

In addition to manual button clicks, the "Update", "Update Email", and "Send Email" tasks can be triggered automatically at scheduled times using APScheduler.

### Chained Execution Model

**All three tasks run as a chain, not independently.** When the scheduled time arrives:

1. **Update Tracker** runs first
2. Wait **5 seconds**
3. **Update News** runs
4. Wait **5 seconds**
5. **Send Email** runs

This ensures data flows correctly: stock prices are updated before generating email content, and email content is generated before sending.

### Configuration File

**File:** `schedule.json`

**Structure:**
```json
{
  "Update": {
    "enable": true,
    "trigger_time": "2026-01-17T07:00:00+08:00"
  },
  "Update Email": {
    "enable": true,
    "trigger_time": "2026-01-17T07:30:00+08:00"
  },
  "Send Email": {
    "enable": true,
    "trigger_time": "2026-01-17T07:40:00+08:00"
  }
}
```

**Note:** Only the `Update.trigger_time` is used to start the chain. The other trigger times are stored for backward compatibility but are ignored since all tasks run sequentially.

### Configuration Fields

| Field | Description |
|-------|-------------|
| `Update.enable` | Boolean - whether the chained execution should be scheduled |
| `Update.trigger_time` | ISO 8601 datetime with timezone when the chain starts |

### Scheduler Implementation

**Library:** APScheduler (AsyncIOScheduler)

**File:** `main.py`

**Key Functions:**
- `setup_scheduled_tasks()` - Reads `schedule.json` and schedules the chained job
- `scheduled_chain_execution()` - Master orchestrator that runs Update Tracker → Update News → Send Email with 5-second delays
- Individual wrappers (`scheduled_update_stocks()`, etc.) still exist for potential standalone use

### Job ID

- **`chained_execution_scheduled`** - Single job ID for the chained execution

### Lifecycle Events

1. **Application Startup (`startup_event`):**
   - Calls `setup_scheduled_tasks()` to read schedule.json
   - Schedules single `chained_execution_scheduled` job
   - Starts the APScheduler with `scheduler.start()`

2. **Application Shutdown (`shutdown_event`):**
   - Stops the APScheduler with `scheduler.shutdown(wait=False)`

### Workflow: Chained Execution

1. **On Application Startup:**
   - Read `schedule.json`
   - Check `Update.enable` - if true and trigger_time is in future:
     - Schedule `scheduled_chain_execution` job
     - Job ID: `chained_execution_scheduled`

2. **When Scheduled Time Arrives:**
   - APScheduler triggers `scheduled_chain_execution()`
   - **Task 1/3:** Update Tracker
     - Calls `_perform_update_stocks()`
     - Broadcasts `stocks-updated` SSE event
   - **5-second delay**
   - **Task 2/3:** Update News
     - Calls `_perform_update_email()`
     - Broadcasts `email-updated` SSE event
   - **5-second delay**
   - **Task 3/3:** Send Email
     - Calls `_perform_send_email()`
     - Broadcasts `email-sent` SSE event
   - Chain complete

### Error Handling (Fault Tolerance)

If one task fails, the chain **continues** to the next task:

| Task | Fails | Result |
|------|-------|--------|
| Update Tracker | Yes | Logs error, waits 5s, continues to Update News |
| Update News | Yes | Logs error, waits 5s, continues to Send Email |
| Send Email | Yes | Logs error, chain ends |

This ensures a single failure doesn't block subsequent tasks.

### Edge Case Handling

| Scenario | Behavior |
|----------|----------|
| `schedule.json` missing | Log warning, no chain scheduled |
| `schedule.json` invalid JSON | Log error, no chain scheduled |
| `Update.trigger_time` in the past | Log warning, no chain scheduled |
| `Update.enable: false` | Log info, no chain scheduled |
| Individual task fails | Log error, chain continues to next task |

### Log Messages

**Startup:**
```
Setting up scheduled tasks from schedule.json...
Scheduled chained execution (Update Tracker -> Update News -> Send Email) for 2026-01-17T07:00:00+08:00
Total scheduled jobs: 1
  - Job 'chained_execution_scheduled' scheduled for 2026-01-17 07:00:00+08:00
APScheduler started
```

**Execution:**
```
============================================================
SCHEDULED CHAIN: Starting chained execution
============================================================
SCHEDULED CHAIN: Task 1/3 - Update Tracker - Starting
SCHEDULED CHAIN: Task 1/3 - Update Tracker - Completed: {...}
SCHEDULED CHAIN: Waiting 5 seconds before next task...
SCHEDULED CHAIN: Task 2/3 - Update News - Starting
SCHEDULED CHAIN: Task 2/3 - Update News - Completed: {...}
SCHEDULED CHAIN: Waiting 5 seconds before next task...
SCHEDULED CHAIN: Task 3/3 - Send Email - Starting
SCHEDULED CHAIN: Task 3/3 - Send Email - Completed: {...}
============================================================
SCHEDULED CHAIN: All tasks completed
============================================================
```

### Schedule Status API

The `/api/schedule-status` endpoint reflects the chain model:
- When the chain is scheduled, all three indicators (`update`, `updateEmail`, `sendEmail`) return `true`
- When the chain is not scheduled, all three return `false`

---

## Real-Time Frontend Updates (SSE)

The application uses Server-Sent Events (SSE) to push real-time updates from the backend to the frontend.

### How It Works

1. **Frontend connects on page load**
   - `connectSSE()` in `app.js` establishes connection to `/api/events`
   - Connection auto-reconnects on errors

2. **Backend broadcasts events after task completion**
   - `stocks-updated`: After scheduled/manual Update Tracker completes
   - `email-updated`: After scheduled/manual Update News completes
   - `email-sent`: After scheduled/manual Send Email completes

3. **Frontend reacts to events**
   - On `stocks-updated`: Calls `fetchStocks()` to refresh UI with new data

### SSE Endpoint

- **URL:** `GET /api/events`
- **Response:** `text/event-stream`
- **Events:**
  - `connected` - Initial connection acknowledgment
  - `stocks-updated` - Stock prices updated
  - `email-updated` - Email content generated
  - `email-sent` - Email sent successfully

### Key Behavior

- Scheduled tasks automatically notify frontend when complete
- Frontend refreshes stock data without manual page reload
- Keepalive pings sent every 30 seconds to maintain connection
- **On reconnection:** Frontend fetches latest stocks to catch any events missed during disconnection

---

## Summary

### Data Flow Overview

| Button/Feature | Action | API Endpoint | DB Read | DB Write | External Services | Schedulable |
|----------------|--------|--------------|---------|----------|-------------------|-------------|
| **Add** | Add empty row | None | None | None | None | No |
| **Auto-Save** | Save edits on blur | `PATCH /api/stocks/autosave` | stockapp.json | stockapp.json | None | No |
| **Update** | Save & fetch prices | `PUT /api/stocks`, `GET /api/stocks` | stockapp.json | stockapp.json | yfinance | Yes |
| **Update Email** | Generate news | `POST /api/update-email` | stockapp.json, email.json | email.json | OpenAI, Search API, News sites | Yes |
| **Send Email** | Send email | `POST /api/send-test-email` | email.json | None | Gmail SMTP | Yes |

### Data Files
- **stockapp.json** - Source of truth for stock portfolio
- **email.json** - Email configuration and generated content
- **schedule.json** - Scheduled task configuration (trigger times and enable flags)

### Environment Variables Required
- `SUPER_MIND_API_KEY` - For AI-powered news generation
- `GMAIL_USER` - Gmail email address for sending emails
- `GMAIL_APP_PASSWORD` - Gmail App Password (16-character code from Google Account settings)

### Common UI Pattern
All async buttons follow this pattern:
1. Show loading overlay
2. Disable button
3. Change button text to action verb (Saving/Updating/Sending)
4. Make API call
5. On success: show "Success!" text, reset after 1.5s
6. On error: show "Error!" text, reset after 1.5s, log to console
