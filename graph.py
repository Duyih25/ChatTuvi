import os
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from agent.agents import QueryPlanningAgents, StatisticAgent, ContentAgent, AgentState
from langchain_core.pydantic_v1 import BaseModel, Field
from langchain_google_genai import ChatGoogleGenerativeAI
from agent.tools import retrieve_tool
from dotenv import load_dotenv
from agent.tools import *
import json

def build_graph():
    load_dotenv()
    os.environ["GOOGLE_API_KEY"] = os.getenv('API_KEY')

    GEMINI_MODEL = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0)

    def query_planning_step(state: AgentState):
        """Điều hướng đến Agent phù hợp"""
        n_last_message = state["messages"][-5: ]
        response = queryPlaningAgent(n_last_message)
        answer = response.content.replace("json", "").replace("`", "").strip()
        answer = json.loads(answer)
        if 'statistic' in answer['agent']:
            return "statistic"
        elif 'content' in answer['agent']:
            return "content"
        else:
            print("End ròi")
            return END


    def statistic_answer(state: AgentState):
        n_last_message = state["messages"][-5:]
        userId = state['userId']  
        response = statisticAgent(n_last_message, userId)
        return {"messages": [response]}


    def content_answer(state: AgentState):
        """Lấy câu trả lời từ Agent trả lời thông tin liên quan đến tnội dung"""
        n_last_message = state["messages"][-5: ]
        response = contentAgent(n_last_message)

        return {"messages": [response]}

    def should_continue(state: AgentState): 
        messages = state["messages"]
        last_message = messages[-1]
        if not last_message.tool_calls: 
            return "end"
        else:
            return "continue"


    workflow = StateGraph(AgentState)

    # tool list
    tool_list_content = [retrieve_tool]
    tool_list_stat = [statistic_tool]
    tool_node_stat = ToolNode(tools=tool_list_stat)
    tool_node_content = ToolNode(tools=tool_list_content)

    workflow.add_node("tools_stat", tool_node_stat)
    workflow.add_node("tools_content", tool_node_content)

    # ----- Agent wrappers -----
    queryPlaningAgent = QueryPlanningAgents(GEMINI_MODEL)
    statisticAgent = StatisticAgent(GEMINI_MODEL, tool_list_stat)
    contentAgent = ContentAgent(GEMINI_MODEL, tool_list_content)

    workflow.add_node("queryPlan", lambda state:state)
    workflow.add_node("content", content_answer)
    workflow.add_node("statistic", statistic_answer)


    workflow.set_entry_point("queryPlan")


    workflow.add_conditional_edges(
        "queryPlan",
        query_planning_step,
        {
            "content": "content",
            "statistic": "statistic",
            END: END
        },
    )

    workflow.add_conditional_edges(
        "content",
        should_continue,
        {
            "continue": "tools_content",
            "end": END,
        },
    )
    workflow.add_edge("tools_content", "content")

    workflow.add_conditional_edges(
        "statistic",
        should_continue,
        {
            "continue": "tools_stat",
            "end": END,
        },
    )
    workflow.add_edge("tools_stat", "statistic")


    app = workflow.compile()
    
    return app