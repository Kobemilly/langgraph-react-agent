import os
from typing import List, Dict, TypedDict

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

    print("AI analysis complete. Responding to UI.")
    return {"messages": state["messages"] + [AIMessage(content=analysis_text)]}

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
builder.add_edge("analyze_content", "present_results")
builder.add_edge("present_results", END)

app = builder.compile()