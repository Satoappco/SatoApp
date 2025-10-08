"""
Complete setup for Date & Timeframe Specialist
This script:
1. Adds the Date & Timeframe Specialist agent
2. Updates the Master Agent to delegate date parsing
3. Enables delegation for Google Ads and Facebook Ads specialists
"""

import asyncio
from datetime import datetime
from sqlmodel import select
from app.config.database import get_session
from app.models.agents import AgentConfig


def add_date_specialist():
    """Add Date & Timeframe Specialist agent"""
    
    agent_data = {
        "agent_type": "date_timeframe_specialist",
        "name": "Date & Timeframe Specialist",
        "role": "Date and timeframe conversion expert",
        "goal": "Convert natural language timeframes (like 'last 60 days', 'this month', 'yesterday') into precise YYYY-MM-DD date formats required by different marketing analytics APIs (Google Ads, Facebook Ads, GA4, etc.)",
        "backstory": """You are a specialized agent that understands date expressions and timeframes. 
You excel at interpreting user requests like "last 60 days", "this quarter", "last week", "yesterday", 
or any natural date expression and converting them to the exact YYYY-MM-DD format required by various 
marketing APIs. You understand different calendar systems, business quarters, and can handle relative 
dates. You always return clear, unambiguous date ranges.""",
        "task": """Convert the timeframe "{timeframe}" into start_date and end_date in YYYY-MM-DD format. 

Current date context: Today is {current_date}.

Provide your response ONLY in this exact JSON format:
{{
  "start_date": "YYYY-MM-DD",
  "end_date": "YYYY-MM-DD",
  "interpretation": "Brief explanation of what date range this represents"
}}

Examples:
- "last 60 days" → start_date: 60 days before today, end_date: today
- "this month" → start_date: first day of current month, end_date: today
- "Q1 2024" → start_date: "2024-01-01", end_date: "2024-03-31"
- "yesterday" → start_date: yesterday, end_date: yesterday
- "last week" → start_date: 7 days ago, end_date: today""",
        "allow_delegation": False,
        "verbose": True,
        "is_active": True,
        "max_iterations": 1
    }
    
    with get_session() as session:
        statement = select(AgentConfig).where(AgentConfig.agent_type == agent_data["agent_type"])
        existing_agent = session.exec(statement).first()
        
        if existing_agent:
            print(f"📝 Date Specialist already exists (ID: {existing_agent.id}). Skipping creation...")
            return existing_agent
        else:
            print(f"✨ Creating Date & Timeframe Specialist...")
            agent = AgentConfig(**agent_data)
            session.add(agent)
            session.commit()
            session.refresh(agent)
            print(f"✅ Date Specialist created (ID: {agent.id})")
            return agent


def update_master_agent():
    """Update master agent with date delegation instructions"""
    
    with get_session() as session:
        for master_type in ['seo_campaign_manager', 'master', 'seo_master', 'campaign_manager']:
            statement = select(AgentConfig).where(
                AgentConfig.agent_type == master_type,
                AgentConfig.is_active == True
            )
            master_agent = session.exec(statement).first()
            
            if master_agent:
                print(f"\n📋 Found master agent: {master_agent.name}")
                
                # Check if already updated
                if "Date & Timeframe Specialist" in master_agent.backstory:
                    print("✅ Master agent already has date delegation instructions")
                    return master_agent
                
                # Add date delegation instructions
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

                master_agent.backstory = master_agent.backstory.strip() + date_delegation_section
                master_agent.allow_delegation = True
                master_agent.updated_at = datetime.utcnow()
                
                session.add(master_agent)
                session.commit()
                session.refresh(master_agent)
                
                print(f"✅ Master agent updated with date delegation instructions")
                return master_agent
        
        print("❌ No master agent found!")
        return None


