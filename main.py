from fastapi import FastAPI
from pydantic import BaseModel
from openai import OpenAI
from dotenv import load_dotenv
import os

load_dotenv()

app = FastAPI()

client = OpenAI(
    api_key=os.getenv("SUPER_MIND_API_KEY"),
    base_url="https://space.ai-builders.com/backend/v1"
)

class ChatRequest(BaseModel):
    user_message: str

@app.get("/hello/{input}")
async def hello(input: str):
    return {"message": f"Hello, World {input}"}

@app.post("/chat")
async def chat(request: ChatRequest):
    response = client.chat.completions.create(
        model="gpt-5",
        messages=[
            {"role": "user", "content": request.user_message}
        ]
    )
    return {"response": response.choices[0].message.content}
