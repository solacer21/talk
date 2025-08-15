import os, requests
from typing import Optional
from deep_translator import GoogleTranslator

# 正規化語言碼（部分常見別名）
_ALIAS = {
    "zh": "zh-TW",
    "zh-tw": "zh-TW",
    "zh_hant": "zh-TW",
    "zh-hant": "zh-TW",
    "zh_cn": "zh-CN",
    "zh-cn": "zh-CN",
    "zh-hans": "zh-CN",
    "en-us": "en",
    "en-gb": "en",
    "jp": "ja",
    # deep_translator 使用 'iw' 代表希伯来文
    "he": "iw",
}

def normalize_lang(code: str) -> str:
    if not code:
        return "zh-TW"
    c = code.strip()
    lc = c.lower().replace(" ", "").replace("-", "-")
    key = lc.replace("_", "-")
    # 统一 key（支持 zh_hant/zh-hant、zh_cn/zh-cn 等）
    key = key.replace("zh_hant", "zh-hant").replace("zh_cn", "zh-cn")
    return _ALIAS.get(key, c)

def translate(text: str, target_lang: str, src_lang: Optional[str] = "auto") -> str:
    provider = (os.getenv("TRANSLATOR_PROVIDER") or "google").lower()
    target_lang = normalize_lang(target_lang)
    source_lang = src_lang or "auto"
    if source_lang and source_lang.lower() != "auto":
        source_lang = normalize_lang(source_lang)
    else:
        source_lang = "auto"

    if provider == "google":
        return GoogleTranslator(source=source_lang, target=target_lang).translate(text)

    if provider == "azure":
        key = os.getenv("AZURE_TRANSLATOR_KEY")
        region = os.getenv("AZURE_TRANSLATOR_REGION")
        endpoint = "https://api.cognitive.microsofttranslator.com/translate"
        params = {"api-version": "3.0", "to": [target_lang]}
        headers = {
            "Ocp-Apim-Subscription-Key": key,
            "Ocp-Apim-Subscription-Region": region,
            "Content-type": "application/json"
        }
        body = [{"text": text}]
        r = requests.post(endpoint, params=params, headers=headers, json=body, timeout=30)
        r.raise_for_status()
        j = r.json()
        return j[0]["translations"][0]["text"]

    if provider == "libre":
        base = os.getenv("LIBRE_BASE_URL", "http://localhost:5000")
        r = requests.post(
            f"{base}/translate",
            json={"q": text, "source": source_lang, "target": target_lang},
            timeout=30,
        )
        r.raise_for_status()
        j = r.json()
        return j.get("translatedText") or j.get("translated_text") or ""

    # 預設 fallback
    return GoogleTranslator(source=src_lang or "auto", target=target_lang).translate(text)
