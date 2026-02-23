# Import relevant functionality
from langchain.chat_models import init_chat_model
from langchain_tavily import TavilySearch
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import create_react_agent

import getpass
import os

from src.core.constants import TAVILY_API_KEY, GENAI_API_KEY

os.environ["TAVILY_API_KEY"] = TAVILY_API_KEY

if not os.environ.get("GENAI_API_KEY"):
  os.environ["GENAI_API_KEY"] = GENAI_API_KEY
  
# Create the agent
# memory = MemorySaver()
model = init_chat_model("gemini-2.5-flash", model_provider="google_genai")
search = TavilySearch(max_results=2)
tools = [search]

agent_executor = create_react_agent(model, tools)

input_message = {"role": "user", "content": "Search for the weather in SF"}
response = agent_executor.invoke({"messages": [input_message]})

for message in response["messages"]:
    message.pretty_print()