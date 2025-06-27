# Initialize OpenAI llm
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import AIMessage, HumanMessage
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_community.callbacks.manager import get_openai_callback
from langchain_community.tools.tavily_search import TavilySearchResults
from tools.rag_tools import *

from utils import fetch_conversation_memory,store_conversation_memory

tool_map = {
    "tavily_search_results": TavilySearchResults,
    "fetch_rag_answers" : FetchRAGAnswer,
}

def get_openai_llm(model, api_key):
    """Fetch the OpenAI LLM."""
    return ChatOpenAI(model=model, openai_api_key=api_key)


def get_prompt_template(system_prompt):
    """Returns a systemprompt to be used"""
    return ChatPromptTemplate.from_messages(
        [
            ("system", system_prompt),
            ("placeholder", "{chat_history}"),
            ("human", "{input}"),
            ("placeholder", "{agent_scratchpad}"),
            ("system", "Current date and time (IST): {date_time}")
        ]
    )


def get_agent_tools(tool_names, tool_config):
    """Gets a list of tools based on names"""
    tools = []
    for tool_name in tool_names:
        # Retrieve tool_variables for the current tool_name
        tool_variables = next(
            (tool["tool_variables"] for tool in tool_config if tool["tool_id"] == tool_name), 
            {}
        ) 
          # Create an instance of the tool with the retrieved tool_variables
        if(tool_variables):
            tool_instance = tool_map[tool_name](tool_variables)
            tools.append(tool_instance)
        else:
            tools.append(tool_map[tool_name]())

        
    return tools


def create_lc_agent(llm, tools, prompt):
    """Construct the Tools agent"""
    agent = create_tool_calling_agent(llm, tools, prompt)
    return agent


def create_lc_agent_executor(system_prompt, model, api_key, tool_names,tool_config):
    """Create an agent executor by passing in the agent and tools"""
    llm = get_openai_llm(model, api_key)
    tools = get_agent_tools(tool_names,tool_config)
    prompt = get_prompt_template(system_prompt)
    agent = create_lc_agent(llm, tools, prompt)
    agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True,stream_runnable=False)
    return agent_executor


def invoke_lc_agent(
    input: str, chat_history: list, agent_executor: AgentExecutor, date_time: str
) -> dict:
    """Talk to the agent by passing a input."""
    # pass user input to the agent
    with get_openai_callback() as cb:
        agent_response = agent_executor.invoke(
        {"input": input, "chat_history": chat_history, "date_time": date_time}
        )
        

    # store the conversation in chat history

    chat_history.extend(
        [
            HumanMessage(content=str(agent_response["input"])),
            AIMessage(content=str(agent_response["output"])),
        ]
    )
    # return the response
    return agent_response, chat_history,cb