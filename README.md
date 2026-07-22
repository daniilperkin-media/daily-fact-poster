# 💡 Daily Fact Poster

An automated pipeline that generates 1 interesting visual fact card + caption every day using **Google Gemini 2.5 Flash** and AI image generation, hosting the graphic on AWS S3 and publishing it across **Threads, Telegram, Instagram, and X** via a **Make.com Free Webhook**.

---

## ✨ Features

- **🧠 Gemini 2.5 Flash**: Automatically selects unique, non-repeating facts and formats engaging captions with hashtags.
- **🎨 AI Image Generation**: Generates 3D thematic artwork via Pollinations.ai API.
- **🖼️ PIL Graphic Card Builder**: Overlays dark gradients, typography, titles, and custom watermarks onto a 1080x1080 social media graphic card.
- **☁️ S3 Hosting**: Uploads rendered graphic cards to AWS S3 to generate public HTTPS URLs.
- **🌐 Make.com Webhook Posting**: Sends a single JSON payload to Make.com, which routes posts to Threads, Instagram, Telegram, and Twitter/X for free.
- **🤖 GitHub Actions Scheduling**: Runs automatically on a daily cloud cron schedule (`0 9 * * *`).

---

## 🛠️ Quick Start

### 1. Install Dependencies
```bash
cd Daily_Fact_Poster
pip install -r requirements.txt
cp .env.example .env  # Edit .env with your keys
```

### 2. Run Dry Run (Local Test)
```bash
python main.py --dry-run
```
This generates the fact, AI artwork, builds `output/daily_fact_card.png`, and logs the payload without sending live posts.

### 3. Production Run
```bash
python main.py
```

---

## 🔗 Setting Up Make.com Free Webhook

1. Sign up for a free account at [Make.com](https://www.make.com/).
2. Create a new Scenario with a **Custom Webhook** trigger module.
3. Copy the Webhook URL into your `.env` file as `MAKE_WEBHOOK_URL`.
4. Connect social media action modules (Threads, Telegram Channel Bot, Instagram for Business, Twitter) to the Webhook module.
5. Map `1.caption` and `1.image_url` to your social media posts!
