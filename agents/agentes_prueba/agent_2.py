import os
from dotenv import load_dotenv
from langchain_community.vectorstores import FAISS
from langchain_community.document_loaders import TextLoader
from langchain.text_splitter import CharacterTextSplitter
from langchain_google_genai import GoogleGenerativeAIEmbeddings

# Load environment variables
load_dotenv()

# Load the example file and process it
loader = TextLoader('example.txt', encoding='utf-8')
documents = loader.load() # It saves the content of the file in a list of documents, each document is an item in the list

#print (documents[0].content)

# Split the text into smaller chunks
text_splitter = CharacterTextSplitter(chunk_size=200, chunk_overlap=20)
texts = text_splitter.split_documents(documents)

# Create embeddings
embeddings = GoogleGenerativeAIEmbeddings(
    model="models/embedding-001",
    google_api_key=os.getenv("GENAI_API_KEY")
)

# Create the vector database
db = FAISS.from_documents(texts, embeddings)

# Query the database
query = "¿qué es LangChain?"
docs = db.similarity_search(query)
print(docs[0].page_content)