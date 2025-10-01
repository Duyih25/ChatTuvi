import os
from typing import TypedDict, Union, List, Optional
from operator import itemgetter

from langchain_core.agents import AgentFinish
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable, RunnablePassthrough
from langchain_google_genai import ChatGoogleGenerativeAI
from typing import Annotated, Sequence, TypedDict
from langgraph.graph.message import add_messages

from agent.tools import *
from agent.prompts import *


class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_messages]
    userId: Optional[str] = None


class AgentBase:
    def __init__(self, model: ChatGoogleGenerativeAI, 
                 tools: List[Runnable], system_prompt: str):
        self.tools = tools
        self.llm_with_tools = model.bind_tools(tools=tools)
        self.system_prompt = system_prompt


class QueryPlanningAgents(AgentBase):
    """Agent chia nhỏ task và chọn Agent hỏi đáp về nội dung được đưa ra hay hỏi về thống kê log của user"""
    def __init__(self, model: ChatGoogleGenerativeAI):
        super().__init__(
            model=model, 
            tools=[],
            system_prompt = QUERY_PLANNING_PROMPT
        )
    
    def __call__(self, message: List[Union[HumanMessage, AIMessage]]):
        system_prompt = SystemMessage(content= self.system_prompt)
        response = self.llm_with_tools.invoke([system_prompt] + message)
        return response

class StatisticAgent(AgentBase):
    """Agent thống kê log của người dùng"""
    def __init__(self, model: ChatGoogleGenerativeAI, tool_list = []):
        super().__init__(
            model=model, 
            tools=tool_list,
            system_prompt = STATISTIC_SYSTEM_PROMPT
        )
    
    def __call__(self, message: List[Union[HumanMessage, AIMessage]], userId):
        system_prompt = SystemMessage(content= self.system_prompt + f" userId của người dùng này là {userId}")
        response = self.llm_with_tools.invoke([system_prompt] + message)
        return response
        
class ContentAgent(AgentBase):
    """Agent trả lời câu hỏi từ """
    def __init__(self, model: ChatGoogleGenerativeAI, tool_list = []):
        super().__init__(
            model=model, 
            tools=tool_list,
            system_prompt = CONTENT_SYSTEM_PROMPT
        )
    
    def __call__(self, message: List[Union[HumanMessage, AIMessage]]):
        system_prompt = SystemMessage(content= self.system_prompt)
        response = self.llm_with_tools.invoke([system_prompt] + message)
        return response