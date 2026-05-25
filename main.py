from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
import json
from pydantic import BaseModel


from fastapi import FastAPI, File, UploadFile, Body
import os
import shutil


from fastapi.middleware.cors import CORSMiddleware

from openai import OpenAI
from dotenv import load_dotenv
load_dotenv()

client = OpenAI(
    api_key=os.getenv("GROQ_API_KEY"),
    base_url="https://api.groq.com/openai/v1"
)

# Folder where PDFs will be stored
UPLOAD_DIR = "data/pdfs"

embeddings = HuggingFaceEmbeddings(
    model_name="BAAI/bge-small-en-v1.5"
)

app= FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def home():
    return { 'message' : 'working'}


@app.post("/upload")
async def upload(file: UploadFile = File(...)):

    file_path = os.path.join(UPLOAD_DIR, file.filename)

    # Save uploaded PDF
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # Load PDF using LangChain
    loader = PyPDFLoader(file_path)

    documents = loader.load()

    # Create text splitter
    text_splitter = RecursiveCharacterTextSplitter(
      chunk_size=200,
      chunk_overlap=50
    )

    # Split documents into chunks
    chunks = text_splitter.split_documents(documents)
    
    vector_store = FAISS.from_documents(
      chunks,
      embeddings
    )

    # Create vector store
    vector_store = FAISS.from_documents(chunks, embeddings)

    # Create folder if it doesn't exist
    VECTOR_DB_PATH = "data/vector_store"

    os.makedirs(VECTOR_DB_PATH, exist_ok=True)

    # Save FAISS vector database
    vector_store.save_local(VECTOR_DB_PATH)
    
    return {
    "message": "PDF processed successfully",
    "filename": file.filename,
    "total_pages": len(documents),
    "total_chunks": len(chunks),
    "vector_store_created": True
    }

# helper functions

def get_vector_store():

    #Load saved FAISS vector database
    vector_store = FAISS.load_local(
        "data/vector_store",
        embeddings,
        allow_dangerous_deserialization=True
    )

    return vector_store

# Perform similarity search
def retrieve_chunks(question, k=5):

    vector_store = get_vector_store()

    results = vector_store.similarity_search_with_score(
        question,
        k=20
    )

    prioritized_results = []

    # PRIORITIZE chunks containing query words
    for doc, score in results:

        content = doc.page_content.lower()

        if "future work" in content:
            prioritized_results.insert(0, (doc, score))

        else:
            prioritized_results.append((doc, score))

    return prioritized_results[:k]

@app.post("/query")
async def query_rag(question: str = Body(...)):

    results = retrieve_chunks(question)

    retrieved_chunks = [
     {
        "score": float(score),
        "content": doc.page_content
     }
    for doc, score in results
   ]

    return {
        "question": question,
        "retrieved_chunks": retrieved_chunks
    }



class QuestionRequest(BaseModel):
    question: str


@app.post("/ask")
async def ask_rag(request: QuestionRequest):

    question = request.question
    results = retrieve_chunks(question)

    context = "\n\n".join(
      [doc.page_content for doc, score in results[:3]]
    )

    sources = []

    for doc, score in results:

      sources.append({
        "page": doc.metadata.get("page", "N/A"),
        "content": doc.page_content[:300]
        
      })


    prompt = f"""
    You are a research paper assistant.

    Context:
    {context}

    Question:
    {question}

    Answer briefly:
    """

    response = client.chat.completions.create(

      model="llama-3.1-8b-instant",

      messages=[
        {
            "role": "user",
            "content": prompt,
            
        }
    ]
    )

    answer = response.choices[0].message.content

    return {
        "question": question,
        "answer": answer,
        "sources": sources
    }



@app.post("/compare")
async def compare_papers(
    file1: UploadFile = File(...),
    file2: UploadFile = File(...)
):

    # SAVE PDFS 

    file1_path = os.path.join(UPLOAD_DIR, file1.filename)
    file2_path = os.path.join(UPLOAD_DIR, file2.filename)

    with open(file1_path, "wb") as f:
        shutil.copyfileobj(file1.file, f)

    with open(file2_path, "wb") as f:
        shutil.copyfileobj(file2.file, f)


    # LOAD PDFs 

    loader1 = PyPDFLoader(file1_path)
    loader2 = PyPDFLoader(file2_path)

    docs1 = loader1.load()
    docs2 = loader2.load()


    # EXTRACT TEXT
    text1 = "\n".join([doc.page_content for doc in docs1])
    text2 = "\n".join([doc.page_content for doc in docs2])


    def extract_section(text, start_word, end_word):

      start = text.lower().find(start_word.lower())

      end = text.lower().find(end_word.lower())

      if start != -1 and end != -1:

        return text[start:end]

      return ""


    abstract1 = extract_section(
     text1,
     "abstract",
     "introduction"
    )

    conclusion1 = extract_section(
      text1,
      "conclusion",
      "references"
    )

    paper1_context = abstract1 + "\n\n" + conclusion1[:3000]

    abstract2 = extract_section(
     text2,
     "abstract",
     "introduction"
    )

    conclusion2 = extract_section(
     text2,
     "conclusion",
     "references"
    )

    paper2_context = abstract2 + "\n\n" + conclusion2[:3000]

    # CREATE PROMPT 

    prompt = f"""
    Compare these research papers.

    Paper 1: 
    {paper1_context}

    Paper 2:
    {paper2_context}

    Return ONLY valid JSON.

    Only include information explicitly supported by the provided paper sections.
    Do NOT invent assumptions, comparisons, or limitations.

    If some information is missing, write:
    "Not explicitly mentioned."

    {{
    "research_objective": {{
      "paper1": "",
      "paper2": ""
     }},
    "methodology": {{
      "paper1": "",
      "paper2": ""
     }},
    "contributions": {{
      "paper1": "",
      "paper2": ""
     }},
    "limitations": {{
      "paper1": "",
      "paper2": ""
     }}
    }}
    """


    # LLM RESPONSE 

    response = client.chat.completions.create(

        model="llama-3.1-8b-instant",

        messages=[
            {
                "role": "user",
                "content": prompt
            }
        ]
    )

    answer = response.choices[0].message.content

    print(answer)

    # Remove markdown formatting
    answer = answer.replace("```json", "")
    answer = answer.replace("```", "")
    answer = answer.strip()

    #  Find JSON boundaries
    start = answer.find("{")
    end = answer.rfind("}") + 1

    # Extract JSON only
    json_string = answer[start:end]

    # Convert to Python dictionary
    answer = json.loads(json_string)


    return {
        "paper1": file1.filename,
        "paper2": file2.filename,
        "comparison": answer
    }