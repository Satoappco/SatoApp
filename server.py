from fastapi import FastAPI
import main  # import your existing crewai logic here
from pydantic import BaseModel
from crewai import Agent, Crew  # adjust if your repo uses different imports

app = FastAPI()

# ---- Health check ----
@app.get("/")
def health():
    return {"status": "ok"}
    
# ---- Request schema for crew ----
class CrewRequest(BaseModel):
    prompt: str

# ---- Crew endpoint ----
@app.post("/crew")
def run_crew(request: CrewRequest):
    # Example: a single agent crew (replace with your actual crew setup)
    agent = Agent(
        name="Researcher",
        role="Research",
        goal="Answer user queries with useful information"
    )

    crew = Crew(agents=[agent])

    # Kickoff with user input
    result = crew.kickoff(inputs={"topic": request.prompt})

    return {"result": str(result)}
