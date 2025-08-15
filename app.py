# -*- coding: utf-8 -*-
import os, json, time, logging, re
from pathlib import Path
from flask import Flask, request, abort
from dotenv import load_dotenv
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage, JoinEvent
from langdetect import detect, DetectorFactory

# ── 基本設定 ──────────────────────────────────────────
load_dotenv()
DetectorFactory.seed = 0

CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")
CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
DEFAULT_TARGET = os.getenv("DEFAULT_TARGET", "zh-TW")
FANOUT_MODE = os.getenv("FANOUT_MODE", "group")  # 預設群組翻譯
TARGETS = ["zh-TW", "en", "th"]                  # 繁中 / 英文 / 泰文
DEBUG_FLAG = os.getenv("DEBUG", "1") == "1"

if not CHANNEL_SECRET or not CHANNEL_ACCESS_TOKEN:
    raise RuntimeError("請在 .env 設定 LINE_CHANNEL_SECRET / LINE_CHANNEL_ACCESS_TOKEN")

app = Flask(__name__)
line_bot_api = LineBotApi(CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(CHANNEL_SECRET)

# 偏好語言儲存（支援以環境變數 PREF_PATH 指定雲端磁碟掛載路徑）
PREF_PATH = Path(os.getenv("PREF_PATH", "user_langs.json"))
if not PREF_PATH.exists():
    PREF_PATH.write_text("{}", encoding="utf-8")

def load_prefs():
    try:
        return json.loads(PREF_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}

def save_prefs(prefs):
    PREF_PATH.write_text(json.dumps(prefs, ensure_ascii=False, indent=2), encoding="utf-8")

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger("translator-bot")

HELP_TEXT = (
    "指令：\n"
    "/lang <code>  設定你的偏好語言（例：/lang en、/lang zh-TW、/lang th）\n"
    "/mylang       查看你的設定\n"
    "/help         顯示此說明\n"
    f"目前群組模式：{FANOUT_MODE}；群組翻譯語言：{', '.join(TARGETS)}"
)

def normalize_lang(code: str) -> str:
    if not code:
        return DEFAULT_TARGET
    c = code.strip().lower()
    alias = {
        "zh": "zh-TW", "zh-tw": "zh-TW", "zh-hant": "zh-TW", "zh-hans": "zh-CN",
        "en-us": "en", "en-gb": "en",
        "jp": "ja",
        "th-th": "th", "thai": "th", "泰文": "th", "英文": "en", "繁中": "zh-TW",
    }
    return alias.get(c, code)

def safe_detect(text: str) -> str:
    t = (text or "").strip()
    # 不要用 \W 過濾，否則中/日/韓/泰 全會被當作非字元而長度為 0
    if len(t) < 2:
        return "auto"
    if re.search(r"https?://|www\.", t):
        return "auto"
    try:
        return detect(t)
    except Exception:
        return "auto"

# 語言判斷輔助
def is_chinese_lang(code: str) -> bool:
    c = (code or "").lower()
    return c.startswith("zh")

def is_thai_lang(code: str) -> bool:
    c = (code or "").lower()
    return c.startswith("th")

# 依文字內容粗略判斷是否像中文/泰文（避免偵測器失敗時退回 auto 導致私聊回中文）
def looks_like_chinese(text: str) -> bool:
    if not text:
        return False
    return re.search(r"[\u4e00-\u9fff]", text) is not None

def looks_like_thai(text: str) -> bool:
    if not text:
        return False
    return re.search(r"[\u0E00-\u0E7F]", text) is not None

# 翻譯函式
from translator import translate
def translate_with_retry(text: str, target: str, src: str = "auto", retries: int = 3, wait: float = 0.8) -> str:
    last_err = None
    for i in range(retries + 1):
        try:
            return translate(text, target_lang=target, src_lang=src or "auto")
        except Exception as e:
            last_err = e
            log.warning(f"translate fail({i+1}/{retries+1}) target={target} err={e}")
            time.sleep(wait)
    raise last_err

def robust_translate(text: str, target: str, src_primary: str) -> str:
    """先用指定源語言翻，若輸出為空或與原文相同，改用 auto 再試。"""
    try:
        first = translate_with_retry(text, target=target, src=src_primary)
        if not first or first.strip() == text.strip():
            # 回退使用 auto 再試一次
            second = translate_with_retry(text, target=target, src="auto")
            return second
        return first
    except Exception:
        # 若主流程錯誤，再以 auto 試一次
        return translate_with_retry(text, target=target, src="auto")

@app.get("/")
def health():
    return "ok", 200

@app.get("/health")
def health_probe():
    return "ok", 200

@app.post("/callback")
def callback():
    signature = request.headers.get("X-Line-Signature", "")
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return "OK"

@handler.add(JoinEvent)
def handle_join(event):
    welcome = (
        "大家好，我是翻譯助手！\n"
        "用 `/lang <code>` 設定你的偏好語言，例如：/lang en /lang zh-TW /lang th。\n"
        f"目前群組翻譯語言：{', '.join(TARGETS)}"
    )
    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=welcome))

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    text = (event.message.text or "").strip()
    user_id = getattr(event.source, "user_id", None)
    source_type = event.source.type

    prefs = load_prefs()
    if user_id and user_id not in prefs:
        prefs[user_id] = {"target": DEFAULT_TARGET}
        save_prefs(prefs)

    low = text.lower()
    if low.startswith("/help"):
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=HELP_TEXT))
        return

    if low.startswith("/mylang"):
        target = prefs.get(user_id, {}).get("target", DEFAULT_TARGET)
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"你的偏好：{target}"))
        return

    if low.startswith("/lang"):
        parts = text.split(maxsplit=1)
        if len(parts) == 2:
            code = normalize_lang(parts[1])
            prefs[user_id] = {"target": code}
            save_prefs(prefs)
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"OK！你的偏好語言改為：{code}"))
        else:
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="用法：/lang <code> 例如 /lang en"))
        return

    if not text:
        return

    src = safe_detect(text)
    if DEBUG_FLAG:
        log.info(f"recv type={source_type} src={src} text='{text[:40]}'...")

    # 群組翻譯模式
    if source_type in ("group", "room"):
        out_lines = [f"[原文 {src}] {text}"]

        # 先以內容特徵輔助判斷，避免偵測失敗時為 auto
        src_like_cn = looks_like_chinese(text)
        src_like_th = looks_like_thai(text)
        src_effective = src
        if src_like_cn:
            src_effective = "zh-TW"
        elif src_like_th:
            src_effective = "th"

        # 自訂目標：
        # - 中文輸入：只回覆英文、泰文
        # - 泰文輸入：只回覆英文、中文
        # - 其他語言：維持原本邏輯（翻譯到 TARGETS，排除來源語系與同屬中文族群）
        if is_chinese_lang(src) or src_like_cn:
            target_list = ["en", "th"]
        elif is_thai_lang(src) or src_like_th:
            target_list = ["en", "zh-TW"]
        else:
            target_list = []
            for tgt in TARGETS:
                if tgt.lower().startswith(src.lower()):
                    continue
                # 若來源與目標皆為中文族群，視為同語系而跳過
                if is_chinese_lang(src) and tgt.lower().startswith("zh"):
                    continue
                target_list.append(tgt)

        for tgt in target_list:
            try:
                tr = robust_translate(text, target=tgt, src_primary=src_effective)
                out_lines.append(f"[{tgt}] {tr}")
            except Exception as e:
                out_lines.append(f"[{tgt}] <翻譯失敗: {e}>")
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="\n".join(out_lines)))
        return

    # 私聊模式
    if source_type == "user":
        # 先以內容特徵輔助判斷，避免偵測器回 auto 導致回到中文
        src_like_cn = looks_like_chinese(text)
        src_like_th = looks_like_thai(text)
        src_effective = src
        if src_like_cn:
            src_effective = "zh-TW"
        elif src_like_th:
            src_effective = "th"

        # 中文→回覆 英文+泰文；泰文→回覆 英文+中文；其他→沿用使用者偏好
        if is_chinese_lang(src) or src_like_cn:
            target_list = ["en", "th"]
        elif is_thai_lang(src) or src_like_th:
            target_list = ["en", "zh-TW"]
        else:
            target_list = [prefs.get(user_id, {}).get("target", DEFAULT_TARGET)]

        out_lines = []
        for tgt in target_list:
            try:
                tr = robust_translate(text, target=tgt, src_primary=src_effective)
                out_lines.append(f"[{tgt}] {tr}")
            except Exception as e:
                out_lines.append(f"[{tgt}] <翻譯失敗: {e}>")
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="\n".join(out_lines)))

if __name__ == "__main__":
    log.info(f"FANOUT_MODE={FANOUT_MODE} TARGETS={TARGETS}")
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
