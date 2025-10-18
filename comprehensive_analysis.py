#!/usr/bin/env python3
"""
Comprehensive Database Column Analysis
"""

import os
import psycopg2
from psycopg2.extras import RealDictCursor

def analyze_all_columns():
    """Analyze all columns in all tables"""
    
    database_url = "postgresql://postgres:SatoDB_92vN!fG7kAq4hRzLwYx2!PmE@34.165.111.32:5432/sato"
    
    try:
        conn = psycopg2.connect(database_url)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        print("🔍 Comprehensive Database Analysis")
        print("=" * 80)
        
        # Get all tables
        cur.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            ORDER BY table_name
        """)
        tables = [row['table_name'] for row in cur.fetchall()]
        
        analysis_results = {}
        
        for table in tables:
            print(f"\n📊 {table.upper()} Table:")
            print("-" * 50)
            
            # Get total count
            cur.execute(f"SELECT COUNT(*) as total FROM {table}")
            total = cur.fetchone()['total']
            print(f"Total records: {total}")
            
            if total == 0:
                analysis_results[table] = {"status": "EMPTY", "columns": {}}
                print("❌ TABLE IS EMPTY")
                continue
            
            # Get column information
            cur.execute("""
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns 
                WHERE table_name = %s 
                ORDER BY ordinal_position
            """, (table,))
            columns = cur.fetchall()
            
            table_analysis = {"status": "ACTIVE", "total_records": total, "columns": {}}
            
            for col in columns:
                col_name = col['column_name']
                col_type = col['data_type']
                
                # Skip id, created_at, updated_at as they're always used
                if col_name in ['id', 'created_at', 'updated_at']:
                    table_analysis["columns"][col_name] = {"status": "✅ ACTIVE", "usage": "100%"}
                    continue
                
                # Check for NULL values
                cur.execute(f"SELECT COUNT(*) as null_count FROM {table} WHERE {col_name} IS NULL")
                null_count = cur.fetchone()['null_count']
                
                # Check for empty strings
                cur.execute(f"SELECT COUNT(*) as empty_count FROM {table} WHERE {col_name} = ''")
                empty_count = cur.fetchone()['empty_count']
                
                # Check for empty JSON
                empty_json_count = 0
                if 'json' in col_type.lower():
                    cur.execute(f"SELECT COUNT(*) as empty_json FROM {table} WHERE {col_name}::text = '{{}}' OR {col_name}::text = '[]'")
                    empty_json_count = cur.fetchone()['empty_json']
                
                # Calculate usage
                used_count = total - null_count - empty_count - empty_json_count
                usage_percentage = (used_count / total) * 100
                
                # Determine status
                if usage_percentage == 0:
                    status = "❌ UNUSED"
                elif usage_percentage < 10:
                    status = "⚠️  RARELY USED"
                elif usage_percentage < 50:
                    status = "⚠️  PARTIALLY USED"
                else:
                    status = "✅ ACTIVE"
                
                table_analysis["columns"][col_name] = {
                    "status": status,
                    "usage": f"{usage_percentage:.1f}%",
                    "used_count": used_count,
                    "total_count": total,
                    "null_count": null_count,
                    "empty_count": empty_count,
                    "empty_json_count": empty_json_count
                }
                
                print(f"  {col_name} ({col_type}): {status} - {usage_percentage:.1f}%")
                if usage_percentage > 0 and usage_percentage < 100:
                    print(f"    Used: {used_count}/{total}, NULL: {null_count}, Empty: {empty_count}, Empty JSON: {empty_json_count}")
            
            analysis_results[table] = table_analysis
        
        # Summary
        print("\n" + "=" * 80)
        print("📋 SUMMARY")
        print("=" * 80)
        
        unused_columns = []
        rarely_used_columns = []
        partially_used_columns = []
        active_columns = []
        empty_tables = []
        
        for table, analysis in analysis_results.items():
            if analysis["status"] == "EMPTY":
                empty_tables.append(table)
                continue
                
            for col_name, col_data in analysis["columns"].items():
                status = col_data["status"]
                if status == "❌ UNUSED":
                    unused_columns.append(f"{table}.{col_name}")
                elif status == "⚠️  RARELY USED":
                    rarely_used_columns.append(f"{table}.{col_name}")
                elif status == "⚠️  PARTIALLY USED":
                    partially_used_columns.append(f"{table}.{col_name}")
                else:
                    active_columns.append(f"{table}.{col_name}")
        
        print(f"\n❌ EMPTY TABLES ({len(empty_tables)}):")
        for table in empty_tables:
            print(f"  - {table}")
        
        print(f"\n❌ UNUSED COLUMNS ({len(unused_columns)}):")
        for col in unused_columns:
            print(f"  - {col}")
        
        print(f"\n⚠️  RARELY USED COLUMNS ({len(rarely_used_columns)}):")
        for col in rarely_used_columns:
            print(f"  - {col}")
        
        print(f"\n⚠️  PARTIALLY USED COLUMNS ({len(partially_used_columns)}):")
        for col in partially_used_columns:
            print(f"  - {col}")
        
        print(f"\n✅ ACTIVE COLUMNS ({len(active_columns)}):")
        for col in active_columns[:20]:  # Show first 20
            print(f"  - {col}")
        if len(active_columns) > 20:
            print(f"  ... and {len(active_columns) - 20} more")
        
        cur.close()
        conn.close()
        
        return analysis_results
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return None

if __name__ == "__main__":
    results = analyze_all_columns()
