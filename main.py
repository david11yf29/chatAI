from fastapi import FastAPI

app = FastAPI()

@app.get("/hello/{input}")
async def hello(input: str):
    return {"message": f"Hello, World {input}"}
