import os
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain
from langchain_openai import ChatOpenAI
from langchain.memory import ConversationBufferMemory

from postfast.core.logger import logger

# Load environment variables
load_dotenv()

# Configure the Gemini  model

llm = ChatGoogleGenerativeAI(
    model="gemini-2.0-flash",
    api_key=os.getenv("GENAI_API_KEY"),
    temperature=0.5
)

logger.info("Model loaded successfully")

# Basic example of chat 
response = llm.invoke("¿Cuáles son los principales beneficios de usar LangChain?")
print(response.content)

# Create a prompt template
template = """Actúa como un experto en {tema}. Proporciona una explicación detallada sobre: {concepto}."""

# Create a prompt
prompt = PromptTemplate(
    input_variables=["tema", "concepto"],
    template=template
)

# Create a chain
chain = prompt | llm

# Execute the chain
response = chain.invoke({
    "tema": "ingeligencia artificial", 
    "concepto": "redes neuronales convolucionales"
})

print(response.content)

# Configure the memory -> we set the memory_key to chat_history to use this variable in the prompt. It stores the conversation history.

memory = ConversationBufferMemory(memory_key="chat_history", return_messages=True)

# Create a prompt template
template = """La siguiente es una conversacion amigable entre un humano y un asistente AI.
Historial de la conversacion:
{chat_history}
Humano: {input}
Asistente:"""

# Create a prompt
prompt = PromptTemplate(
    input_variables=["chat_history", "input"],
    template=template
)

conversation = LLMChain(
    llm=llm,
    memory=memory,
    prompt=prompt,
    verbose=True
)

print(conversation.predict(input="Que pais ha ganado mas mundiales de futbol?"))
print(conversation.predict(input="Nombrame 10 jugadores historicos de esa seleccion"))
print(conversation.predict(input="De que color era su camiseta?"))

# Sentiment analysis
sentiment_template = """Analiza el sentimiento del siguiente texto y clasif'ícalo como positivo, negativo o neutral. Proporciona también una explicación de tu análisis.

Texto: {texto}

Formato de respuesta:
Sentimiento: [clasificacion]
Explicacion: [tu análisis]
"""
sentiment_prompt = PromptTemplate(
    input_variables=["texto"],
    template=sentiment_template
)

logger.info("✅ Prompt template created successfully")

# Create the chain -> LLMChain is deprecated so we use the | operator to chain the prompts using the order: prompt | llm where prompt is the prompt template and llm is the language model. The prompt has to be the first element in the chain.
sentiment_chain = sentiment_prompt | llm

# Execute the chain
example_text = "El nuevo restaurante supero todas mis expectativas. La comida estaba deliciosa y el servicio fue excelente."

# Predict method is deprecated so we use the invoke method to execute the chain. The LangChain interface for Runnable objects recommends using the invoke method to execute the chain.
response = sentiment_chain.invoke({
    "texto": example_text
})

logger.info("✅ Chain executed successfully")

print(response.content)
