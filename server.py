from fastapi import FastAPI
import main  # import your existing crewai logic here

app = FastAPI()

@app.get("/")
def health():
    return {"status": "ok"}

@app.get("/crew")
def run_crew():
    # maybe call functions from your existing main.py
    return {"result": "crew logic triggered"}