# AWS Bedrock 設定指南

## 前置準備

### 1. 安裝依賴套件

```bash
pip install langchain-aws boto3
```

或使用 pip 安裝完整專案依賴:

```bash
pip install -e .
```

### 2. AWS 認證配置

#### 方法 A: 使用 .env 文件 (推薦)

在專案根目錄的 `.env` 文件中設定:

```env
AWS_ACCESS_KEY_ID=your-access-key-id
AWS_SECRET_ACCESS_KEY=your-secret-access-key
AWS_REGION=us-east-1
BEDROCK_MODEL_ID=anthropic.claude-3-5-sonnet-20241022-v2:0
```

#### 方法 B: 使用 AWS CLI 配置

```bash
aws configure
```

輸入:
- AWS Access Key ID
- AWS Secret Access Key
- Default region name (例如: us-east-1)
- Default output format (json)

#### 方法 C: 使用 IAM Role (適用於 EC2/ECS)

如果在 AWS 環境中運行,可以使用 IAM Role,無需明確提供憑證。

### 3. 啟用 Bedrock 模型訪問權限

1. 登入 AWS Console
2. 前往 **Amazon Bedrock** 服務
3. 點擊左側選單的 **Model access**
4. 點擊 **Manage model access** 或 **Edit**
5. 勾選您想使用的模型:
   - ✅ **Anthropic Claude 3.5 Sonnet v2** (推薦)
   - ✅ Anthropic Claude 3 Sonnet
   - ✅ Anthropic Claude 3 Haiku
   - ✅ Meta Llama 3.1
   - ✅ Amazon Titan
6. 點擊 **Request model access**
7. 等待審核通過 (通常幾分鐘內完成)

### 4. 確認 IAM 權限

確保您的 IAM 使用者或角色具有以下權限:

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "bedrock:InvokeModel",
                "bedrock:InvokeModelWithResponseStream"
            ],
            "Resource": "arn:aws:bedrock:*::foundation-model/*"
        }
    ]
}
```

## 可用的 Bedrock 模型

### Anthropic Claude 系列 (推薦)

| 模型 ID | 說明 | 特點 |
|---------|------|------|
| `anthropic.claude-3-5-sonnet-20241022-v2:0` | Claude 3.5 Sonnet v2 | 最新,最強大,推理能力強 |
| `anthropic.claude-3-sonnet-20240229-v1:0` | Claude 3 Sonnet | 穩定,平衡性能和成本 |
| `anthropic.claude-3-haiku-20240307-v1:0` | Claude 3 Haiku | 快速,經濟實惠 |

### Meta Llama 系列

| 模型 ID | 說明 |
|---------|------|
| `meta.llama3-1-405b-instruct-v1:0` | Llama 3.1 405B |
| `meta.llama3-1-70b-instruct-v1:0` | Llama 3.1 70B |
| `meta.llama3-1-8b-instruct-v1:0` | Llama 3.1 8B |

### Amazon Titan 系列

| 模型 ID | 說明 |
|---------|------|
| `amazon.titan-text-premier-v1:0` | Titan Text Premier |
| `amazon.titan-text-express-v1` | Titan Text Express |

## 測試連接

創建測試檔案 `test_bedrock.py`:

```python
from langchain_aws import ChatBedrock
import os
from dotenv import load_dotenv

load_dotenv()

# 初始化 Bedrock 模型
llm = ChatBedrock(
    model_id=os.getenv("BEDROCK_MODEL_ID", "anthropic.claude-3-5-sonnet-20241022-v2:0"),
    region_name=os.getenv("AWS_REGION", "us-east-1"),
    model_kwargs={
        "temperature": 0.7,
        "max_tokens": 1024
    }
)

# 測試呼叫
try:
    response = llm.invoke("你好,請用繁體中文介紹自己。")
    print("✅ Bedrock 連接成功!")
    print(f"回應: {response.content}")
except Exception as e:
    print(f"❌ 連接失敗: {e}")
```

執行測試:

```bash
python test_bedrock.py
```

## 成本估算

### Claude 3.5 Sonnet v2 定價 (us-east-1)
- Input: $3.00 / 1M tokens
- Output: $15.00 / 1M tokens

### Claude 3 Haiku 定價 (經濟實惠)
- Input: $0.25 / 1M tokens
- Output: $1.25 / 1M tokens

## 疑難排解

### 錯誤: "Access denied"
- 檢查 IAM 權限是否正確設定
- 確認已在 Bedrock Console 啟用模型訪問權限

### 錯誤: "ResourceNotFoundException"
- 確認 `BEDROCK_MODEL_ID` 拼寫正確
- 確認模型在您選擇的 region 可用
- 嘗試切換到 `us-east-1` 或 `us-west-2`

### 錯誤: "ValidationException"
- 檢查 `model_kwargs` 參數設定
- 確認 `max_tokens` 不超過模型限制

### 錯誤: "ThrottlingException"
- 請求速率過高,加入重試邏輯
- 考慮升級 AWS 帳戶的服務配額

## 進階配置

### 使用串流回應

```python
from langchain_aws import ChatBedrock

llm = ChatBedrock(
    model_id="anthropic.claude-3-5-sonnet-20241022-v2:0",
    streaming=True,
    model_kwargs={
        "temperature": 0.7,
        "max_tokens": 4096
    }
)

for chunk in llm.stream("寫一個關於 AI 的故事"):
    print(chunk.content, end="", flush=True)
```

### 切換不同 Region

支援的 Bedrock Regions:
- `us-east-1` (美國東部,維吉尼亞)
- `us-west-2` (美國西部,俄勒岡)
- `ap-southeast-1` (亞太,新加坡)
- `ap-northeast-1` (亞太,東京)
- `eu-central-1` (歐洲,法蘭克福)

## 運行應用

設定完成後,啟動 LangGraph 服務:

```bash
langgraph dev
```

或使用 Python 直接執行:

```bash
python src/react_agent/graph.py
```
