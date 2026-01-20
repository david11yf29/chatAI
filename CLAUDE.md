# Claude Code Project Context

## Project Overview
Stock Tracker application - A web app for tracking stock prices, generating AI-powered news summaries, and sending email reports.

## Key Documentation

### workflow.md (SOURCE OF TRUTH)
**Always read `workflow.md` first** when working on tasks related to:
- Button functionality (Add, Update, Update Email, Send Email)
- API endpoints (`/api/stocks`, `/api/update-email`, `/api/send-test-email`)
- Frontend-backend communication flow
- External service integrations (yfinance, OpenAI, Resend)

This file contains the canonical reference for how the application's main features work.

## Process Reminders

### When Modifying Button Logic
1. **Before coding**: Read `workflow.md` to understand the current flow
2. **After coding**: Update `workflow.md` to reflect any changes made to:
   - Event handlers in `static/js/app.js`
   - API endpoints in `main.py`
   - Button definitions in `static/index.html`
3. **Update the "Last Updated" date** in workflow.md header

### Files to Watch for Workflow Changes
- `static/js/app.js` - Frontend event handlers and API calls
- `main.py` - Backend API endpoints and business logic
- `static/index.html` - Button definitions and UI structure
- `stockapp.json` - Stock data storage
- `email.json` - Email configuration and content

## Architecture Quick Reference

### Data Files
- `stockapp.json` - Source of truth for stock portfolio
- `email.json` - Email configuration and generated content

### External Services
- **yfinance** - Stock price data from Yahoo Finance
- **OpenAI (gpt-5)** - AI-powered news summarization
- **AI Builder Search API** - Web search for news articles
- **Resend** - Email delivery service

### Environment Variables
- `SUPER_MIND_API_KEY` - For AI-powered news generation
- `RESEND_API_KEY` - For email sending via Resend
