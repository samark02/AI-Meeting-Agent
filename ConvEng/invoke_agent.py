from agents.lcagent_tools import *
from agents.lcagent import *
from datetime import datetime, UTC
import pytz
import logging

def get_current_datetime_ist():
    ist = pytz.timezone('Asia/Kolkata')
    utc_now = datetime.now(pytz.utc)
    ist_now = utc_now.astimezone(ist)
    return ist_now.strftime("%d/%m/%Y %H:%M:%S")

def agent_run(conversation_config,input_,conversation_history):
    logging.info(f"CHAT HISTORY  {conversation_history}")
    if(len(conversation_config["tool_config"])>0):
            # get an agent executor
        agent_executor = create_lc_agent_executor(
            system_prompt=conversation_config["prompt_template"],
            model=conversation_config["engine_model"],
            api_key=conversation_config["engine_auth"],
            tool_names=[
                tool_config["tool_id"] for tool_config in conversation_config["tool_config"]
            ],
            tool_config=conversation_config['tool_config']
        )
        #store_agent_in_cache(cache_key, agent_executor)

    else:
        agent_executor = create_lc_chain(
            system_prompt=conversation_config["prompt_template"],
            model=conversation_config["engine_model"],
            api_key=conversation_config["engine_auth"]
        )
        #store_agent_in_cache(cache_key, agent_executor)


    if(len(conversation_config["tool_config"])>0):
        agent_response, conversation_history,cb = invoke_lc_agent(
            input=input_,
            chat_history=conversation_history,
            agent_executor=agent_executor,
            date_time=get_current_datetime_ist()
        )
    else:
        agent_response, conversation_history,cb = invoke_lc_chain(
            input=input_,
            chat_history=conversation_history,
            chain=agent_executor,
            date_time=get_current_datetime_ist()
        )
        agent_response['output'] = agent_response['text']
    return agent_response,conversation_history,cb