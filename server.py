from fastapi import FastAPI
from pydantic import BaseModel
from crewai import Agent, Crew

app = FastAPI()

# ---- Health check ----
@app.get("/")
def health():
    return {"status": "ok"}


# ---- Define your agents and crew ONCE ----
researcher = Agent(
    name="Researcher",
    role="Research",
    goal="Answer user queries with useful information"
)

crew = Crew(agents=[researcher])


# ---- Input model ----
class CrewRequest(BaseModel):
    prompt: str


# ---- Endpoint ----
@app.post("/crew")
def run_crew(request: CrewRequest):
    result = crew.kickoff(inputs={"topic": request.prompt})
    return {"result": str(result)}
