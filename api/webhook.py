from http.server import BaseHTTPRequestHandler
import os, json, re, tempfile, base64
from urllib import request as urlrequest
from yt_dlp import YoutubeDL

BOT_TOKEN = os.getenv("BOT_TOKEN")
TG_API = f"https://api.telegram.org/bot{BOT_TOKEN}" if BOT_TOKEN else None

URL_RE = re.compile(r"https?://\S+")
YOUTUBE_ID_RE = re.compile(r"(?:v=|/shorts/|youtu\.be/)([A-Za-z0-9_-]{11})")

INVIDIOUS_HOSTS = ["yewtu.be", "vid.puffyan.us", "invidious.snopyta.org"]
PIPED_HOSTS = ["piped.video", "piped.video-proxy.lunar.icu"]

# optional: base64-langan Netscape cookies.txt
COOKIES_B64 = os.getenv("YTDLP_COOKIES_B64")

def _tg_post(method: str, payload: dict):
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urlrequest.Request(f"{TG_API}/{method}", data=data,
                             headers={"Content-Type": "application/json; charset=utf-8"})
    with urlrequest.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode("utf-8"))

def send_text(chat_id, text):
    if TG_API:
        try: _tg_post("sendMessage", {"chat_id": chat_id, "text": text})
        except Exception as e: print("send_text error:", e)

def send_video_url(chat_id, url, caption=""):
    try: return _tg_post("sendVideo", {"chat_id": chat_id, "video": url, "caption": caption})
    except Exception as e: print("send_video_url error:", e); return {"ok": False}

def send_audio_url(chat_id, url, caption=""):
    try: return _tg_post("sendAudio", {"chat_id": chat_id, "audio": url, "caption": caption})
    except Exception as e: print("send_audio_url error:", e); return {"ok": False}

def send_document_url(chat_id, url, caption=""):
    try: return _tg_post("sendDocument", {"chat_id": chat_id, "document": url, "caption": caption})
    except Exception as e: print("send_document_url error:", e); return {"ok": False}

def parse_mode(text: str):
    t = (text or "").lower()
    if "audio" in t or "/audio" in t: return ("audio", None)
    if "720" in t or "/video720" in t or "/v720" in t: return ("video", "720")
    if "360" in t or "/video360" in t or "/v360" in t: return ("video", "360")
    return ("video", "best")

HELP_TEXT = (
    "👋 *Video Downloader bot*\n\n"
    "Menga *public* video havolasini yuboring.\n"
    "🎛 Rejimlar: `720`, `360`, `audio` (yoki /video720, /video360, /audio)\n"
    "Masalan: `https://youtu.be/... 720`"
)

def _base_ydl_opts(fmt: str, cookiefile: str | None):
    opts = {
        "quiet": True, "noprogress": True,
        "skip_download": True, "noplaylist": True,
        "format": fmt, "extractor_retries": 2,
        "http_headers": {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9"
        },
        "geo_bypass": True
    }
    if cookiefile: opts["cookiefile"] = cookiefile
    return opts

def _cookies_file_or_none():
    if not COOKIES_B64: return None
    try:
        raw = base64.b64decode(COOKIES_B64)
        tf = tempfile.NamedTemporaryFile(delete=False)
        tf.write(raw); tf.flush(); tf.close()
        return tf.name
    except Exception as e:
        print("cookies decode error:", e)
        return None

def _try_with_ydl(url: str, yfmt: str, cookiefile: str | None, client: list | None = None):
    opts = _base_ydl_opts(yfmt, cookiefile)
    if client:
        opts.setdefault("extractor_args", {}).setdefault("youtube", {})["player_client"] = client
    with YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=False)
        title = info.get("title") or "video"
        direct = info.get("url")
        if not direct:
            for f in reversed(info.get("formats") or []):
                if f.get("url"): direct = f["url"]; break
    return direct, title

