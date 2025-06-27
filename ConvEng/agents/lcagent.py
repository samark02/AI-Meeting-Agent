# Initialize OpenAI llm
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import AIMessage, HumanMessage
from langchain.chains import LLMChain
from langchain_community.callbacks import get_openai_callback

def get_openai_llm(model, api_key):
    """Fetch the OpenAI LLM."""
    return ChatOpenAI(model=model, openai_api_key=api_key)


def get_prompt_template(system_prompt):
    """Returns a systemprompt to be used"""
    return ChatPromptTemplate.from_messages(
        [
            ("system", system_prompt),
            MessagesPlaceholder("chat_history"),
            ("human", "{input}"),
            ("system", "Current date and time (IST): {date_time}")
        ]
    )

def create_lc_chain(system_prompt, model, api_key):
    """Create an agent executor by passing in the agent and tools"""
    llm = get_openai_llm(model, api_key)
    
    prompt = get_prompt_template(system_prompt)
    return LLMChain(llm=llm, prompt=prompt)


def invoke_lc_chain(
    input: str, chat_history: list, chain: LLMChain, date_time: str
) -> dict:
    """Talk to the agent by passing a input."""
    # pass user input to the agent
    with get_openai_callback() as cb:
        chain_response = chain.invoke(
        {"input": input, "chat_history": chat_history, "date_time": date_time}
        )    
    
    # store the conversation in chat history
    chat_history.extend(
        [
            HumanMessage(content=str(chain_response["input"])),
            AIMessage(content=str(chain_response["text"])),
        ]
    )
    # return the response
    return chain_response, chat_history,cb

def create_guardrail_check_model(dynamic_prompt,model,api_key):
    llm = get_openai_llm(model, api_key)
    prompt_template = ChatPromptTemplate.from_template(dynamic_prompt)
    return llm, prompt_template