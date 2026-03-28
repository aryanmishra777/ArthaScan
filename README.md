# ArthaScan

Telegram-based mutual fund portfolio analyzer built as a deterministic hackathon prototype.

## Telegram Bot

Live bot: https://t.me/ArthaScanBot

## Architecture

The pipeline follows the required fixed order:

`PDF -> Extraction Engine -> Finance Engine -> Decision Engine -> AI Response Engine -> Telegram Bot`

## Project Structure

```text
bot/
  telegram_bot.py
  handlers.py
extraction/
  extractor.py
  schema.py
finance/
  metrics.py
decision/
  rules.py
ai/
  formatter.py
utils/
  fallback.py
  helpers.py
main.py
requirements.txt
README.md
```

## Setup

1. Create and activate a virtual environment.
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Create a `.env` file in the project root:

```env
TELEGRAM_BOT_TOKEN=your_bot_token
BOT_LANGUAGE=english
USE_GEMINI_EXPLANATIONS=true
GEMINI_API_KEY=your_gemini_api_key
GEMINI_MODEL=gemini-2.5-flash
SAFE_CHAT_MODE=true
```

4. Or set environment variables manually:

```bash
set TELEGRAM_BOT_TOKEN=your_bot_token
set BOT_LANGUAGE=english
```

`BOT_LANGUAGE` supports `english` and `hinglish`.
`USE_GEMINI_EXPLANATIONS` defaults to `true` and only affects the explanation layer.
`SAFE_CHAT_MODE` defaults to `true` and allows guarded free-text portfolio questions.

## Run

```bash
python main.py
```

## Supported Flow

- `/start` explains how to use the bot
- Upload a PDF mutual fund statement
- The bot shows staged progress updates
- The bot returns a deterministic analysis with inline buttons
- `Download detailed report` generates a simple PDF summary

## Demo Fallback

If extraction fails or times out, the system uses deterministic demo data:

- XIRR: `11.2`
- Overlap: `65`
- Expense ratio: `1.5`
- Alpha: `-1.4`
- Wealth bleed over 10 years: `320000`

The user is explicitly notified when demo data is used.

## Notes

- No business logic is inside any LLM call
- All calculations are implemented in Python
- Free-text chat is enabled in guarded mode and only answers uploaded-portfolio questions
- The system always returns a usable response and avoids hard crashes
- Gemini is only used for short explanation responses and always falls back to deterministic templates
