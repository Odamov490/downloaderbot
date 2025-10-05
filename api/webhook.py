import re

YOUTUBE_ID_RE = re.compile(r'(?:v=|/shorts/|youtu\.be/)([A-Za-z0-9_-]{11})')

INVIDIOUS_HOSTS = [
    "yewtu.be",           # eng barqarorlaridan biri
    "vid.puffyan.us",
    "invidious.snopyta.org",
]
PIPED_HOSTS = [
    "piped.video",        # Piped ham ko‘pincha yaxshi ishlaydi
    "piped.video-proxy.lunar.icu"
]

def _try_ydl(url, yfmt, cookiefile=None, client=None):
    opts = _base_ydl_opts(yfmt, cookiefile)
    if client:
        opts.setdefault("extractor_args", {}).setdefault("youtube", {})["player_client"] = client
    with YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=False)
        title = info.get("title") or "video"
        direct = info.get("url")
        if not direct:
            for f in reversed(info.get("formats") or []):
                if f.get("url"):
                    direct = f["url"]; break
    return direct, title

def extract_direct_url(src_url: str, quality: str = "best", audio_only: bool = False):
    # format tanlash
    if audio_only:
        yfmt = "bestaudio/best"
    else:
        yfmt = {"720": "bestvideo[height<=720]+bestaudio/best[height<=720]/best",
                "360": "bestvideo[height<=360]+bestaudio/best[height<=360]/best"}.get(quality, "best[ext=mp4]/best")

    # 1) Asl URL (YouTube bo‘lsa bir necha client bilan)
    is_yt = "youtube.com" in src_url or "youtu.be" in src_url
    last_err = None
    if is_yt:
        for client in [["android"], ["web"], ["ios"], ["mweb"]]:
            try:
                d, t = _try_ydl(src_url, yfmt, cookiefile=None, client=client)
                if d: return d, t
            except Exception as e:
                last_err = e
                print("yt try failed", client, e)
    else:
        try:
            return _try_ydl(src_url, yfmt, cookiefile=None)
        except Exception as e:
            last_err = e
            print("extract error", e)

    # 2) Fallback — Invidious
    if is_yt:
        m = YOUTUBE_ID_RE.search(src_url)
        vid = m.group(1) if m else None
        if vid:
            for host in INVIDIOUS_HOSTS:
                inv_url = f"https://{host}/watch?v={vid}"
                try:
                    d, t = _try_ydl(inv_url, yfmt, cookiefile=None)
                    if d: return d, t
                except Exception as e:
                    print("invidious failed", host, e)

            # 3) Fallback — Piped
            for host in PIPED_HOSTS:
                piped_url = f"https://{host}/watch?v={vid}"
                try:
                    d, t = _try_ydl(piped_url, yfmt, cookiefile=None)
                    if d: return d, t
                except Exception as e:
                    print("piped failed", host, e)

    # Agar hech biri bo‘lmadi:
    if last_err:
        raise last_err
    raise Exception("Direct URL topilmadi (prob: login/region/age limit)")
