from http.server import BaseHTTPRequestHandler
import os, json, re
from urllib import request as urlrequest
from yt_dlp import YoutubeDL

# === Environment ===
BOT_TOKEN = os.getenv("BOT_TOKEN")
TG_API = f"https://api.telegram.org/bot{BOT_TOKEN}" if BOT_TOKEN else None

# === Kiritilgan matndan URL izlash ===
URL_RE = re.compile(r"https?://\S+")

# === Telegram helperlari ===
def tg_post(method: str, payload: dict):
    """POST JSON to Telegram Bot API."""
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urlrequest.Request(
        f"{TG_API}/{method}",
        data=data,
        headers={"Content-Type": "application/json; charset=utf-8"},
    )
    with urlrequest.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode("utf-8"))

def send_text(chat_id: int, text: str):
    if TG_API:
        try:
            tg_post("sendMessage", {"chat_id": chat_id, "text": text})
        except Exception as e:
            print("send_text error:", e)

def send_video_by_url(chat_id: int, url: str, caption: str = ""):
    try:
        return tg_post("sendVideo", {"chat_id": chat_id, "video": url, "caption": caption})
    except Exception as e:
        print("send_video_by_url error:", e)
        return {"ok": False, "error": str(e)}

def send_audio_by_url(chat_id: int, url: str, caption: str = ""):
    try:
        return tg_post("sendAudio", {"chat_id": chat_id, "audio": url, "caption": caption})
    except Exception as e:
        print("send_audio_by_url error:", e)
        return {"ok": False, "error": str(e)}

def send_document_by_url(chat_id: int, url: str, caption: str = ""):
    try:
        return tg_post("sendDocument", {"chat_id": chat_id, "document": url, "caption": caption})
    except Exception as e:
        print("send_document_by_url error:", e)
        return {"ok": False, "error": str(e)}

# === yt-dlp orqali to‘g‘ridan-to‘g‘ri media URL chiqarish (download=False) ===
def extract_direct_url(src_url: str, quality: str = "best", audio_only: bool = False):
    """
    quality: 'best' | '720' | '360'
    audio_only: True bo‘lsa faqat audio URL qaytaradi
    """
    if audio_only:
        ydl_format = "bestaudio/best"
    else:
        if quality == "720":
            ydl_format = "bestvideo[height<=720]+bestaudio/best[height<=720]/best"
        elif quality == "360":
            ydl_format = "bestvideo[height<=360]+bestaudio/best[height<=360]/best"
        else:
            ydl_format = "best[ext=mp4]/best"

    opts = {
        "quiet": True,
        "noprogress": True,
        "skip_download": True,
        "noplaylist": True,
        "format": ydl_format,
    }

    with YoutubeDL(opts) as ydl:
        info = ydl.extract_info(src_url, download=False)
        title = info.get("title") or "video"
        # Ba’zi saytlarda tanlangan format info["url"] da bo‘ladi
        direct = info.get("url")
        if not direct:
            for f in reversed(info.get("formats") or []):
                if f.get("url"):
                    direct = f["url"]
                    break
    return direct, title

# === Foydalanuvchi buyruqlarini tushunish ===
def parse_mode(text: str):
    """
    Matndan sifat/audio rejimini aniqlaydi.
    Misollar:
      "https://... 720" -> ("video", "720")
      "https://... audio" -> ("audio", None)
      "/video360 https://..." -> ("video", "360")
    """
    t = (text or "").lower()
    if "audio" in t or "/audio" in t:
        return ("audio", None)
    if "720" in t or "/video720" in t or "/v720" in t:
        return ("video", "720")
    if "360" in t or "/video360" in t or "/v360" in t:
        return ("video", "360")
    # default
    return ("video", "best")

HELP_TEXT = (
    "👋 *Video Downloader bot*\n\n"
    "Menga *public* video havolasini yuboring.\n"
    "✅ Standart: eng yaxshi sifatdagi video yuboriladi.\n\n"
    "🎛 *Rejimlar:*\n"
    "• Video 720p: havoladan keyin `720` yozing yoki /video720\n"
    "• Video 360p: havoladan keyin `360` yozing yoki /video360\n"
    "• Faqat audio: havoladan keyin `audio` yozing yoki /audio\n\n"
    "Misollar:\n"
    "`https://youtu.be/... 720`\n"
    "`https://tiktok.com/... audio`\n"
    "`/video360 https://instagram.com/reel/...`\n\n"
    "_Eslatma: private/login talab qiladigan linklar ishlamaydi._"
)

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        # Vercel uchun tezda 200 qaytaramiz (serverless requestni bloklamaslik uchun)
        try:
            length = int(self.headers.get("content-length", "0"))
            body = self.rfile.read(length) if length > 0 else b"{}"
            update = json.loads(body.decode("utf-8"))
        except Exception:
            self.send_response(200); self.end_headers(); return

        # Javobni darhol yopamiz
        self.send_response(200)
        self.end_headers()

        if not BOT_TOKEN:
            print("ERROR: BOT_TOKEN env yo‘q.")
            return

        msg = update.get("message") or update.get("edited_message") or {}
        chat_id = (msg.get("chat") or {}).get("id")
        text = msg.get("text") or msg.get("caption") or ""

        if not chat_id:
            return

        # Slash komandalar
        if text.startswith("/start"):
            send_text(chat_id, "Salom! 🖐️ Menga video havolasini yuboring.\n\n" + HELP_TEXT)
            return
        if text.startswith("/help"):
            send_text(chat_id, HELP_TEXT)
            return
        if text.startswith("/about"):
            send_text(chat_id, "Bot: Vercel webhook + yt-dlp (URL orqali jo‘natish). Muallif: siz 😎")
            return

        # Link qidiramiz
        m = URL_RE.search(text)
        if not m:
            # Foydalanuvchiga yo‘l-yo‘riq
            send_text(chat_id, "🎯 Havola yuboring.\n\n" + HELP_TEXT)
            return

        src_url = m.group(0)
        mode, q = parse_mode(text)

        send_text(chat_id, "⏬ Link qabul qilindi, tayyorlayapman…")

        try:
            if mode == "audio":
                direct, title = extract_direct_url(src_url, audio_only=True)
                if not direct:
                    send_text(chat_id, "❌ Audio URL topilmadi.")
                    return
                r = send_audio_by_url(chat_id, direct, caption=title)
                if not (isinstance(r, dict) and r.get("ok")):
                    send_document_by_url(chat_id, direct, caption=title)
            else:
                direct, title = extract_direct_url(src_url, quality=q or "best", audio_only=False)
                if not direct:
                    send_text(chat_id, "❌ Video URL topilmadi.")
                    return
                r = send_video_by_url(chat_id, direct, caption=title)
                if not (isinstance(r, dict) and r.get("ok")):
                    # Ba’zi hollarda Telegram video URL’ni rad etadi — hujjat sifatida urinib ko‘ramiz
                    send_document_by_url(chat_id, direct, caption=title)

        except Exception as e:
            print("Process error:", e)
            send_text(chat_id, f"❌ Yuklab bo‘lmadi: {e}")
