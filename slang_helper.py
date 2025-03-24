import os
import psycopg2
import json
from dotenv import load_dotenv
from datetime import datetime

# Load environment variables
load_dotenv()

def get_db_connection():
    """Create a connection to the PostgreSQL database"""
    conn = psycopg2.connect(
        host=os.getenv('DEV_DB_HOST'),
        user=os.getenv('DEV_DB_USER'),
        password=os.getenv('DEV_DB_PASS'),
        dbname=os.getenv('DEV_DB_NAME')
    )
    return conn

def get_max_transcription_id():
    """Get the highest transcription_id from the evaluation_gemini table"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("SELECT COALESCE(MAX(transcription_id), 0) FROM slang.evaluation_gemini")
        max_id = cursor.fetchone()[0]
        return max_id
    except Exception as e:
        print(f"Error getting max transcription_id: {e}")
        return 0
    finally:
        cursor.close()
        conn.close()

def get_transcription_cursor(limit=None, offset=0, order_by="call_id"):
    """Get a server-side cursor for transcriptions that fetches records one at a time
    
    Args:
        limit (int, optional): Maximum number of transcriptions to fetch. Default is None (all entries).
        offset (int, optional): Number of records to skip. Default is 0.
        order_by (str, optional): Column to order by. Default is "call_id".
        
    Returns:
        tuple: (connection, cursor) - Keep the connection open until done with cursor
    """
    conn = get_db_connection()
    # Use server-side cursor to avoid loading all records into memory
    cursor = conn.cursor(name='transcriptions_cursor')
    
    query = f"SELECT call_id, transcription FROM slang.transcriptions_gemini ORDER BY {order_by}"
    
    if offset > 0:
        query += f" OFFSET {offset}"
        
    if limit is not None:
        query += f" LIMIT {limit}"
        
    cursor.execute(query)
    return conn, cursor

def get_unprocessed_transcription_cursor(limit=None, order_by="call_id"):
    """Get a cursor for transcriptions that haven't been processed yet
    
    This uses a JOIN to exclude records that have already been processed,
    which is much more efficient than loading all processed IDs into memory.
    
    Args:
        limit (int, optional): Maximum number of transcriptions to fetch. Default is None (all entries).
        order_by (str, optional): Column to order by. Default is "call_id".
        
    Returns:
        tuple: (connection, cursor) - Keep the connection open until done with cursor
    """
    conn = get_db_connection()
    cursor = conn.cursor(name='unprocessed_cursor')
    
    # This query selects transcriptions that don't have matching call_id in the evaluation table
    query = f"""
    SELECT t.call_id, t.transcription 
    FROM slang.transcriptions_gemini t
    LEFT JOIN slang.evaluation_gemini e ON t.call_id = e.call_id
    WHERE e.call_id IS NULL
    ORDER BY t.{order_by}
    """
    
    if limit is not None:
        query += f" LIMIT {limit}"
        
    cursor.execute(query)
    return conn, cursor

def get_total_transcription_count():
    """Get the total number of records in the transcriptions_gemini table"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("SELECT COUNT(*) FROM slang.transcriptions_gemini")
        count = cursor.fetchone()[0]
        return count
    except Exception as e:
        print(f"Error getting transcription count: {e}")
        return 0
    finally:
        cursor.close()
        conn.close()

def get_unprocessed_count():
    """Get the count of unprocessed records"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        query = """
        SELECT COUNT(*) 
        FROM slang.transcriptions_gemini t
        LEFT JOIN slang.evaluation_gemini e ON t.call_id = e.call_id
        WHERE e.call_id IS NULL
        """
        cursor.execute(query)
        count = cursor.fetchone()[0]
        return count
    except Exception as e:
        print(f"Error getting unprocessed count: {e}")
        return 0
    finally:
        cursor.close()
        conn.close()

def insert_evaluation(evaluation_data):
    """Insert evaluation data into the evaluation_gemini table"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    insert_query = """
    INSERT INTO slang.evaluation_gemini (
        transcription_id, call_id, intern_ai_grade, score, max_score, 
        criteria, passed, explanation, improvement_suggestion, 
        found_references, context, original_transcription
    ) VALUES (
        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
    )
    """
    
    cursor.execute(insert_query, (
        evaluation_data['transcription_id'],
        evaluation_data['call_id'],
        evaluation_data['intern_ai_grade'],
        evaluation_data['score'],
        evaluation_data['max_score'],
        evaluation_data['criteria'],
        evaluation_data['passed'],
        evaluation_data['explanation'],
        evaluation_data['improvement_suggestion'],
        json.dumps(evaluation_data['found_references']),
        evaluation_data['context'],
        evaluation_data['original_transcription']
    ))
    
    conn.commit()
    cursor.close()
    conn.close()