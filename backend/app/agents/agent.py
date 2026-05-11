from typing import TypedDict, Annotated
import operator
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, BaseMessage
import structlog
import os

from backend.app.tools.web_scraper_tool import web_scraper_tool
from backend.app.tools.news_search_tool import news_search_tool
from backend.app.tools.reddit_search_tool import reddit_search_tool

logger = structlog.get_logger()

SYSTEM_PROMPT = """You are a Market Intelligence Agent. Your job is to analyze competitors.

When given a company name or URL, you must:
1. Scrape their website using web_scraper_tool
2. Search for recent news using news_search_tool
3. Find user opinions using reddit_search_tool
4. Synthesize everything into a structured SWOT analysis report

IMPORTANT: Call all three tools ONCE, then write the final report. Do NOT call tools again after you have results.

Return the final report in this exact format:

## Company: [name]

### Overview
[2-3 sentences about what the company does]

### Strengths
- [strength 1]
- [strength 2]
- [strength 3]

### Weaknesses
- [weakness 1]
- [weakness 2]

### Opportunities
- [opportunity 1]
- [opportunity 2]

### Threats
- [threat 1]
- [threat 2]

### Recent News
- [news item 1]
- [news item 2]

### User Sentiment
[Summary of what users say on Reddit and review sites]

### Conclusion
[2-3 sentences with key takeaways]
"""

tools = [web_scraper_tool, news_search_tool, reddit_search_tool]


class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], operator.add]


def should_continue(state: AgentState) -> str:
    last_message = state["messages"][-1]
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "tools"
    return END


def call_model(state: AgentState) -> AgentState:
    logger.info("agent_thinking", messages_count=len(state["messages"]))

    llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        google_api_key=os.getenv("GOOGLE_API_KEY"),
    ).bind_tools(tools)

    messages = list(state["messages"])
    if len(messages) == 1:
        first = messages[0]
        messages[0] = HumanMessage(
            content=f"{SYSTEM_PROMPT}\n\nUser request: {first.content}"
        )

    response = llm.invoke(messages)
    logger.info("agent_responded", has_tool_calls=bool(
        hasattr(response, "tool_calls") and response.tool_calls
    ))
    return {"messages": [response]}


def build_agent():
    tool_node = ToolNode(tools)

    graph = StateGraph(AgentState)
    graph.add_node("agent", call_model)
    graph.add_node("tools", tool_node)

    graph.set_entry_point("agent")
    graph.add_conditional_edges(
        "agent",
        should_continue,
        {"tools": "tools", END: END}
    )
    graph.add_edge("tools", "agent")

    return graph.compile()


def run_agent(company: str, language: str = "Russian") -> str:
    logger.info("run_started", company=company, language=language)
    agent = build_agent()

    result = agent.invoke({
        "messages": [HumanMessage(
            content=f"Analyze this competitor: {company}. Write the entire report in {language} language."
        )]
    })

    final_message = result["messages"][-1]
    if isinstance(final_message.content, list):
        report = " ".join(
            block.get("text", "") for block in final_message.content
            if isinstance(block, dict)
        )
    else:
        report = final_message.content
    logger.info("run_finished", company=company, report_length=len(report))
    return report

if __name__ == "__main__":
    from dotenv import load_dotenv
    from pathlib import Path
    load_dotenv(Path(__file__).parent.parent.parent.parent / ".env")
    report = run_agent("Notion", language="Russian")
    print(report)


