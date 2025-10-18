#!/usr/bin/env python3
"""
Simple Database Column Analysis
"""

import os
import psycopg2
from psycopg2.extras import RealDictCursor

def analyze_specific_tables():
    """Analyze specific tables for empty columns"""
    
    database_url = "postgresql://postgres:SatoDB_92vN!fG7kAq4hRzLwYx2!PmE@34.165.111.32:5432/sato"
    
    try:
        conn = psycopg2.connect(database_url)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        print("🔍 Database Column Analysis")
        print("=" * 50)
        
        # Analyze sub_customers table
        print("\n📊 SUB_CUSTOMERS Table:")
        cur.execute("SELECT COUNT(*) as total FROM sub_customers")
        total = cur.fetchone()['total']
        print(f"Total records: {total}")
        
        if total > 0:
            # Check external_ids column
            cur.execute("SELECT COUNT(*) as empty FROM sub_customers WHERE external_ids::text = '{}' OR external_ids IS NULL")
            empty_external_ids = cur.fetchone()['empty']
            print(f"Empty external_ids: {empty_external_ids}/{total} ({empty_external_ids/total*100:.1f}%)")
            
            # Check other columns
            cur.execute("SELECT COUNT(*) as empty FROM sub_customers WHERE timezone IS NULL")
            empty_timezone = cur.fetchone()['empty']
            print(f"Empty timezone: {empty_timezone}/{total} ({empty_timezone/total*100:.1f}%)")
            
            cur.execute("SELECT COUNT(*) as empty FROM sub_customers WHERE budget_monthly IS NULL")
            empty_budget = cur.fetchone()['empty']
            print(f"Empty budget_monthly: {empty_budget}/{total} ({empty_budget/total*100:.1f}%)")
            
            cur.execute("SELECT COUNT(*) as empty FROM sub_customers WHERE notes IS NULL")
            empty_notes = cur.fetchone()['empty']
            print(f"Empty notes: {empty_notes}/{total} ({empty_notes/total*100:.1f}%)")
        
        # Analyze users table
        print("\n📊 USERS Table:")
        cur.execute("SELECT COUNT(*) as total FROM users")
        total_users = cur.fetchone()['total']
        print(f"Total records: {total_users}")
        
        if total_users > 0:
            cur.execute("SELECT COUNT(*) as empty FROM users WHERE phone IS NULL")
            empty_phone = cur.fetchone()['empty']
            print(f"Empty phone: {empty_phone}/{total_users} ({empty_phone/total_users*100:.1f}%)")
            
            cur.execute("SELECT COUNT(*) as empty FROM users WHERE google_id IS NULL")
            empty_google_id = cur.fetchone()['empty']
            print(f"Empty google_id: {empty_google_id}/{total_users} ({empty_google_id/total_users*100:.1f}%)")
            
            cur.execute("SELECT COUNT(*) as empty FROM users WHERE avatar_url IS NULL")
            empty_avatar = cur.fetchone()['empty']
            print(f"Empty avatar_url: {empty_avatar}/{total_users} ({empty_avatar/total_users*100:.1f}%)")
        
        # Analyze digital_assets table
        print("\n📊 DIGITAL_ASSETS Table:")
        cur.execute("SELECT COUNT(*) as total FROM digital_assets")
        total_assets = cur.fetchone()['total']
        print(f"Total records: {total_assets}")
        
        if total_assets > 0:
            cur.execute("SELECT COUNT(*) as empty FROM digital_assets WHERE handle IS NULL")
            empty_handle = cur.fetchone()['empty']
            print(f"Empty handle: {empty_handle}/{total_assets} ({empty_handle/total_assets*100:.1f}%)")
            
            cur.execute("SELECT COUNT(*) as empty FROM digital_assets WHERE url IS NULL")
            empty_url = cur.fetchone()['empty']
            print(f"Empty url: {empty_url}/{total_assets} ({empty_url/total_assets*100:.1f}%)")
        
        # Analyze connections table
        print("\n📊 CONNECTIONS Table:")
        cur.execute("SELECT COUNT(*) as total FROM connections")
        total_connections = cur.fetchone()['total']
        print(f"Total records: {total_connections}")
        
        if total_connections > 0:
            cur.execute("SELECT COUNT(*) as empty FROM connections WHERE account_email IS NULL")
            empty_email = cur.fetchone()['empty']
            print(f"Empty account_email: {empty_email}/{total_connections} ({empty_email/total_connections*100:.1f}%)")
            
            cur.execute("SELECT COUNT(*) as empty FROM connections WHERE refresh_token_enc IS NULL")
            empty_refresh = cur.fetchone()['empty']
            print(f"Empty refresh_token_enc: {empty_refresh}/{total_connections} ({empty_refresh/total_connections*100:.1f}%)")
            
            cur.execute("SELECT COUNT(*) as empty FROM connections WHERE rotated_at IS NULL")
            empty_rotated = cur.fetchone()['empty']
            print(f"Empty rotated_at: {empty_rotated}/{total_connections} ({empty_rotated/total_connections*100:.1f}%)")
        
        # Check empty tables
        print("\n📊 EMPTY TABLES:")
        empty_tables = []
        tables_to_check = [
            'kpi_catalog', 'kpi_goals', 'rtm_table', 'questions_table'
        ]
        
        for table in tables_to_check:
            cur.execute(f"SELECT COUNT(*) as total FROM {table}")
            count = cur.fetchone()['total']
            if count == 0:
                empty_tables.append(table)
                print(f"  ❌ {table}: 0 records")
            else:
                print(f"  ✅ {table}: {count} records")
        
        cur.close()
        conn.close()
        
        print(f"\n✅ Analysis completed!")
        
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    analyze_specific_tables()
