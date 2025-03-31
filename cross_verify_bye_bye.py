import re
import os
import psycopg2
import json
from dotenv import load_dotenv
from slang import extract_agent_lines, SLANG_WORDS, SLANG_ALTERNATIVES
from slang_helper import get_db_connection

# Load environment variables
load_dotenv()

def get_senna_db_connection():
    """Create a connection to the Senna PostgreSQL database"""
    conn = psycopg2.connect(
        host=os.getenv('PRODUCTION_DB_HOST'),
        user=os.getenv('PRODUCTION_DB_USER'),
        password=os.getenv('PRODUCTION_DB_PASS'),
        port=os.getenv('PRODUCTION_DB_PORT'),
        dbname=os.getenv('PRODUCTION_DB_NAME')
    )
    return conn

def get_gemini_transcription(call_id):
    """Get transcription from the gemini-db for a specific call_id"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("SELECT transcription FROM slang.transcriptions_gemini WHERE call_id = %s", (call_id,))
        result = cursor.fetchone()
        return result[0] if result else None
    except Exception as e:
        print(f"Error getting gemini transcription for call_id {call_id}: {e}")
        return None
    finally:
        cursor.close()
        conn.close()

def get_whisper_transcription(call_id):
    """Get final_transcript from the senna-database for a specific call_id"""
    conn = get_senna_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("SELECT final_transcript FROM public.audio_file_processing_data WHERE call_id = %s", (call_id,))
        result = cursor.fetchone()
        return result[0] if result else None
    except Exception as e:
        print(f"Error getting whisper transcription for call_id {call_id}: {e}")
        return None
    finally:
        cursor.close()
        conn.close()

def check_bye_bye_in_transcript(transcript, last_lines_only=True):
    """
    Check if 'bye-bye' appears in AGENT lines of the transcript
    
    Args:
        transcript (str): The transcript text
        last_lines_only (bool): If True, only check the last few lines of the transcript
        
    Returns:
        tuple: (bool, list of matching lines)
    """
    if not transcript:
        return False, []
    
    agent_lines = extract_agent_lines(transcript)
    
    # If last_lines_only is True, only use the last 5 agent lines (or all if less than 5)
    if last_lines_only and len(agent_lines) > 5:
        agent_lines = agent_lines[-5:]
    
    matches = []
    found = False
    
    for line in agent_lines:
        # Extract timestamp and text
        parts = line.split('AGENT:', 1)
        if len(parts) < 2:
            continue
            
        timestamp = parts[0].strip()
        agent_text = parts[1].strip()
        agent_text_lower = agent_text.lower()
        
        # Check for 'bye-bye' as a whole word
        pattern = r'\b' + re.escape('bye-bye') + r'\b'
        
        if re.search(pattern, agent_text_lower):
            found = True
            # Extract context (10 chars before and after if available)
            for match in re.finditer(pattern, agent_text_lower):
                start_pos = match.start()
                end_pos = match.end()
                
                start_context = max(0, start_pos - 10)
                end_context = min(len(agent_text_lower), end_pos + 10)
                
                context_text = agent_text_lower[start_context:end_context]
                matches.append((timestamp, context_text))
    
    return found, matches

def cross_verify_call_ids_with_bye_bye(limit=None):
    """
    Find call_ids in gemini-db that have 'bye-bye' in the AGENT lines,
    then check if the same call_id in senna-database also has 'bye-bye'
    
    Args:
        limit (int, optional): Maximum number of call_ids to check
        
    Returns:
        dict: Results statistics and details
    """
    # Connect to gemini-db to get call_ids
    gemini_conn = get_db_connection()
    gemini_cursor = gemini_conn.cursor()
    
    query = """
    SELECT call_id, transcription 
    FROM slang.transcriptions_gemini 
    ORDER BY call_id
    """
    
    if limit:
        query += f" LIMIT {limit}"
    
    gemini_cursor.execute(query)
    
    # Results tracking
    results = {
        'total_checked': 0,
        'bye_bye_in_gemini': 0,
        'bye_bye_in_both': 0,
        'bye_bye_only_in_gemini': 0,
        'false_positives': [],
        'confirmed_matches': []
    }
    
    try:
        for call_id, gemini_transcript in gemini_cursor:
            results['total_checked'] += 1
            
            # First check if the gemini transcript has 'bye-bye'
            gemini_has_bye_bye, gemini_matches = check_bye_bye_in_transcript(gemini_transcript)
            
            if gemini_has_bye_bye:
                results['bye_bye_in_gemini'] += 1
                print(f"\n{'='*60}")
                print(f"Call ID {call_id} has 'bye-bye' in gemini-db transcript")
                
                # Now check the whisper database
                whisper_transcript = get_whisper_transcription(call_id)
                
                if whisper_transcript:
                    whisper_has_bye_bye, whisper_matches = check_bye_bye_in_transcript(whisper_transcript)
                    
                    if whisper_has_bye_bye:
                        results['bye_bye_in_both'] += 1
                        results['confirmed_matches'].append({
                            'call_id': call_id,
                            'gemini_matches': gemini_matches,
                            'whisper_matches': whisper_matches
                        })
                        print(f"CONFIRMED: 'bye-bye' also found in whisper transcription for call_id {call_id}")
                        for timestamp, context in gemini_matches:
                            print(f"  - Gemini: {timestamp} - '{context}'")
                        for timestamp, context in whisper_matches:
                            print(f"  - Whisper: {timestamp} - '{context}'")
                    else:
                        results['bye_bye_only_in_gemini'] += 1
                        results['false_positives'].append({
                            'call_id': call_id,
                            'gemini_matches': gemini_matches
                        })
                        print(f"FALSE POSITIVE: 'bye-bye' NOT found in whisper transcription for call_id {call_id}")
                        for timestamp, context in gemini_matches:
                            print(f"  - Gemini: {timestamp} - '{context}'")
                        
                        # Print the last few lines of both transcripts for comparison
                        print("\nGemini transcript last lines:")
                        agent_lines = extract_agent_lines(gemini_transcript)
                        for line in agent_lines[-3:]:
                            print(f"  {line}")
                            
                        print("\nWhisper transcript last lines:")
                        whisper_agent_lines = extract_agent_lines(whisper_transcript)
                        for line in whisper_agent_lines[-3:]:
                            print(f"  {line}")
                else:
                    print(f"WARNING: No transcript found in whisper transcription for call_id {call_id}")
                
                print(f"{'='*60}")
            
            # Progress update every 20 records
            if results['total_checked'] % 20 == 0:
                print(f"Processed {results['total_checked']} records...")
    
    finally:
        gemini_cursor.close()
        gemini_conn.close()
    
    # Print summary statistics
    print("\n" + "="*60)
    print("SUMMARY RESULTS:")
    print(f"Total call_ids checked: {results['total_checked']}")
    print(f"Call_ids with 'bye-bye' in gemini transcriptions: {results['bye_bye_in_gemini']}")
    print(f"Call_ids with 'bye-bye' in both transcription types: {results['bye_bye_in_both']}")
    print(f"Call_ids with 'bye-bye' ONLY in gemini transcriptions (false positives): {results['bye_bye_only_in_gemini']}")
    print("="*60)
    
    return results

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Cross-verify bye-bye occurrences between calvin-db and senna-database')
    parser.add_argument('--limit', type=int, help='Limit the number of call_ids to check')
    parser.add_argument('--call-id', type=int, help='Check a specific call_id')
    
    args = parser.parse_args()
    
    if args.call_id:
        # Check a specific call_id
        call_id = args.call_id
        print(f"Checking specific call_id: {call_id}")
        
        gemini_transcript = get_gemini_transcription(call_id)
        if gemini_transcript:
            gemini_has_bye_bye, gemini_matches = check_bye_bye_in_transcript(gemini_transcript)
            print(f"Gemini transcript {'has' if gemini_has_bye_bye else 'does NOT have'} 'bye-bye'")
            
            if gemini_has_bye_bye:
                for timestamp, context in gemini_matches:
                    print(f"  - Gemini: {timestamp} - '{context}'")
            
            whisper_transcript = get_whisper_transcription(call_id)
            if whisper_transcript:
                whisper_has_bye_bye, whisper_matches = check_bye_bye_in_transcript(whisper_transcript)
                print(f"Whisper transcript {'has' if whisper_has_bye_bye else 'does NOT have'} 'bye-bye'")
                
                if whisper_has_bye_bye:
                    for timestamp, context in whisper_matches:
                        print(f"  - Whisper: {timestamp} - '{context}'")
                
                print("\nGemini transcript last lines:")
                gemini_agent_lines = extract_agent_lines(gemini_transcript)
                for line in gemini_agent_lines[-3:]:
                    print(f"  {line}")
                    
                print("\nWhisper transcript last lines:")
                whisper_agent_lines = extract_agent_lines(whisper_transcript)
                for line in whisper_agent_lines[-3:]:
                    print(f"  {line}")
            else:
                print(f"No whisper transcript found for call_id {call_id}")
        else:
            print(f"No gemini transcript found for call_id {call_id}")
    else:
        # Run the full cross-verification
        cross_verify_call_ids_with_bye_bye(limit=args.limit)