def extract_direct_url(src_url: str, quality: str = "best", audio_only: bool = False):
    if audio_only:
        yfmt = "bestaudio/best"
    else:
        yfmt = {"720":"bestvideo[height<=720]+bestaudio/best[height<=720]/best",
                "360":"bestvideo[height<=360]+bestaudio/best[height<=360]/best"}.get(quality, "best[ext=mp4]/best")

    is_yt = ("youtube.com" in src_url) or ("youtu.be" in src_url)
    cookiefile = _cookies_file_or_none()  # bo‘lsa ishlatamiz
    last_err = None

    if is_yt:
        # 1) YouTube o‘zi (multi client)
        for client in [["android"], ["web"], ["ios"], ["mweb"]]:
            try:
                d, t = _try_with_ydl(src_url, yfmt, cookiefile, client=client)
                if d: return d, t
            except Exception as e:
                last_err = e; print("yt try failed", client, e)
    else:
        try:
            return _try_with_ydl(src_url, yfmt, cookiefile)
        except Exception as e:
            last_err = e; print("extract error", e)

    # 2) Invidious
    if is_yt:
        m = YOUTUBE_ID_RE.search(src_url); vid = m.group(1) if m else None
        if vid:
            for host in INVIDIOUS_HOSTS:
                try:
                    d, t = _try_with_ydl(f"https://{host}/watch?v={vid}", yfmt, cookiefile=None)
                    if d: return d, t
                except Exception as e:
                    print("invidious failed", host, e)
            # 3) Piped
            for host in PIPED_HOSTS:
                try:
                    d, t = _try_with_ydl(f"https://{host}/watch?v={vid}", yfmt, cookiefile=None)
                    if d: return d, t
                except Exception as e:
                    print("piped failed", host, e)

    if last_err: raise last_err
    raise Exception("Direct URL topilmadi (login/region/age limit?)")

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            ln = int(self.headers.get("content-length", "0"))
            body = self.rfile.read(ln) if ln>0 else b"{}"
            update = json.loads(body.decode("utf-8"))
        except Exception:
            self.send_response(200); self.end_headers(); return

        self.send_response(200); self.end_headers()

        if not BOT_TOKEN:
            print("ERROR: BOT_TOKEN yo‘q."); return

        msg = update.get("message") or update.get("edited_message") or {}
        chat_id = (msg.get("chat") or {}).get("id")
        text = msg.get("text") or msg.get("caption") or ""
        if not chat_id: return

        if text.startswith("/start"): send_text(chat_id, "Salom!\n\n"+HELP_TEXT); return
        if text.startswith("/help"):  send_text(chat_id, HELP_TEXT); return
        if text.startswith("/about"): send_text(chat_id, "Vercel webhook + yt-dlp (URL orqali)."); return

        m = URL_RE.search(text or "")
        if not m:
            send_text(chat_id, "🎯 Havola yuboring.\n\n"+HELP_TEXT); return

        src_url = m.group(0)
        mode, q = parse_mode(text)
        send_text(chat_id, "⏬ Link qabul qilindi, tayyorlayapman…")

        try:
            if mode == "audio":
                direct, title = extract_direct_url(src_url, audio_only=True)
                if not direct: send_text(chat_id, "❌ Audio URL topilmadi."); return
                r = send_audio_url(chat_id, direct, caption=title)
                if not (isinstance(r, dict) and r.get("ok")): send_document_url(chat_id, direct, caption=title)
            else:
                direct, title = extract_direct_url(src_url, quality=q or "best", audio_only=False)
                if not direct: send_text(chat_id, "❌ Video URL topilmadi."); return
                r = send_video_url(chat_id, direct, caption=title)
                if not (isinstance(r, dict) and r.get("ok")): send_document_url(chat_id, direct, caption=title)
        except Exception as e:
            print("Process error:", e)
            send_text(chat_id, "❌ Yuklab bo‘lmadi.\nIltimos, boshqa PUBLIC link yuboring yoki keyinroq urinib ko‘ring.")
