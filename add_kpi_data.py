#!/usr/bin/env python3
"""
Add example data to kpi_catalog table
"""

import psycopg2
from datetime import datetime

def main():
    # Database connection
    database_url = 'postgresql://postgres:SatoDB_92vN!fG7kAq4hRzLwYx2!PmE@34.165.111.32:5432/sato'
    
    try:
        conn = psycopg2.connect(database_url)
        cur = conn.cursor()
        
        # Add 3 example rows based on CSV data
        now = datetime.now()
        
        examples = [
            (1, 'ecommerce', 'Revenue', '["Transactions","Avg. Order Value"]', 'Conversion Rate', '["Sessions","Users"]', 'Users', '["New Users","Sessions"]', 'Engagement', '["Engaged Sessions","Avg. Engagement Time"]'),
            (2, 'leadgen', 'Leads Generated', '["Conversion Rate","Conversions"]', 'Traffic Volume', '["Users","Sessions"]', 'Sessions', '["Users","New Users"]', 'Engagement', '["Engaged Sessions","Event Count"]'),
            (3, 'content_blog', 'Engagement', '["Avg. Engagement Time","Page Views"]', 'Audience Growth', '["New Users","Returning Users"]', 'Engagement', '["Avg. Engagement Time","Page Views"]', 'Audience Growth', '["Users","Returning Users"]')
        ]
        
        for example in examples:
            cur.execute('''
                INSERT INTO kpi_catalog (
                    id, subtype, primary_metric, primary_submetrics, 
                    secondary_metric, secondary_submetrics, 
                    lite_primary_metric, lite_primary_submetrics, 
                    lite_secondary_metric, lite_secondary_submetrics,
                    created_at, updated_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ''', example + (now, now))
            print(f'✅ Added KPI catalog entry: {example[1]} - {example[2]}')
        
        conn.commit()
        print('✅ Successfully added 3 example rows to kpi_catalog table')
        
        # Verify
        cur.execute('SELECT COUNT(*) FROM kpi_catalog')
        count = cur.fetchone()[0]
        print(f'Total rows in kpi_catalog: {count}')
        
        # Show the data
        cur.execute('SELECT id, subtype, primary_metric, secondary_metric FROM kpi_catalog ORDER BY id')
        rows = cur.fetchall()
        print('\nKPI Catalog entries:')
        for row in rows:
            print(f'  {row[0]}. {row[1]} - Primary: {row[2]}, Secondary: {row[3]}')
        
        cur.close()
        conn.close()
        
    except Exception as e:
        print(f'❌ Error: {e}')
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())
