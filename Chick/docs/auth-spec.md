![alt text](image.png)

身分與登入規格（Guest → Account 升級）

本文件定義：環境變數、資料表欄位、Token 政策、Rotation 規則、限流策略、安全決策、端點介面、測試用例。

1. 名詞與目標

角色：

Guest 使用者：未綁定 Email/第三方，僅與裝置綁定。

Active 使用者：已綁定 Email/第三方，可跨裝置登入。

目標：提供「先玩再綁定」體驗，並確保 Token 安全、可撤銷、可稽核。

2. 環境變數（.env）

DATABASE_URL：MySQL 連線字串（async 驅動，應用程式使用）。

JWT_SECRET：JWT 簽章用強隨機字串（至少 32 字元）。

ACCESS_TOKEN_EXPIRE_MINUTES：預設 20。

REFRESH_TOKEN_EXPIRE_DAYS：預設 21。

（預留）CORS_ALLOW_ORIGINS、郵件服務、第三方登入金鑰⋯⋯

3. 資料表（結構說明）
3.1 users

id：主鍵

status：guest / active / banned（預設 guest）

device_id：裝置識別（Guest 初次登入綁定；可空）

email：可空；active 才會有

password_hash：可空

created_at、last_login_at

建議索引：status、device_id、email UNIQUE

3.2 refresh_tokens

id：主鍵

user_id：外鍵→users.id

token_hash：Refresh Token 雜湊（只存雜湊，不存明文）

expires_at、revoked_at（撤銷時填）

created_at、created_ip、created_user_agent

索引：token_hash（INDEX）

3.3（可選）devices

id、user_id、device_id（UNIQUE）

platform、app_version、device_model、os_version

created_at、last_seen_at、created_ip、created_user_agent

時區：所有時間以 UTC 儲存；顯示時再轉本地。

4. Token 政策與安全決策

Access Token（AT）：JWT，效期 20 分鐘；用途是存取受保護 API。

Claims（最小集）：sub(user_id)、exp、iat、is_guest。

演算法：HS256；金鑰：JWT_SECRET。

Refresh Token（RT）：長隨機字串，效期 21 天；只能用來換新 AT。

僅在發行當下回傳明文；資料庫僅存雜湊。

Rotation（旋轉更新）：

每次 /auth/refresh：驗證舊 RT → 發新 AT + 新 RT → 立即撤銷舊 RT。

同一 RT 被重複使用 → 視為可疑，拒絕並可標記異常。

登出：撤銷對應 RT（寫入 revoked_at）。

升級帳號（guest→active）：成功後旋轉 RT。

重設密碼：撤銷該 user 所有有效 RT（等同「登出所有裝置」）。

多裝置：允許多筆有效 RT（每裝置一筆）；提供「登出所有裝置」。

5. 限流（Rate Limit）

/auth/guest：每 IP + 每 device_id，每分鐘最多 10 次。

/auth/refresh：每 Refresh Token，每分鐘最多 6 次。

/auth/login（未來 Email 登入）：每帳號 + IP，15 分鐘最多 20 次。

違反：回傳 RATE_LIMITED 與 retry_after_seconds。

6. CORS 與傳輸

開發：允許本機或測試來源。

正式：僅允許正式網域；強制 HTTPS。

授權標頭：Authorization: Bearer <access_token>。

7. 端點介面（不含程式碼）
7.1 POST /auth/guest

請求：device_id（可選；若無則後端生成回傳並要求前端保存）、platform、app_version、（可選）device_model、os_version。

流程：

限流與資料驗證

依 device_id 查找 user；找不到則建立 status=guest 的 user

簽發 AT；產生 RT 並存雜湊

更新/新增 devices 記錄（若有）

回應：user_id、access_token、access_token_expires_in、refresh_token、refresh_token_expires_in、is_guest、（後端生成時回 device_id）

錯誤碼：DEVICE_ID_INVALID、RATE_LIMITED、SERVER_ERROR

7.2 POST /auth/refresh

請求：refresh_token

流程：驗證雜湊→檢查未過期、未撤銷→旋轉（發新 AT+RT，撤銷舊 RT）

回應：access_token、access_token_expires_in、refresh_token（若採旋轉）、refresh_token_expires_in

錯誤碼：INVALID_TOKEN、TOKEN_EXPIRED、TOKEN_REVOKED、RATE_LIMITED

7.3 POST /auth/logout

請求：refresh_token

流程：將該 RT 記錄設為撤銷

回應：成功訊息

錯誤碼：INVALID_TOKEN、ALREADY_REVOKED

7.4 GET /auth/me（需 AT）

回應：user_id、email（可能為空）、status、is_guest、display_name（如有）

7.5 POST /auth/upgrade（Guest 升級）

請求（擇一或多擇）：

Email + 密碼（本地帳號）

Google/第三方憑證（未來）

流程：

驗證目前 AT（必須已登入）

寫入 email/password_hash 或 oauth 欄位，status=active

旋轉 RT

回應：成功訊息與新憑證（若有）

8. 錯誤碼對照

INVALID_TOKEN：Token 不存在或格式錯誤

TOKEN_EXPIRED：Token 過期

TOKEN_REVOKED：Token 已撤銷

RATE_LIMITED：超出限流，附 retry_after_seconds

DEVICE_ID_INVALID：裝置識別格式錯誤

UNAUTHORIZED：缺少或無效 AT

SERVER_ERROR：伺服器內部錯誤

9. 稽核與告警

記錄：登入成功/失敗、refresh、撤銷、升級帳號、可疑重複使用 RT。

告警：同一 RT 在不同 IP/UA 短時間重複使用 → 阻擋並通知。

日誌保存：至少 30–90 天。

10. 測試用例（驗收清單）

首次 /auth/guest（無 device_id）→ 建立 guest、回 AT/RT。

同一 device_id 再次呼叫 → 回同一 user_id。

AT 過期 → /auth/refresh 成功換新 AT（並旋轉 RT）。

登出後用舊 RT 續期 → 失敗（TOKEN_REVOKED）。

超頻呼叫 /auth/guest → RATE_LIMITED。

升級帳號成功 → 旋轉 RT，保留原遊戲資料。

重設密碼（未來）→ 所有 RT 失效。

同一 RT 重複使用 → 被阻擋並產生日誌。

11. Flutter 端行為（協定）

啟動：若無憑證 → 呼叫 /auth/guest；保存 device_id 與 RT（安全儲存）。

呼叫 API：在標頭帶 Bearer <access_token>。

401 或將過期：先 /auth/refresh 再重試原請求。

登出：呼叫 /auth/logout，刪除本地憑證。

裝置識別：若後端回 device_id，前端需永久保存並後續附帶。