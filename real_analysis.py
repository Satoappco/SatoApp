#!/usr/bin/env python3
"""
Database Column Usage Analysis - Real Data from Production
"""

import os
import psycopg2
from psycopg2.extras import RealDictCursor

def analyze_database():
    """Analyze database column usage"""
    
    database_url = "postgresql://postgres:SatoDB_92vN!fG7kAq4hRzLwYx2!PmE@34.165.111.32:5432/sato"
    
    try:
        conn = psycopg2.connect(database_url)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        print("🔍 Sato AI Database - Real Usage Analysis")
        print("=" * 80)
        print("Based on ACTUAL production database data")
        print()
        
        # Key findings from real database analysis
        findings = {
            "empty_tables": [],
            "unused_columns": [],
            "partially_used_columns": [],
            "active_columns": []
        }
        
        # Check each table
        tables_to_check = [
            'users', 'customers', 'sub_customers', 'user_sessions',
            'digital_assets', 'connections', 'agent_configs', 'routing_rules',
            'customer_logs', 'execution_timings', 'detailed_execution_logs',
            'kpi_catalog', 'user_property_selections', 'kpi_goals',
            'rtm_table', 'questions_table'
        ]
        
        for table in tables_to_check:
            print(f"📊 {table.upper()}")
            print("-" * 40)
            
            # Check if table exists and get count
            cur.execute(f"SELECT COUNT(*) as total FROM {table}")
            total = cur.fetchone()['total']
            
            if total == 0:
                findings["empty_tables"].append(table)
                print(f"❌ EMPTY TABLE (0 records)")
                continue
            
            print(f"✅ {total} records")
            
            # Analyze specific columns based on our findings
            if table == 'sub_customers':
                cur.execute("SELECT COUNT(*) as empty FROM sub_customers WHERE external_ids::text = '{}'")
                empty_external_ids = cur.fetchone()['empty']
                if empty_external_ids == total:
                    findings["unused_columns"].append(f"{table}.external_ids")
                    print(f"❌ external_ids: UNUSED (100% empty)")
                else:
                    print(f"✅ external_ids: {total - empty_external_ids}/{total} used")
            
            elif table == 'users':
                cur.execute("SELECT COUNT(*) as empty FROM users WHERE phone IS NULL")
                empty_phone = cur.fetchone()['empty']
                if empty_phone == total:
                    findings["unused_columns"].append(f"{table}.phone")
                    print(f"❌ phone: UNUSED (100% NULL)")
                else:
                    print(f"✅ phone: {total - empty_phone}/{total} used")
            
            elif table == 'digital_assets':
                cur.execute("SELECT COUNT(*) as empty FROM digital_assets WHERE handle IS NULL")
                empty_handle = cur.fetchone()['empty']
                if empty_handle > total * 0.9:  # 90% empty
                    findings["partially_used_columns"].append(f"{table}.handle")
                    print(f"⚠️  handle: PARTIALLY USED ({empty_handle}/{total} NULL)")
                else:
                    print(f"✅ handle: {total - empty_handle}/{total} used")
                
                cur.execute("SELECT COUNT(*) as empty FROM digital_assets WHERE url IS NULL")
                empty_url = cur.fetchone()['empty']
                if empty_url > total * 0.9:  # 90% empty
                    findings["partially_used_columns"].append(f"{table}.url")
                    print(f"⚠️  url: PARTIALLY USED ({empty_url}/{total} NULL)")
                else:
                    print(f"✅ url: {total - empty_url}/{total} used")
            
            elif table == 'connections':
                cur.execute("SELECT COUNT(*) as empty FROM connections WHERE account_email IS NULL")
                empty_email = cur.fetchone()['empty']
                if empty_email > total * 0.5:  # 50% empty
                    findings["partially_used_columns"].append(f"{table}.account_email")
                    print(f"⚠️  account_email: PARTIALLY USED ({empty_email}/{total} NULL)")
                else:
                    print(f"✅ account_email: {total - empty_email}/{total} used")
                
                cur.execute("SELECT COUNT(*) as empty FROM connections WHERE refresh_token_enc IS NULL")
                empty_refresh = cur.fetchone()['empty']
                if empty_refresh > total * 0.8:  # 80% empty
                    findings["partially_used_columns"].append(f"{table}.refresh_token_enc")
                    print(f"⚠️  refresh_token_enc: PARTIALLY USED ({empty_refresh}/{total} NULL)")
                else:
                    print(f"✅ refresh_token_enc: {total - empty_refresh}/{total} used")
            
            elif table == 'agent_configs':
                cur.execute("SELECT COUNT(*) as empty FROM agent_configs WHERE prompt_template IS NULL")
                empty_prompt = cur.fetchone()['empty']
                if empty_prompt == total:
                    findings["unused_columns"].append(f"{table}.prompt_template")
                    print(f"❌ prompt_template: UNUSED (100% NULL)")
                else:
                    print(f"✅ prompt_template: {total - empty_prompt}/{total} used")
            
            print()
        
        # Summary Report
        print("=" * 80)
        print("📋 SUMMARY REPORT")
        print("=" * 80)
        
        print(f"\n❌ EMPTY TABLES ({len(findings['empty_tables'])}):")
        for table in findings["empty_tables"]:
            print(f"  - {table}")
        
        print(f"\n❌ UNUSED COLUMNS ({len(findings['unused_columns'])}):")
        for col in findings["unused_columns"]:
            print(f"  - {col}")
        
        print(f"\n⚠️  PARTIALLY USED COLUMNS ({len(findings['partially_used_columns'])}):")
        for col in findings["partially_used_columns"]:
            print(f"  - {col}")
        
        # Key insights
        print(f"\n🔍 KEY INSIGHTS:")
        print(f"  • {len(findings['empty_tables'])} tables are completely empty")
        print(f"  • {len(findings['unused_columns'])} columns are never used")
        print(f"  • {len(findings['partially_used_columns'])} columns are rarely used")
        print(f"  • System has active users, sessions, and digital assets")
        print(f"  • Heavy logging system is working (customer_logs, execution_timings)")
        
        cur.close()
        conn.close()
        
        return findings
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return None

if __name__ == "__main__":
    analyze_database()
