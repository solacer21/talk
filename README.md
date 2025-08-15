# LINE 雙向翻譯聊天室（免金鑰個人測試版）
支援語言：繁中（zh-TW）、英文（en）、日文（ja）、泰文（th）  
翻譯：`deep-translator` 的 Google 翻譯（免金鑰，適合個人測試）  
包含 **自動設定 Webhook**（透過 ngrok 抓 HTTPS URL 並設定到 LINE）。

## 快速開始（Windows）
1. 到 LINE Developers 建立 Messaging API Channel，開啟「允許被加入群組」。抄下：
   - Channel access token
   - Channel secret
2. 下載並安裝 [ngrok](https://ngrok.com/)，或把 `ngrok.exe` 放在此資料夾。
3. 複製 `.env.example` → 重新命名為 `.env`，填入：
   ```env
   LINE_CHANNEL_ACCESS_TOKEN=你的token
   LINE_CHANNEL_SECRET=你的secret
   DEFAULT_TARGET=zh-TW
   TRANSLATOR_PROVIDER=google
   ```
4. **雙擊 `start.bat`**：
   - 建立 venv、安裝依賴
   - 啟動 `ngrok http 5000`（含本地 API: http://127.0.0.1:4040）
   - 自動抓 ngrok **https** URL 並設定到 LINE Webhook（/callback）
   - 啟動 Flask 伺服器（http://127.0.0.1:5000）

## 使用方式
- 把 Bot 加入**群組**。
- 任一成員發言，Bot 會自動偵測語言，並在群組貼出翻譯為：`zh-TW`、`en`、`ja`、`th`（會跳過與原文相同語言）。
- 也支援個人偏好語言：
  - `/lang <code>` 設定你的偏好（如 `/lang en`）
  - `/mylang` 查看設定
  - `/help` 查看說明

> 註：個別推播（push）需對方與 Bot 成為好友。本專案為了簡單測試，主要在群組中直接貼出多語翻譯。

## 重要檔案
- `app.py`：Flask + LINE Webhook 主程式
- `translator.py`：翻譯封裝，可切換 `google`（預設）、`azure`、`libre`
- `update_webhook.py`：從 ngrok 取 HTTPS URL，呼叫 LINE API 設定 Webhook
- `start.bat`：Windows 一鍵啟動（venv、ngrok、設定 Webhook、啟動 Flask）

## 可能問題
- **Webhook 驗證失敗**：請確認 ngrok 已有 `https` 通道，且 `update_webhook.py` 已寫入 `/callback`。
- **deep-translator 被限流**：屬正常現象（非官方 API）。想穩定請改 `TRANSLATOR_PROVIDER=azure` 並填金鑰。
- **LINE 後台要開什麼？** 務必開啟「允許被加入群組」與接收群組訊息。
