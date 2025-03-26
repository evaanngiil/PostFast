from langchain.agents import Tool, initialize_agent, AgentType
from langchain_google_genai import ChatGoogleGenerativeAI
from datetime import datetime
import os

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# Function to get the current time
def get_current_time(_input=None): # Accept an argumetn but it is not used -> for langchain compatibility
    return datetime.now().strftime("%H:%M:%S") 

# Funtion to get the sum of numbers
def calculate_sum(numbers_str) -> str: 
    try:
        numbers = [float(num) for num in numbers_str.split()]
        return str(sum(numbers))
    except Exception as e:
        return "Error: Por favor proporciona números separados por espacios"

# Define the custom tools
tools = [
    Tool(
        name="Hora actual",
        func=get_current_time,
        description="'Util para obtener la hora actual."
    ),
    Tool(
        name="Cualculadora de Suma",
        func=calculate_sum,
        description="Suma una lista de numeros separados por espacios."
    )
]

# Configure the Gemini  model
llm = ChatGoogleGenerativeAI(
    model="gemini-2.0-flash",
    api_key=os.getenv("GENAI_API_KEY"),
    temperature=0.5
)

# Initialize the agent
agent = initialize_agent(
    tools=tools,
    llm=llm,
    agent=AgentType.CHAT_ZERO_SHOT_REACT_DESCRIPTION,
    verbose=True
)

# Start the agent
print(agent.invoke("Que hora es?"))
print(agent.invoke("Suma los siguientes numeros: 10,20,30,40 5"))