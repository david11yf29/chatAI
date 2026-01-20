# Stock Tracker Button Workflows

> **📌 CANONICAL REFERENCE**
> This document is the **source of truth** for understanding button workflows in the Stock Tracker application.
>
> - **Last Updated:** 2026-01-20 (added default buyPrice logic: if user doesn't input buyPrice, defaults to price * 0.9)
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
- **No persistence** until "Update" button is clicked

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

#### Phase 3: Backend Processing (`main.py` lines 308-369)

6. **Read Existing Data**
   - Loads current `stockapp.json` (source of truth)
   - Extracts existing stocks to compare

7. **Process Each Stock**
   - For each stock in the request (skips stocks with empty symbols):

   8. **Fetch Live Price Data from yfinance**
      - Creates ticker object: `yf.Ticker(symbol)`
      - Retrieves company info: `longName`, `shortName`, or symbol fallback

   9. **Get Historical Price Data**
      - Fetches 2-day history: `ticker.history(period="2d")` (sufficient for previous day's close)
      - Extracts last closing price from history
      - Gets the market close time as ISO 8601 datetime with timezone (e.g., "2026-01-16T16:00:00-05:00")

   10. **Calculate Daily Change Percent**
       - Compares current close vs previous close
       - Formula: `((current - previous) / previous) * 100`

11. **Set Default Buy Price (if not provided)**
    - If `buyPrice` is 0 (user didn't input any value):
    - Formula: `buyPrice = price * 0.9`
    - Example: If price is $37.04, default buyPrice = $33.34
    - This gives a 10% discount target as the default buy price

12. **Calculate Need to Drop Until Buy Price**
    - For all stocks:
    - Formula: `diff = ((buyPrice - price) / price) * 100`
    - Negative diff = above buy price
    - Positive diff = below buy price (good opportunity)

13. **Persist to Database**
    - Writes updated stocks array to `stockapp.json`
    - Preserves other fields like `search`, `_metadata`

14. **Return Response**
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

8. **Verify API Credentials**
   - Checks for `RESEND_API_KEY` in environment variables
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

10. **Send via Resend API**
    - **Endpoint:** `https://api.resend.com/emails`
    - **Method:** POST
    - **Headers:** Authorization with Bearer token
    - **Payload:**
      ```json
      {
          "from": "sender@example.com",
          "to": ["recipient1@example.com", "recipient2@example.com"],
          "subject": "Stock Tracker Report",
          "html": "<full HTML email content>"
      }
      ```

11. **Return Response**
    - On success: Returns status with recipients and Resend response
    - On error: Returns error details with status code

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
- **Resend Email Service** (`https://api.resend.com/emails`)
  - Requires: `RESEND_API_KEY` environment variable
  - Sends formatted HTML email to configured recipients

### Database Operations
- **Read:** `email.json` (configuration and content)
- **No Write** - This is a read-only operation

### Error Handling
- Loading overlay is hidden
- Button text changes to "Error!"
- Auto-reset after 1500ms
- Error logged to console

---

## Summary

### Data Flow Overview

| Button | Action | API Endpoint | DB Read | DB Write | External Services |
|--------|--------|--------------|---------|----------|-------------------|
| **Add** | Add empty row | None | None | None | None |
| **Update** | Save & fetch prices | `PUT /api/stocks`, `GET /api/stocks` | stockapp.json | stockapp.json | yfinance |
| **Update Email** | Generate news | `POST /api/update-email` | stockapp.json, email.json | email.json | OpenAI, Search API, News sites |
| **Send Email** | Send email | `POST /api/send-test-email` | email.json | None | Resend |

### Data Files
- **stockapp.json** - Source of truth for stock portfolio
- **email.json** - Email configuration and generated content

### Environment Variables Required
- `SUPER_MIND_API_KEY` - For AI-powered news generation
- `RESEND_API_KEY` - For email sending via Resend

### Common UI Pattern
All async buttons follow this pattern:
1. Show loading overlay
2. Disable button
3. Change button text to action verb (Saving/Updating/Sending)
4. Make API call
5. On success: show "Success!" text, reset after 1.5s
6. On error: show "Error!" text, reset after 1.5s, log to console
