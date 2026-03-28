# ArthaScan: The AI Portfolio Advisor 🏆

> **Hackathon Prototype:** A multimodal, deterministic mutual fund analyzer natively built into Telegram.

Retail investors are flying blind, bleeding lakhs of rupees to overlapping funds and high expense ratios simply because their CAMS/KFintech statements are too dense to read. 

**ArthaScan** solves this by converting static, messy PDFs into actionable, undeniable financial truths in seconds—all through a frictionless Telegram interface. 

---

## 🔥 Key Features (Why this isn't just an LLM Wrapper)

1. **Multimodal "Vision-First" Extraction Pipeline:** Standard PyPDF crawlers break on financial tables. We rasterize the PDF into high-res images and pass them to **Gemini 2.5 Flash** with a strict `Pydantic`-validated schema. If the LLM breaks, a self-healing retry loop and regex parser catch it.
2. **Deterministic Mathematical Engine:** LLMs hallucinate numbers. We don't allow them to do math. A strict Python algorithms engine calculates the true **XIRR (via XNPV)**, 10-year Wealth Bleed, and exactly normalizes stock exposure to reveal hidden overlaps.
3. **0-100 Portfolio Health Score:** A custom algorithmic gauge that deducts penalties for closet indexing and high fee drag, giving users instant visual feedback on their portfolio's health.
4. **"Glass-Box" Conversational Guard:** Users can freely chat with the bot to ask questions (e.g., *"Why is this fund bad?"*). An intent router intercepts the chat, prevents illegal financial advice/hallucinations, and uses Gemini to explain the deterministic calculations clearly in English or Hinglish.
5. **In-Memory Caching:** Explanatory LLM queries are hash-cached in-memory for 0ms latency responses upon repeat clicks.
6. **Dynamic PDF Reporting:** Uses `ReportLab` to instantly generate and send a formatted PDF, complete with a Fund-by-Fund Action Breakdown table.

---

## 🏗️ Architecture Flow

`PDF Upload -> PyMuPDF Image Rasterization -> Gemini Vision Extraction -> Deterministic Finance Engine -> Decision Rules Engine -> Guarded AI Routing -> Telegram Bot Delivery`

## ⚙️ Local Setup

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

4. Run the application:
```bash
python main.py
```

## 🧪 Demo Modes

The system is built to never crash live. If extraction times out (due to API rate limits), the system gracefully downgrades to a deterministic demo environment:
- **XIRR:** `11.2`
- **Overlap:** `65%`
- **Expense ratio:** `1.5%`
- **Wealth bleed (10 yrs):** `₹3,20,000`
