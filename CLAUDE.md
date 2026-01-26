# Claude Code Project Context

## Overview
Stock Tracker - web app for stock prices, AI news summaries, email reports.

## Key Docs
- **workflow.md** - Source of truth for button logic, API endpoints, frontend-backend flow. Read first, update after changes.

## Architecture

### Files
- `main.py` - Backend API
- `static/js/app.js` - Frontend logic
- `static/index.html` - UI
- `stockapp.json` - Stock data
- `email.json` - Email config/content

### External Services
- **yfinance** - Stock prices
- **OpenAI** - News summarization
- **AI Builder Search API** - Web search
- **Gmail SMTP** - Email delivery

### Environment Variables
- `SUPER_MIND_API_KEY` - AI news generation (fallback: `AI_BUILDER_TOKEN`)
- `GMAIL_USER` - Gmail address
- `GMAIL_APP_PASSWORD` - Gmail app password
