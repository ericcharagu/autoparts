from sre_parse import MAX_REPEAT
from ollama import AsyncClient
from dotenv import load_dotenv
import os

#Load environment
load_dotenv()


def ollama_embedding():
    #return AsyncClient(os.getenv("OLLAMA_HOST"))
    return AsyncClient("http://ollama_embedding:11434")
    
def ollama_llm():
    return AsyncClient(os.getenv("OLLAMA_HOST"))

embedding_client=ollama_embedding()
llm_client=ollama_llm()

MAX_RESULTS:int=3