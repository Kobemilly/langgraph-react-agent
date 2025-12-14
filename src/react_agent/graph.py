import os
from typing import List, Dict, TypedDict
from datetime import datetime
import markdown

# LangGraph and related imports
from langgraph.graph import StateGraph, END
from langchain_core.messages import AIMessage, HumanMessage

# AWS Bedrock LLM import
from langchain_aws import ChatBedrock

# Public libraries for web search and scraping
from ddgs.ddgs import DDGS
import requests
from bs4 import BeautifulSoup

# 1. 定義 Graph State
class GraphState(TypedDict, total=False):
    messages: List
    keyword: str
    original_keyword: str
    search_attempts: int
    urls: List[str]
    scraped_content: List[Dict[str, str]]
    grade: str
    analysis: str
    rewritten_content: str
    output_file: str
    html_file: str
    file_saved: bool
    error: str

# 2. 實作節點 (Nodes)

def start_node(state: dict) -> dict:
    """Final version: Correctly parses the nested message structure from agent-chat-ui."""
    print("\n--- (Robust) STARTING GRAPH ---")
    messages = state.get("messages", [])
    if not messages:
        raise ValueError("Input from UI is missing the 'messages' field.")
    last_message = messages[-1]
    if isinstance(last_message, dict):
        content_payload = last_message.get("content", "")
    else:
        content_payload = getattr(last_message, 'content', "")
    if not isinstance(content_payload, list) or not content_payload:
        raise ValueError("Last message content from UI is not in the expected list format.")
    first_content_block = content_payload[0]
    keyword = first_content_block.get("text", "")
    if not keyword or not keyword.strip():
        raise ValueError(f"Extracted keyword from UI input is empty. Content: {content_payload}")
    keyword = keyword.strip()
    print(f"Successfully extracted keyword: {keyword}")
    return {
        "messages": messages,
        "keyword": keyword,
        "original_keyword": keyword,
        "search_attempts": 0,
    }

def web_search_node(state: GraphState) -> GraphState:
    print(f"\n--- PERFORMING WEB SEARCH (Attempt #{state.get('search_attempts', 0) + 1}) ---")
    keyword = state["keyword"]
    print(f"Searching for: {keyword}")
    try:
        with DDGS() as ddgs:
            search_results = list(ddgs.text(query=keyword, max_results=5))
        urls = [result['href'] for result in search_results]
        print(f"Found {len(urls)} URLs.")
        return {"urls": urls}
    except Exception as e:
        print(f"Web search failed: {e}")
        return {"urls": [], "error": f"Web search failed: {e}"}

def scrape_content_node(state: GraphState) -> GraphState:
    print("\n--- SCRAPING CONTENT ---")
    urls = state.get("urls", [])
    if not urls:
        return {"scraped_content": []}
    scraped_data = []
    for url in urls:
        print(f"Scraping {url}...")
        try:
            headers = {'User-Agent': 'Mozilla/5.0'}
            response = requests.get(url, headers=headers, timeout=15)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            text_content = soup.get_text(separator=' ', strip=True)
            scraped_data.append({"url": url, "content": text_content})
        except Exception as e:
            scraped_data.append({"url": url, "content": f"Error: {e}"})
    print("Finished scraping.")
    return {"scraped_content": scraped_data}

def grade_content_node(state: GraphState) -> GraphState:
    print("\n--- GRADING SCRAPED CONTENT ---")
    scraped_content = state.get("scraped_content", [])
    original_keyword = state.get("original_keyword", "").lower()
    if not scraped_content:
        return {"grade": "bad"}
    full_text = " ".join(item["content"] for item in scraped_content).lower()
    if len(full_text) < 1500:
        return {"grade": "bad"}
    if original_keyword not in full_text:
        return {"grade": "bad"}
    return {"grade": "good"}

def refine_search_node(state: GraphState) -> GraphState:
    print("\n--- REFINING SEARCH KEYWORD ---")
    original_keyword = state["original_keyword"]
    new_keyword = f'{original_keyword} 應用與比較'
    return {
        "keyword": new_keyword,
        "search_attempts": state.get("search_attempts", 0) + 1
    }

