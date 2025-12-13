# AWS Bedrock 設定指南

## ✅ 已完成的變更

1. **已更新 `graph.py`**: 從 Google Gemini 改為 AWS Bedrock Claude
2. **已安裝套件**: `langchain-aws` 和 `boto3`
3. **已建立 `.env`**: 包含 AWS 配置範本

---

## ⚠️ 重要說明

由於虛擬環境的 pip 損壞,套件已安裝到系統 Python 環境:
- ✅ `langchain-aws` v1.1.0
- ✅ `boto3` v1.42.9
- ✅ `langchain` v1.1.3

系統可以正常運作,但建議未來重建虛擬環境以保持環境隔離。

---

## 🔧 接下來的設定步驟

### 步驟 1: 啟用 AWS Bedrock 模型存取

1. 登入 [AWS Console](https://console.aws.amazon.com/)
2. 搜尋並進入 **Amazon Bedrock** 服務
3. 左側選單選擇 **Model access** (模型存取)
4. 點擊 **Manage model access** 或 **Edit** 按鈕
5. 勾選你要使用的模型:
   - ✅ **Anthropic Claude 3.5 Sonnet v2** (推薦,最強)
   - ✅ Anthropic Claude 3 Sonnet (平衡)
   - ✅ Anthropic Claude 3 Haiku (最快最便宜)
   - ✅ Meta Llama 3.1 系列 (開源選項)
6. 點擊 **Request model access** 
7. 等待核准(通常幾分鐘內,狀態會從 "In progress" 變為 "Access granted")

**重要**: 必須在你要使用的 AWS 區域(如 `us-east-1`)啟用模型存取!

---

### 步驟 2: 建立 IAM 使用者並取得金鑰

#### 方法 A: 建立新的 IAM 使用者 (推薦)

1. 在 AWS Console 搜尋並進入 **IAM** 服務
2. 左側選單選擇 **Users** → 點擊 **Create user**
3. 輸入使用者名稱,例如: `bedrock-agent-user`
4. 點擊 **Next**
5. 選擇 **Attach policies directly**
6. 搜尋並勾選: **AmazonBedrockFullAccess**
   - (或建立更精細的政策,僅授予 `bedrock:InvokeModel` 權限)
7. 點擊 **Next** → **Create user**
8. 選擇剛建立的使用者
9. 切換到 **Security credentials** 標籤
10. 點擊 **Create access key**
11. 選擇 **Application running outside AWS** → Next
12. (可選)輸入描述標籤 → **Create access key**
13. **❗重要**: 立即複製並儲存:
    - **Access Key ID** (例如: `AKIAIOSFODNN7EXAMPLE`)
    - **Secret Access Key** (例如: `wJalrXUtnFEMI/K7MDENG/...`)
    - 關閉視窗後就無法再看到 Secret Key!

#### 方法 B: 使用現有 IAM 使用者

1. 選擇現有的 IAM 使用者
2. 確保該使用者有 `AmazonBedrockFullAccess` 權限
3. 在 **Security credentials** 建立新的 Access Key

---

### 步驟 3: 更新 `.env` 檔案

編輯 `chatbot_project/.env`:

```bash
# ===== AWS Bedrock 配置 =====
AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE          # 替換為你的 Access Key ID
AWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI/K7MDENG...  # 替換為你的 Secret Key
AWS_REGION=us-east-1                            # 確認與啟用模型的區域一致

# Bedrock 模型選擇 (可選,預設使用 Claude 3.5 Sonnet)
BEDROCK_MODEL_ID=anthropic.claude-3-5-sonnet-20241022-v2:0
```

**支援的模型 ID**:
- `anthropic.claude-3-5-sonnet-20241022-v2:0` (Claude 3.5 Sonnet v2 - 最強)
- `anthropic.claude-3-sonnet-20240229-v1:0` (Claude 3 Sonnet)
- `anthropic.claude-3-haiku-20240307-v1:0` (Claude 3 Haiku - 最快最便宜)
- `meta.llama3-1-405b-instruct-v1:0` (Llama 3.1 405B)
- `meta.llama3-1-70b-instruct-v1:0` (Llama 3.1 70B)
- `mistral.mistral-large-2402-v1:0` (Mistral Large)

---

### 步驟 4: 測試連線

在 `chatbot_project` 目錄下執行:

```powershell
.\.venv\Scripts\Activate.ps1
python
```

然後執行以下測試:

```python
from langchain_aws import ChatBedrock
import os
from dotenv import load_dotenv

load_dotenv()

llm = ChatBedrock(
    model_id="anthropic.claude-3-5-sonnet-20241022-v2:0",
    region_name=os.getenv("AWS_REGION", "us-east-1")
)

response = llm.invoke("你好,請簡單自我介紹一下")
print(response.content)
```

**預期結果**: Claude 應該會用中文回應自我介紹

---

## 🌍 AWS 區域選擇

Bedrock 可用區域(選擇離你最近的):
- `us-east-1` (美東 - 維吉尼亞) ⭐ 最多模型支援
- `us-west-2` (美西 - 奧勒岡)
- `ap-southeast-1` (新加坡)
- `ap-northeast-1` (東京)
- `eu-central-1` (法蘭克福)

**建議台灣使用者**: `ap-northeast-1` (東京) 或 `us-west-2` (美西)

---

## 💰 定價參考

### Claude 3.5 Sonnet v2 (推薦)
- Input: $3.00 / 1M tokens
- Output: $15.00 / 1M tokens
- **範例**: 分析 2000 字文章約花費 $0.01-0.02 USD

### Claude 3 Haiku (最便宜)
- Input: $0.25 / 1M tokens
- Output: $1.25 / 1M tokens
- **範例**: 分析 2000 字文章約花費 $0.001-0.002 USD

### Llama 3.1 70B (開源平衡)
- Input: $0.99 / 1M tokens
- Output: $0.99 / 1M tokens

[完整定價](https://aws.amazon.com/bedrock/pricing/)

---

## 🔒 安全最佳實踐

1. **❌ 絕對不要**將 `.env` 提交到 Git
   ```bash
   # 確認 .gitignore 包含:
   .env
   .env.local
   ```

2. **✅ 使用環境變數** (生產環境)
   - 在伺服器上設定環境變數而非使用 `.env` 文件

3. **✅ 定期輪換金鑰**
   - 每 90 天在 IAM 建立新的 Access Key 並刪除舊的

4. **✅ 使用最小權限原則**
   - 僅授予必要的 Bedrock 權限,避免使用 `FullAccess`
   - 自訂 IAM 政策範例:
     ```json
     {
       "Version": "2012-10-17",
       "Statement": [{
         "Effect": "Allow",
         "Action": [
           "bedrock:InvokeModel",
           "bedrock:InvokeModelWithResponseStream"
         ],
         "Resource": "arn:aws:bedrock:us-east-1::foundation-model/anthropic.claude-3-5-sonnet-20241022-v2:0"
       }]
     }
     ```

5. **✅ 監控使用量**
   - 在 AWS CloudWatch 設定帳單警報
   - 定期檢查 Bedrock 使用量

---

## ❓ 常見問題排查

### Q1: `AccessDeniedException` 錯誤

**原因**:
- IAM 使用者沒有 Bedrock 權限
- 模型存取未啟用
- AWS 金鑰錯誤

**解決方法**:
1. 確認 IAM 使用者有 `AmazonBedrockFullAccess` 或自訂權限
2. 檢查 Bedrock 控制台的 **Model access** 狀態是否為 "Access granted"
3. 驗證 `.env` 的 `AWS_ACCESS_KEY_ID` 和 `AWS_SECRET_ACCESS_KEY` 正確

---

### Q2: `ValidationException: The model returned the following errors`

**原因**:
- 模型 ID 拼寫錯誤
- 該區域不支援此模型
- 輸入內容違反政策

**解決方法**:
1. 檢查 `BEDROCK_MODEL_ID` 拼寫
2. 確認該模型在你的 AWS 區域可用
3. 避免輸入敏感/違規內容

---

### Q3: 想換其他模型怎麼辦?

**方法 1**: 修改 `.env`
```bash
BEDROCK_MODEL_ID=anthropic.claude-3-haiku-20240307-v1:0
```

**方法 2**: 直接修改 `graph.py` 的 `analyze_content_node` 函數
```python
llm = ChatBedrock(
    model_id="anthropic.claude-3-haiku-20240307-v1:0",  # 改這裡
    region_name=os.getenv("AWS_REGION", "us-east-1")
)
```

---

### Q4: 如何在 AWS EC2/Lambda 上使用?

使用 **IAM Role** 而非 Access Key:

1. 建立 IAM Role 並附加 `AmazonBedrockFullAccess`
2. 將 Role 附加到 EC2 instance 或 Lambda function
3. **移除** `.env` 中的 `AWS_ACCESS_KEY_ID` 和 `AWS_SECRET_ACCESS_KEY`
4. boto3 會自動使用 instance/function 的 IAM Role

---

## 🚀 啟動系統

完成設定後,啟動 LangGraph 伺服器:

```powershell
cd C:\Users\kobe.tsai\.gemini\chatbot_project
.\.venv\Scripts\Activate.ps1
langgraph dev
```

然後在另一個終端啟動前端:

```powershell
cd C:\Users\kobe.tsai\.gemini\my_chat_ui
pnpm dev
```

訪問 `http://localhost:3000` 開始測試!

---

## 📝 系統變更摘要

| 項目 | 原始 | 變更後 |
|------|------|--------|
| LLM 提供商 | Google Gemini | AWS Bedrock |
| 預設模型 | gemini-3-pro-preview | Claude 3.5 Sonnet v2 |
| 認證方式 | GOOGLE_API_KEY | AWS Access Key/Secret |
| Python 套件 | langchain-google-genai | langchain-aws, boto3 |
| 區域設定 | N/A | AWS_REGION (可選) |

---

需要協助嗎?請參考:
- [AWS Bedrock 文件](https://docs.aws.amazon.com/bedrock/)
- [LangChain AWS 文件](https://python.langchain.com/docs/integrations/chat/bedrock/)