def enable_specialist_delegation():
    """Enable delegation for Google Ads and Facebook Ads specialists"""
    
    specialist_types = [
        'google_ads_expert',
        'google_database_analysis_expert',
        'paid_media_expert',
        'facebook_ads',
        'facebook_database_analysis_expert',
        'meta_ads_expert',
        'social_media_expert'
    ]
    
    with get_session() as session:
        updated_count = 0
        
        for specialist_type in specialist_types:
            statement = select(AgentConfig).where(
                AgentConfig.agent_type == specialist_type,
                AgentConfig.is_active == True
            )
            specialist = session.exec(statement).first()
            
            if specialist and not specialist.allow_delegation:
                specialist.allow_delegation = True
                specialist.updated_at = datetime.utcnow()
                session.add(specialist)
                updated_count += 1
                print(f"✅ Enabled delegation for: {specialist.name}")
        
        if updated_count > 0:
            session.commit()
            print(f"\n✅ Updated {updated_count} specialists to allow delegation")
        else:
            print("\n✅ All specialists already have delegation enabled")


def verify_setup():
    """Verify the complete setup"""
    
    print(f"\n{'='*80}")
    print("VERIFICATION")
    print(f"{'='*80}\n")
    
    with get_session() as session:
        # Check Date Specialist
        statement = select(AgentConfig).where(
            AgentConfig.agent_type == 'date_timeframe_specialist',
            AgentConfig.is_active == True
        )
        date_specialist = session.exec(statement).first()
        
        if date_specialist:
            print(f"✅ Date & Timeframe Specialist: Active (ID: {date_specialist.id})")
        else:
            print(f"❌ Date & Timeframe Specialist: NOT FOUND")
        
        # Check Master Agent
        master_found = False
        for master_type in ['seo_campaign_manager', 'master', 'seo_master', 'campaign_manager']:
            statement = select(AgentConfig).where(
                AgentConfig.agent_type == master_type,
                AgentConfig.is_active == True
            )
            master_agent = session.exec(statement).first()
            
            if master_agent:
                has_date_instructions = "Date & Timeframe Specialist" in master_agent.backstory
                delegation_enabled = master_agent.allow_delegation
                
                status = "✅" if (has_date_instructions and delegation_enabled) else "⚠️"
                print(f"{status} Master Agent ({master_type}):")
                print(f"   - Has date instructions: {has_date_instructions}")
                print(f"   - Delegation enabled: {delegation_enabled}")
                master_found = True
                break
        
        if not master_found:
            print(f"❌ Master Agent: NOT FOUND")
        
        # Check Specialists
        specialist_types = [
            'google_ads_expert',
            'google_database_analysis_expert',
            'facebook_ads',
            'facebook_database_analysis_expert'
        ]
        
        print(f"\n📊 Specialists with delegation:")
        for specialist_type in specialist_types:
            statement = select(AgentConfig).where(
                AgentConfig.agent_type == specialist_type,
                AgentConfig.is_active == True
            )
            specialist = session.exec(statement).first()
            
            if specialist:
                status = "✅" if specialist.allow_delegation else "❌"
                print(f"{status} {specialist.name}: {specialist.allow_delegation}")
    
    print(f"\n{'='*80}\n")


def main():
    """Run complete setup"""
    
    print(f"\n{'='*80}")
    print("DATE & TIMEFRAME SPECIALIST - COMPLETE SETUP")
    print(f"{'='*80}\n")
    
    print("Step 1: Adding Date & Timeframe Specialist...")
    add_date_specialist()
    
    print("\nStep 2: Updating Master Agent...")
    update_master_agent()
    
    print("\nStep 3: Enabling delegation for specialists...")
    enable_specialist_delegation()
    
    print("\nStep 4: Verifying setup...")
    verify_setup()
    
    print(f"{'='*80}")
    print("✅ SETUP COMPLETE!")
    print(f"{'='*80}\n")
    print("Your agents are now configured to:")
    print("1. Understand natural language date expressions")
    print("2. Delegate date conversion to the Date Specialist")
    print("3. Use properly formatted dates in API calls")
    print("\nNext steps:")
    print("- Test with: 'Show Google Ads data for last 60 days'")
    print("- Deploy: cd SatoApp && ./deploy-fast.sh")
    print(f"\n{'='*80}\n")


if __name__ == "__main__":
    main()

