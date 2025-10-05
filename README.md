
# Telegram Downloader Webhook (Vercel)

Uses `yt-dlp` to extract a **direct media URL** (no download on Vercel) and tells Telegram to fetch it by URL.

## Deploy
1. Push this folder to GitHub.
2. Create a Vercel project from the repo.
3. Settings → Environment Variables:
   - `BOT_TOKEN` = your bot token
4. Deploy, then set webhook:
   ```
   https://api.telegram.org/bot<YOUR_BOT_TOKEN>/setWebhook?url=https://<YOUR_VERCEL_DOMAIN>/api/webhook
   ```
Send a public video link to your bot to test.

> Note: Private/login-only links or very large media may fail. For heavy usage, consider Vercel (webhook) + a worker (Railway/Fly).
