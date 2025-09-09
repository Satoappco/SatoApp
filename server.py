from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import traceback
from datetime import datetime
import os

app = FastAPI(
    title="Sato AI Crew API",
    description="Multi-agent AI system powered by CrewAI for research and reporting",
    version="1.0.0"
)

# Health check
@app.get("/")
def health():
    return {
        "status": "ok", 
        "service": "Sato AI Crew API",
        "timestamp": datetime.utcnow().isoformat()
    }

# Request schemas
class CrewRequest(BaseModel):
    topic: str
    current_year: str = str(datetime.now().year)

class CrewResponse(BaseModel):
    result: str
    topic: str
    execution_time: float
    timestamp: str

# Sato Crew endpoint - uses your actual crew configuration
@app.post("/crew", response_model=CrewResponse)
def run_sato_crew(req: CrewRequest):
    """
    Run the Sato AI crew with your configured agents and tasks
    """
    start_time = datetime.utcnow()
    
    try:
        # Import your actual Sato crew
        from src.sato.crew import Sato
        
        # Create inputs for the crew
        inputs = {
            'topic': req.topic,
            'current_year': req.current_year
        }
        
        # Initialize and run your actual Sato crew
        sato_crew = Sato()
        result = sato_crew.crew().kickoff(inputs=inputs)
        
        # Calculate execution time
        end_time = datetime.utcnow()
        execution_time = (end_time - start_time).total_seconds()
        
        return CrewResponse(
            result=str(result),
            topic=req.topic,
            execution_time=execution_time,
            timestamp=end_time.isoformat()
        )

    except Exception as e:
        # Don't crash the container—return a 500 with the error
        traceback.print_exc()
        raise HTTPException(
            status_code=500, 
            detail=f"Crew execution failed: {str(e)}"
        )

# Alternative endpoint for simple prompts (backward compatibility)
@app.post("/crew/simple")
def run_crew_simple(req: CrewRequest):
    """
    Simple crew endpoint that returns just the result string
    """
    try:
        from src.sato.crew import Sato
        
        inputs = {
            'topic': req.topic,
            'current_year': req.current_year
        }
        
        sato_crew = Sato()
        result = sato_crew.crew().kickoff(inputs=inputs)
        
        return {"result": str(result)}

    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
