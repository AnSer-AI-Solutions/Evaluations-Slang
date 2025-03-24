#!/usr/bin/env python3
import json
import os
import psycopg2
from dotenv import load_dotenv
from datetime import datetime

# Load environment variables
load_dotenv()

# Database connection parameters
DB_HOST = os.getenv("DEV_DB_HOST")
DB_USER = os.getenv("DEV_DB_USER")
DB_PASS = os.getenv("DEV_DB_PASS")
DB_NAME = os.getenv("DEV_DB_NAME")

# JSON file path
JSON_FILE_PATH = "Validated_slang_dataset.json"

def main():
    # Read JSON data
    with open(JSON_FILE_PATH, 'r') as file:
        data = json.load(file)
    
    print(f"Loaded {len(data)} records from JSON file")
    
    # Connect to PostgreSQL
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASS
        )
        cursor = conn.cursor()
        
        # Insert data into the database
        records_inserted = 0
        for record in data:
            call_id = record.get('call_id')
            transcription = record.get('transcription')
            human_grade = record.get('human_grade')
            
            # Insert the record
            cursor.execute(
                """
                INSERT INTO slang.transcriptions_gemini 
                (call_id, transcription, human_grade)
                VALUES (%s, %s, %s)
                ON CONFLICT (call_id) DO UPDATE 
                SET transcription = EXCLUDED.transcription,
                    human_grade = EXCLUDED.human_grade
                """,
                (call_id, transcription, human_grade)
            )
            records_inserted += 1
        
        # Commit the transaction
        conn.commit()
        print(f"Successfully inserted {records_inserted} records into the database")
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        if conn:
            cursor.close()
            conn.close()
            print("Database connection closed")

if __name__ == "__main__":
    main()