def analyze_content_node(state: GraphState) -> GraphState:
    """FINAL VERSION: Performs analysis by calling AWS Bedrock LLM."""
    print("\n--- PERFORMING REAL AI ANALYSIS ---")
    scraped_content = state.get("scraped_content", [])
    analysis_text = ""
    try:
        # Initialize the Bedrock model
        # 支援的模型: anthropic.claude-3-5-sonnet-20241022-v2:0, anthropic.claude-3-sonnet-20240229-v1:0, 
        # anthropic.claude-3-haiku-20240307-v1:0, meta.llama3-1-405b-instruct-v1:0 等
        llm = ChatBedrock(
            model_id=os.getenv("BEDROCK_MODEL_ID", "anthropic.claude-3-5-sonnet-20241022-v2:0"),
            region_name=os.getenv("AWS_REGION", "us-east-1"),
            model_kwargs={
                "temperature": 0.7,
                "max_tokens": 4096
            }
        )
        
        if not scraped_content or all("Error:" in item["content"] for item in scraped_content):
            analysis_text = "抱歉,我無法取得任何內容進行分析。"
        else:
            full_text = " ".join(item["content"] for item in scraped_content if "Error:" not in item["content"])
            text_for_analysis = full_text[:20000] # Use a larger limit for the real LLM
            
            analysis_prompt = (
                "請扮演數據分析師。僅根據以下文本,提供簡潔的摘要(約200字)。"
                "識別關鍵主題和整體情緒。"
                f"使用者原始查詢為: '{state['original_keyword']}'。\n\n"
                "--- 分析文本 ---\n"
                f"{text_for_analysis}"
            )
            
            print(f"Invoking Bedrock model ({llm.model_id}) for analysis...")
            response = llm.invoke(analysis_prompt)
            analysis_text = response.content

    except Exception as e:
        print(f"LLM analysis failed: {e}")
        analysis_text = f"抱歉,AI 分析過程中發生錯誤: {e}"

    print("AI analysis complete.")
    return {"analysis": analysis_text}

def rewrite_content_node(state: GraphState) -> GraphState:
    """改寫代理: 將分析內容改寫為科技資訊風格的文章。"""
    print("\n--- REWRITING CONTENT IN TECH NEWS STYLE ---")
    analysis_text = state.get("analysis", "")
    scraped_content = state.get("scraped_content", [])
    
    try:
        llm = ChatBedrock(
            model_id=os.getenv("BEDROCK_MODEL_ID", "anthropic.claude-3-5-sonnet-20241022-v2:0"),
            region_name=os.getenv("AWS_REGION", "us-east-1"),
            model_kwargs={
                "temperature": 0.8,
                "max_tokens": 4096
            }
        )
        
        # 準備原始內容摘要
        original_content = " ".join(
            item["content"][:500] for item in scraped_content 
            if "Error:" not in item["content"]
        )[:3000]
        
        rewrite_prompt = f"""你是一個內容改寫專家。將提供給你的分析內容改寫為科技資訊風格的文章。

科技資訊風格特點：
1. 標題簡潔醒目
2. 開頭直接點明主題
3. 內容客觀準確但生動有趣
4. 使用專業術語但解釋清晰
5. 段落簡短，重點突出
6. 使用繁體中文

原始查詢: {state['original_keyword']}

分析內容:
{analysis_text}

參考資料摘要:
{original_content}

請將上述分析改寫為一篇完整的科技資訊文章，包含:
- 吸引人的標題
- 引言段落
- 主要內容（2-3個段落）
- 總結
"""
        
        print(f"Invoking Bedrock model for content rewriting...")
        response = llm.invoke(rewrite_prompt)
        rewritten_text = response.content
        
        print("Content rewriting complete.")
        return {
            "rewritten_content": rewritten_text,
            "messages": state["messages"] + [AIMessage(content=rewritten_text)]
        }
        
    except Exception as e:
        print(f"Content rewriting failed: {e}")
        error_msg = f"改寫過程發生錯誤: {e}\n\n原始分析:\n{analysis_text}"
        return {
            "rewritten_content": analysis_text,
            "messages": state["messages"] + [AIMessage(content=error_msg)]
        }

