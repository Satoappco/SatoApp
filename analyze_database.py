#!/usr/bin/env python3
"""
Database Analysis Script - Check for empty/unused columns
"""

import os
import sys
import json
from datetime import datetime
import psycopg2
from psycopg2.extras import RealDictCursor

def get_database_connection():
    """Get database connection from environment"""
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        print("❌ DATABASE_URL not found in environment")
        print("Please set DATABASE_URL environment variable")
        return None
    
    try:
        conn = psycopg2.connect(database_url)
        return conn
    except Exception as e:
        print(f"❌ Failed to connect to database: {e}")
        return None

def analyze_table_column_usage(conn, table_name, columns_info):
    """Analyze usage of columns in a table"""
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    print(f"\n📊 Analyzing table: {table_name}")
    print("=" * 60)
    
    # Get total count
    cur.execute(f"SELECT COUNT(*) as total FROM {table_name}")
    total_count = cur.fetchone()['total']
    
    if total_count == 0:
        print(f"❌ Table {table_name} is EMPTY (0 records)")
        return
    
    print(f"📈 Total records: {total_count}")
    print()
    
    column_analysis = {}
    
    for column_info in columns_info:
        column_name = column_info['name']
        column_type = column_info['type']
        
        # Check for NULL values
        cur.execute(f"SELECT COUNT(*) as null_count FROM {table_name} WHERE {column_name} IS NULL")
        null_count = cur.fetchone()['null_count']
        
        # Check for empty strings
        cur.execute(f"SELECT COUNT(*) as empty_count FROM {table_name} WHERE {column_name} = ''")
        empty_count = cur.fetchone()['empty_count']
        
        # Check for empty JSON objects/arrays
        empty_json_count = 0
        if 'json' in column_type.lower():
            cur.execute(f"SELECT COUNT(*) as empty_json_count FROM {table_name} WHERE {column_name} = '{{}}' OR {column_name} = '[]'")
            empty_json_count = cur.fetchone()['empty_json_count']
        
        # Calculate usage percentage
        used_count = total_count - null_count - empty_count - empty_json_count
        usage_percentage = (used_count / total_count) * 100 if total_count > 0 else 0
        
        # Determine status
        if usage_percentage == 0:
            status = "❌ UNUSED"
        elif usage_percentage < 10:
            status = "⚠️  RARELY USED"
        elif usage_percentage < 50:
            status = "⚠️  PARTIALLY USED"
        else:
            status = "✅ ACTIVE"
        
        column_analysis[column_name] = {
            'total': total_count,
            'null_count': null_count,
            'empty_count': empty_count,
            'empty_json_count': empty_json_count,
            'used_count': used_count,
            'usage_percentage': usage_percentage,
            'status': status
        }
        
        print(f"  {column_name} ({column_type}):")
        print(f"    Status: {status}")
        print(f"    Usage: {used_count}/{total_count} ({usage_percentage:.1f}%)")
        print(f"    NULL: {null_count}, Empty: {empty_count}, Empty JSON: {empty_json_count}")
        
        # Show sample values for active columns
        if usage_percentage > 0:
            cur.execute(f"SELECT DISTINCT {column_name} FROM {table_name} WHERE {column_name} IS NOT NULL AND {column_name} != '' AND {column_name} != '{{}}' AND {column_name} != '[]' LIMIT 3")
            samples = cur.fetchall()
            if samples:
                sample_values = [str(row[column_name])[:50] + "..." if len(str(row[column_name])) > 50 else str(row[column_name]) for row in samples]
                print(f"    Samples: {', '.join(sample_values)}")
        print()
    
    cur.close()
    return column_analysis

def get_table_columns(conn, table_name):
    """Get column information for a table"""
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    query = """
    SELECT 
        column_name as name,
        data_type as type,
        is_nullable,
        column_default
    FROM information_schema.columns 
    WHERE table_name = %s 
    ORDER BY ordinal_position
    """
    
    cur.execute(query, (table_name,))
    columns = cur.fetchall()
    cur.close()
    
    return columns

def analyze_all_tables():
    """Analyze all tables in the database"""
    conn = get_database_connection()
    if not conn:
        return
    
    print("🔍 Sato AI Database Analysis")
    print("=" * 80)
    print(f"Analysis started at: {datetime.now()}")
    print()
    
    # Define tables to analyze (only active tables)
    tables_to_analyze = [
        'campaigners',
        'agencies', 
        'customers',
        'campaigner_sessions',
        'digital_assets',
        'connections',
        'agent_configs',
        'routing_rules',
        'customer_logs',
        'execution_timings',
        'detailed_execution_logs',
        'kpi_catalog',
        'user_property_selections',
        'kpi_goals',
        'rtm_table',
        'questions_table'
    ]
    
    all_analysis = {}
    
    for table_name in tables_to_analyze:
        try:
            # Check if table exists
            cur = conn.cursor()
            cur.execute("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = %s)", (table_name,))
            table_exists = cur.fetchone()[0]
            cur.close()
            
            if not table_exists:
                print(f"⚠️  Table {table_name} does not exist, skipping...")
                continue
            
            # Get column information
            columns_info = get_table_columns(conn, table_name)
            
            if not columns_info:
                print(f"⚠️  No columns found for table {table_name}")
                continue
            
            # Analyze the table
            analysis = analyze_table_column_usage(conn, table_name, columns_info)
            all_analysis[table_name] = analysis
            
        except Exception as e:
            print(f"❌ Error analyzing table {table_name}: {e}")
            continue
    
    # Summary report
    print("\n" + "=" * 80)
    print("📋 SUMMARY REPORT")
    print("=" * 80)
    
    unused_columns = []
    rarely_used_columns = []
    partially_used_columns = []
    active_columns = []
    
    for table_name, analysis in all_analysis.items():
        if not analysis:
            continue
            
        for column_name, data in analysis.items():
            if data['status'] == "❌ UNUSED":
                unused_columns.append(f"{table_name}.{column_name}")
            elif data['status'] == "⚠️  RARELY USED":
                rarely_used_columns.append(f"{table_name}.{column_name}")
            elif data['status'] == "⚠️  PARTIALLY USED":
                partially_used_columns.append(f"{table_name}.{column_name}")
            else:
                active_columns.append(f"{table_name}.{column_name}")
    
    print(f"\n✅ ACTIVE COLUMNS ({len(active_columns)}):")
    for col in active_columns[:10]:  # Show first 10
        print(f"  - {col}")
    if len(active_columns) > 10:
        print(f"  ... and {len(active_columns) - 10} more")
    
    print(f"\n⚠️  PARTIALLY USED COLUMNS ({len(partially_used_columns)}):")
    for col in partially_used_columns:
        print(f"  - {col}")
    
    print(f"\n⚠️  RARELY USED COLUMNS ({len(rarely_used_columns)}):")
    for col in rarely_used_columns:
        print(f"  - {col}")
    
    print(f"\n❌ UNUSED COLUMNS ({len(unused_columns)}):")
    for col in unused_columns:
        print(f"  - {col}")
    
    # Save detailed analysis to file
    with open('database_analysis_report.json', 'w') as f:
        json.dump(all_analysis, f, indent=2, default=str)
    
    print(f"\n💾 Detailed analysis saved to: database_analysis_report.json")
    
    conn.close()
    print(f"\n✅ Analysis completed at: {datetime.now()}")

if __name__ == "__main__":
    analyze_all_tables()
