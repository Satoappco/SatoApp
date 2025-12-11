"""
Update Master Agent to include Date & Timeframe Specialist delegation instructions
"""

from datetime import datetime, timezone
from sqlmodel import select
from app.config.database import get_session
from app.models.agents import AgentConfig


def update_master_agent_backstory():
    """Update master agent backstory to include date delegation instructions"""
    
    with get_session() as session:
        # Find master agent
        for master_type in ['seo_campaign_manager', 'master', 'seo_master', 'campaign_manager']:
            statement = select(AgentConfig).where(
                AgentConfig.name == master_type,
                AgentConfig.is_active == True
            )
            master_agent = session.exec(statement).first()
            
            if master_agent:
                print(f"\n✅ Found master agent: {master_agent.name}")
                print(f"\n{'='*80}")
                print("CURRENT BACKSTORY:")
                print(f"{'='*80}")
                print(master_agent.backstory)
                
                # Add date delegation instructions to backstory
                date_delegation_section = """

**Date & Timeframe Handling:**
When you encounter natural language date expressions (like "last 60 days", "this month", "yesterday", "Q1 2024"), you MUST delegate to the Date & Timeframe Specialist to convert them to YYYY-MM-DD format before passing to API specialists.

Process:
1. User mentions a timeframe → Delegate to "Date & Timeframe Specialist"
2. Receive formatted dates (start_date, end_date in YYYY-MM-DD)
3. Pass these formatted dates to the appropriate data specialist (Google Ads, Facebook Ads, GA4, etc.)

Examples:
- User: "Show Google Ads for last 60 days" 
  → First delegate: "Convert 'last 60 days' to YYYY-MM-DD format"
  → Then delegate to Google Ads specialist with the formatted dates

- User: "Compare this month vs last month"
  → First delegate: "Convert 'this month' and 'last month' to YYYY-MM-DD format"
  → Then delegate to appropriate specialist with both date ranges"""

                # Check if already has date delegation instructions
                if "Date & Timeframe Specialist" in master_agent.backstory:
                    print("\n⚠️  Master agent already has Date & Timeframe Specialist instructions")
                    print("Skipping update...")
                    return master_agent
                
                # Append to existing backstory
                updated_backstory = master_agent.backstory.strip() + date_delegation_section
                
                print(f"\n{'='*80}")
                print("NEW BACKSTORY:")
                print(f"{'='*80}")
                print(updated_backstory)
                
                # Update the agent
                master_agent.backstory = updated_backstory
                master_agent.updated_at = datetime.now(timezone.utc)
                
                # Ensure delegation is enabled
                if not master_agent.allow_delegation:
                    print("\n⚠️  Master agent delegation was DISABLED. Enabling it now...")
                    master_agent.allow_delegation = True
                
                session.add(master_agent)
                session.commit()
                session.refresh(master_agent)
                
                print(f"\n{'='*80}")
                print("✅ MASTER AGENT UPDATED SUCCESSFULLY!")
                print(f"{'='*80}")
                print(f"Agent ID: {master_agent.id}")
                print(f"Name: {master_agent.name}")
                print(f"Allow Delegation: {master_agent.allow_delegation}")
                print(f"Updated At: {master_agent.updated_at}")
                print(f"\n{'='*80}\n")
                
                return master_agent
        
        print("❌ No master agent found in database!")
        return None


if __name__ == "__main__":
    print("🚀 Updating Master Agent with Date & Timeframe Specialist instructions...")
    update_master_agent_backstory()
    print("\n✅ Done! Master agent now knows to delegate date parsing tasks.")

