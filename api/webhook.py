
from http.server import BaseHTTPRequestHandler
import os, json, re
from urllib import request as urlrequest
from yt_dlp import YoutubeDL

BOT_TOKEN = os.getenv("BOT_TOKEN")
TG_API = f"https://api.telegram.org/bot{BOT_TOKEN}" if BOT_TOKEN else None
URL_RE = re.compile(r"https?://\S+")

def _post_json(url: str, payload: dict):
    data = json.dumps(payload).encode("utf-8")
    req = urlrequest.Request(url, data=data, headers={"Content-Type": "application/json"})
    with urlrequest.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode("utf-8"))

def send_message(chat_id, text):
    if not TG_API:
        return
    try:
        _post_json(f"{TG_API}/sendMessage", {"chat_id": chat_id, "text": text})
    except Exception as e:
        print("send_message error:", e)

def send_video_by_url(chat_id, video_url, caption=""):
    if not TG_API:
        return {"ok": False, "error": "no token"}
    try:
        return _post_json(f"{TG_API}/sendVideo", {"chat_id": chat_id, "video": video_url, "caption": caption})
    except Exception as e:
        print("send_video_by_url error:", e)
        return {"ok": False, "error": str(e)}

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            ln = int(self.headers.get("content-length", "0"))
            body = self.rfile.read(ln) if ln > 0 else b"{}"
            update = json.loads(body.decode("utf-8"))
        except Exception as e:
            self.send_response(200); self.end_headers(); return

        msg = update.get("message") or update.get("edited_message") or {}
        chat = msg.get("chat") or {}
        chat_id = chat.get("id")
        text = msg.get("text") or msg.get("caption") or ""

        # Respond fast
        self.send_response(200)
        self.end_headers()

        if not BOT_TOKEN or not chat_id:
            return

        m = URL_RE.search(text or "")
        if not m:
            send_message(chat_id, "🎯 Menga video link yuboring (public post/reel/shorts).")
            return

        url = m.group(0)
        send_message(chat_id, "⏬ Link qabul qilindi, tayyorlayapman…")

        # Extract direct media URL without downloading
        ydl_opts = {
            "quiet": True, "noprogress": True,
            "skip_download": True, "noplaylist": True,
            "format": "best[ext=mp4]/best",
        }
        direct_url, title = None, "video"
        try:
            with YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                title = info.get("title") or title
                direct_url = info.get("url")
                if not direct_url:
                    fmts = info.get("formats") or []
                    for f in reversed(fmts):
                        if f.get("url"):
                            direct_url = f["url"]; break
        except Exception as e:
            print("yt-dlp extract error:", e)
            send_message(chat_id, f"❌ Yuklab bo‘lmadi: {e}")
            return

        if not direct_url:
            send_message(chat_id, "❌ To‘g‘ridan-to‘g‘ri video URL topilmadi.")
            return

        r = send_video_by_url(chat_id, direct_url, caption=title)
        if not (isinstance(r, dict) and r.get("ok")):
            try:
                _post_json(f"{TG_API}/sendDocument", {"chat_id": chat_id, "document": direct_url, "caption": title})
            except Exception as e:
                print("sendDocument fallback error:", e)
                send_message(chat_id, "❌ Telegram video URL ni qabul qilmadi (ehtimol katta yoki yopiq post).")