def write_file_node(state: GraphState) -> GraphState:
    """文件寫入代理: 將改寫後的內容保存到文件。"""
    print("\n--- WRITING CONTENT TO FILE ---")
    rewritten_content = state.get("rewritten_content", "")
    original_keyword = state.get("original_keyword", "unknown")
    
    try:
        # 建立輸出目錄
        output_dir = "output"
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
            print(f"Created output directory: {output_dir}")
        
        # 生成文件名稱（包含日期時間）
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        # 清理關鍵字作為文件名的一部分
        safe_keyword = "".join(c for c in original_keyword if c.isalnum() or c in (' ', '-', '_')).strip()
        safe_keyword = safe_keyword.replace(' ', '_')[:50]  # 限制長度
        filename = f"{timestamp}_{safe_keyword}.md"
        filepath = os.path.join(output_dir, filename)
        
        # 寫入文件
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(f"# {original_keyword}\n\n")
            f.write(f"生成時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            f.write("---\n\n")
            f.write(rewritten_content)
        
        success_msg = f"✅ 文章已成功保存\n\n📁 文件路徑: `{filepath}`\n📊 文件大小: {len(rewritten_content)} 字元\n⏰ 保存時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        print(f"File saved successfully: {filepath}")
        
        return {
            "output_file": filepath,
            "file_saved": True,
            "messages": state["messages"] + [AIMessage(content=success_msg)]
        }
        
    except Exception as e:
        print(f"File writing failed: {e}")
        error_msg = f"❌ 文件保存失敗: {e}\n\n內容已在上方顯示。"
        return {
            "file_saved": False,
            "messages": state["messages"] + [AIMessage(content=error_msg)]
        }

def render_html_node(state: GraphState) -> GraphState:
    """HTML 渲染代理: 將 Markdown 內容轉換為專業的 HTML 檔案。"""
    print("\n--- RENDERING HTML FROM MARKDOWN ---")
    rewritten_content = state.get("rewritten_content", "")
    original_keyword = state.get("original_keyword", "unknown")
    md_filepath = state.get("output_file", "")
    
    try:
        # 生成 HTML 文件名稱（與 MD 文件同名但副檔名不同）
        if md_filepath:
            html_filepath = md_filepath.replace('.md', '.html')
        else:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            safe_keyword = "".join(c for c in original_keyword if c.isalnum() or c in (' ', '-', '_')).strip()
            safe_keyword = safe_keyword.replace(' ', '_')[:50]
            html_filepath = f"output/{timestamp}_{safe_keyword}.html"
        
        # 使用 Markdown 套件轉換內容
        md = markdown.Markdown(extensions=['extra', 'nl2br', 'sane_lists'])
        html_content = md.convert(rewritten_content)
        
        # 專業 HTML 模板
        html_template = f"""<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="generator" content="LangGraph ReAct Agent">
    <meta name="keywords" content="{original_keyword}">
    <title>{original_keyword} - 科技資訊文章</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        body {{
            font-family: 'Segoe UI', 'Microsoft JhengHei', Arial, sans-serif;
            line-height: 1.8;
            color: #333;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 20px;
        }}
        .container {{
            max-width: 900px;
            margin: 0 auto;
            background: white;
            border-radius: 12px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.1);
            overflow: hidden;
        }}
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 40px;
            text-align: center;
        }}
        .header h1 {{
            font-size: 2.2em;
            margin-bottom: 10px;
            font-weight: 700;
        }}
        .metadata {{
            background: #f8f9fa;
            padding: 15px 40px;
            border-bottom: 2px solid #e9ecef;
            font-size: 0.9em;
            color: #6c757d;
        }}
        .metadata span {{
            margin-right: 20px;
        }}
        .content {{
            padding: 40px;
        }}
        .content h1 {{
            color: #667eea;
            font-size: 2em;
            margin: 30px 0 20px 0;
            padding-bottom: 10px;
            border-bottom: 3px solid #667eea;
        }}
        .content h2 {{
            color: #764ba2;
            font-size: 1.5em;
            margin: 25px 0 15px 0;
            padding-left: 15px;
            border-left: 4px solid #764ba2;
        }}
        .content h3 {{
            color: #495057;
            font-size: 1.2em;
            margin: 20px 0 10px 0;
        }}
        .content p {{
            margin-bottom: 16px;
            text-align: justify;
        }}
        .content ul, .content ol {{
            margin: 15px 0 15px 30px;
        }}
        .content li {{
            margin-bottom: 8px;
        }}
        .content strong {{
            color: #667eea;
            font-weight: 600;
        }}
        .content code {{
            background: #f8f9fa;
            padding: 2px 6px;
            border-radius: 3px;
            font-family: 'Courier New', monospace;
            color: #e83e8c;
        }}
        .content pre {{
            background: #f8f9fa;
            padding: 15px;
            border-radius: 5px;
            overflow-x: auto;
            margin: 15px 0;
        }}
        .content blockquote {{
            border-left: 4px solid #667eea;
            padding-left: 20px;
            margin: 20px 0;
            color: #6c757d;
            font-style: italic;
        }}
        .footer {{
            background: #f8f9fa;
            padding: 20px 40px;
            text-align: center;
            color: #6c757d;
            font-size: 0.9em;
            border-top: 1px solid #e9ecef;
        }}
        .badge {{
            display: inline-block;
            padding: 5px 12px;
            background: #667eea;
            color: white;
            border-radius: 20px;
            font-size: 0.85em;
            margin: 5px;
        }}
        @media (max-width: 768px) {{
            body {{
                padding: 10px;
            }}
            .container {{
                border-radius: 8px;
            }}
            .header, .content {{
                padding: 20px;
            }}
            .header h1 {{
                font-size: 1.6em;
            }}
            .content h1 {{
                font-size: 1.5em;
            }}
            .content h2 {{
                font-size: 1.2em;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>{original_keyword}</h1>
            <div style="margin-top: 15px;">
                <span class="badge">🔍 AI 搜尋</span>
                <span class="badge">🤖 AI 分析</span>
                <span class="badge">✍️ AI 改寫</span>
            </div>
        </div>
        <div class="metadata">
            <span>📅 生成時間: {datetime.now().strftime('%Y年%m月%d日 %H:%M:%S')}</span>
            <span>📦 文件格式: HTML</span>
            <span>🌐 語言: 繁體中文</span>
        </div>
        <div class="content">
{html_content}
        </div>
        <div class="footer">
            <p>🤖 由 <strong>LangGraph ReAct Agent</strong> 自動生成</p>
            <p style="margin-top: 10px; font-size: 0.85em;">
                技術支持: AWS Bedrock Claude 3.5 Sonnet | LangChain | LangGraph
            </p>
        </div>
    </div>
</body>
</html>
"""
        
        # 寫入 HTML 文件
        with open(html_filepath, 'w', encoding='utf-8') as f:
            f.write(html_template)
        
        success_msg = f"\n\n🌐 HTML 檔案已成功生成\n\n📄 HTML 路徑: `{html_filepath}`\n📊 檔案大小: {len(html_template)} 字元\n✨ 可用於 EMAIL 分享或網頁展示"
        print(f"HTML file rendered successfully: {html_filepath}")
        
        return {
            "html_file": html_filepath,
            "messages": state["messages"] + [AIMessage(content=success_msg)]
        }
        
    except Exception as e:
        print(f"HTML rendering failed: {e}")
        error_msg = f"\n\n⚠️ HTML 渲染失敗: {e}\n\nMarkdown 檔案已成功保存。"
        return {
            "messages": state["messages"] + [AIMessage(content=error_msg)]
        }

def present_results_node(state: GraphState) -> GraphState:
    print("\n--- FINAL STATE REACHED --- For UI display, check the chat history.")
    return {}

# ... (Conditional Logic and Graph building remains the same) ...

def decide_to_proceed(state: GraphState) -> str:
    if state.get("error") or not state.get("urls"):
        return "__end__"
    return "scrape"

def decide_to_analyze_or_refine(state: GraphState) -> str:
    grade = state.get("grade")
    attempts = state.get("search_attempts", 0)
    if grade == "good":
        return "analyze"
    else:
        if attempts >= 1:
            return "analyze"
        else:
            return "refine"

builder = StateGraph(GraphState)

builder.add_node("start_node", start_node)
builder.add_node("web_search", web_search_node)
builder.add_node("scrape_content", scrape_content_node)
builder.add_node("grade_content", grade_content_node)
builder.add_node("refine_search", refine_search_node)
builder.add_node("analyze_content", analyze_content_node)
builder.add_node("rewrite_content", rewrite_content_node)
builder.add_node("write_file", write_file_node)
builder.add_node("render_html", render_html_node)
builder.add_node("present_results", present_results_node)

builder.set_entry_point("start_node")
builder.add_edge("start_node", "web_search")
builder.add_conditional_edges("web_search", decide_to_proceed, {"scrape": "scrape_content", "__end__": "present_results"})
builder.add_edge("scrape_content", "grade_content")
builder.add_conditional_edges(
    "grade_content",
    decide_to_analyze_or_refine,
    {
        "analyze": "analyze_content",
        "refine": "refine_search"
    }
)
builder.add_edge("refine_search", "web_search")
builder.add_edge("analyze_content", "rewrite_content")
builder.add_edge("rewrite_content", "write_file")
builder.add_edge("write_file", "render_html")
builder.add_edge("render_html", "present_results")
builder.add_edge("present_results", END)

app = builder.compile()
graph = app  # Alias for backward compatibility
