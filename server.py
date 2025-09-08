from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import traceback

app = FastAPI()

# Health check
@app.get("/")
def health():
    return {"status": "ok"}

# Request schema
class CrewRequest(BaseModel):
    prompt: str

# Crew endpoint
@app.post("/crew")
def run_crew(req: CrewRequest):
    try:
        # Lazy import so startup never fails if CrewAI isn't present/ready
        from crewai import Agent, Crew, Process

        # Minimal, valid agent (include required fields like backstory)
        researcher = Agent(
            name="Researcher",
            role="Research",
            goal="Answer user queries with useful information",
            backstory="An experienced analyst who writes concise, helpful answers.",
            verbose=True,
        )

        crew = Crew(
            agents=[researcher],
            process=Process.sequential  # optional; keep it simple
        )

        result = crew.kickoff(inputs={"topic": req.prompt})
        return {"result": str(result)}

    except Exception as e:
        # Don't crash the container—return a 500 with the error
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
