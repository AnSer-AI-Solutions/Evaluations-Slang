import re
import os
import psycopg2
import json
from dotenv import load_dotenv
from slang import extract_agent_lines, SLANG_WORDS, SLANG_ALTERNATIVES
from slang_helper import get_db_connection

# Load environment variables
load_dotenv()

# Define slang words that need verification
VERIFIED_SLANG_WORDS = ['bye-bye', 'all righty']

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

def check_slang_in_transcript(transcript, slang_word, last_lines_only=True):
    """
    Check if specific slang word appears in AGENT lines of the transcript
    
    Args:
        transcript (str): The transcript text
        slang_word (str): The slang word to check for
        last_lines_only (bool): If True, only check the last few lines of the transcript
        
    Returns:
        tuple: (bool, list of matching lines)
    """
    if not transcript:
        return False, []
    
    agent_lines = extract_agent_lines(transcript)
    
    # If last_lines_only is True and the slang word is typically used at the end (like bye-bye),
    # only use the last 5 agent lines (or all if less than 5)
    if last_lines_only and slang_word == 'bye-bye' and len(agent_lines) > 5:
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
        
        # Check for slang word as a whole word
        pattern = r'\b' + re.escape(slang_word) + r'\b'
        
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

def verify_slang_word_in_call(call_id, slang_word):
    """
    Verify if a specific slang word appears in both gemini and whisper transcriptions
    
    Args:
        call_id (int): The call ID to check
        slang_word (str): The slang word to verify
        
    Returns:
        tuple: (appears_in_gemini, appears_in_whisper, gemini_matches, whisper_matches)
    """
    # Check gemini transcription
    gemini_transcript = get_gemini_transcription(call_id)
    if not gemini_transcript:
        return False, False, [], []
        
    gemini_has_slang, gemini_matches = check_slang_in_transcript(
        gemini_transcript, 
        slang_word,
        last_lines_only=(slang_word == 'bye-bye')  # Only use last lines for bye-bye
    )
    
    # If not found in gemini, no need to check whisper
    if not gemini_has_slang:
        return False, False, [], []
    
    # Check whisper transcription
    whisper_transcript = get_whisper_transcription(call_id)
    if not whisper_transcript:
        return gemini_has_slang, False, gemini_matches, []
    
    whisper_has_slang, whisper_matches = check_slang_in_transcript(
        whisper_transcript, 
        slang_word,
        last_lines_only=(slang_word == 'bye-bye')  # Only use last lines for bye-bye
    )
    
    return gemini_has_slang, whisper_has_slang, gemini_matches, whisper_matches

def should_count_slang(call_id, slang_word):
    """
    Determine if a slang word should be counted for a specific call
    Returns True if the word should be counted, False if it should be ignored
    
    Args:
        call_id (int): The call ID
        slang_word (str): The slang word to check
        
    Returns:
        bool: True if the word should be counted as slang, False otherwise
    """
    # If slang word doesn't need verification, always count it
    if slang_word not in VERIFIED_SLANG_WORDS:
        return True
    
    # If it's a word that needs verification, check both transcriptions
    gemini_has_slang, whisper_has_slang, _, _ = verify_slang_word_in_call(call_id, slang_word)
    
    # Only count if it appears in both transcriptions
    should_count = gemini_has_slang and whisper_has_slang
    
    if gemini_has_slang and not whisper_has_slang:
        print(f"INFO: '{slang_word}' found in gemini transcription but NOT in whisper transcription for call_id {call_id} - NOT counting it")
    
    return should_count

def cross_verify_slang_words(limit=None, specific_slang=None):
    """
    Find call_ids in gemini-db that have specific slang words in the AGENT lines,
    then verify them against whisper transcriptions
    
    Args:
        limit (int, optional): Maximum number of call_ids to check
        specific_slang (str, optional): Specific slang word to check, or None for all VERIFIED_SLANG_WORDS
        
    Returns:
        dict: Results statistics and details
    """
    # Define which words to check
    slang_words_to_check = [specific_slang] if specific_slang else VERIFIED_SLANG_WORDS
    
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
    results = {word: {
        'in_gemini': 0,
        'in_both': 0,
        'only_in_gemini': 0,
        'false_positives': [],
        'confirmed_matches': []
    } for word in slang_words_to_check}
    
    # Overall tracking
    total_checked = 0
    
    try:
        for call_id, gemini_transcript in gemini_cursor:
            total_checked += 1
            
            # Check each slang word
            for slang_word in slang_words_to_check:
                # Check if word appears in gemini transcript
                gemini_has_slang, gemini_matches = check_slang_in_transcript(
                    gemini_transcript, 
                    slang_word,
                    last_lines_only=(slang_word == 'bye-bye')
                )
                
                if gemini_has_slang:
                    results[slang_word]['in_gemini'] += 1
                    print(f"\n{'='*60}")
                    print(f"Call ID {call_id} has '{slang_word}' in gemini transcription")
                    
                    # Check the whisper database
                    whisper_transcript = get_whisper_transcription(call_id)
                    
                    if whisper_transcript:
                        whisper_has_slang, whisper_matches = check_slang_in_transcript(
                            whisper_transcript, 
                            slang_word,
                            last_lines_only=(slang_word == 'bye-bye')
                        )
                        
                        if whisper_has_slang:
                            results[slang_word]['in_both'] += 1
                            results[slang_word]['confirmed_matches'].append({
                                'call_id': call_id,
                                'gemini_matches': gemini_matches,
                                'whisper_matches': whisper_matches
                            })
                            print(f"CONFIRMED: '{slang_word}' also found in whisper transcription for call_id {call_id}")
                            for timestamp, context in gemini_matches:
                                print(f"  - Gemini: {timestamp} - '{context}'")
                            for timestamp, context in whisper_matches:
                                print(f"  - Whisper: {timestamp} - '{context}'")
                        else:
                            results[slang_word]['only_in_gemini'] += 1
                            results[slang_word]['false_positives'].append({
                                'call_id': call_id,
                                'gemini_matches': gemini_matches
                            })
                            print(f"FALSE POSITIVE: '{slang_word}' NOT found in whisper transcription for call_id {call_id}")
                            for timestamp, context in gemini_matches:
                                print(f"  - Gemini: {timestamp} - '{context}'")
                            
                            # Print the surrounding lines for comparison
                            print("\nGemini transcript context:")
                            agent_lines = extract_agent_lines(gemini_transcript)
                            for i, line in enumerate(agent_lines):
                                for timestamp, _ in gemini_matches:
                                    if timestamp in line:
                                        # Print a few lines before and after
                                        start_idx = max(0, i - 2)
                                        end_idx = min(len(agent_lines), i + 3)
                                        for j in range(start_idx, end_idx):
                                            print(f"  {agent_lines[j]}")
                    else:
                        print(f"WARNING: No whisper transcript found for call_id {call_id}")
                    
                    print(f"{'='*60}")
            
            # Progress update every 20 records
            if total_checked % 20 == 0:
                print(f"Processed {total_checked} records...")
    
    finally:
        gemini_cursor.close()
        gemini_conn.close()
    
    # Print summary statistics
    print("\n" + "="*60)
    print("SUMMARY RESULTS:")
    print(f"Total call_ids checked: {total_checked}")
    
    for slang_word in slang_words_to_check:
        print(f"\nResults for '{slang_word}':")
        print(f"  - Found in gemini transcriptions: {results[slang_word]['in_gemini']}")
        print(f"  - Found in both transcription types: {results[slang_word]['in_both']}")
        print(f"  - Found ONLY in gemini (false positives): {results[slang_word]['only_in_gemini']}")
    
    print("="*60)
    
    # Add total_checked to results
    results['total_checked'] = total_checked
    
    return results

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Cross-verify slang word occurrences between transcription types')
    parser.add_argument('--limit', type=int, help='Limit the number of call_ids to check')
    parser.add_argument('--call-id', type=int, help='Check a specific call_id')
    parser.add_argument('--slang-word', choices=VERIFIED_SLANG_WORDS, help='Specific slang word to verify')
    
    args = parser.parse_args()
    
    if args.call_id:
        # Check a specific call_id
        call_id = args.call_id
        print(f"Checking specific call_id: {call_id}")
        
        if args.slang_word:
            # Check for specific slang word
            slang_word = args.slang_word
            gemini_has_slang, whisper_has_slang, gemini_matches, whisper_matches = verify_slang_word_in_call(call_id, slang_word)
            
            print(f"Gemini transcript {'has' if gemini_has_slang else 'does NOT have'} '{slang_word}'")
            if gemini_has_slang:
                for timestamp, context in gemini_matches:
                    print(f"  - Gemini: {timestamp} - '{context}'")
            
            print(f"Whisper transcript {'has' if whisper_has_slang else 'does NOT have'} '{slang_word}'")
            if whisper_has_slang:
                for timestamp, context in whisper_matches:
                    print(f"  - Whisper: {timestamp} - '{context}'")
            
            # Print summary
            if gemini_has_slang and whisper_has_slang:
                print(f"VERIFIED: '{slang_word}' appears in both transcriptions - should COUNT as slang")
            elif gemini_has_slang and not whisper_has_slang:
                print(f"NOT VERIFIED: '{slang_word}' only appears in gemini - should NOT count as slang")
            else:
                print(f"NOT FOUND: '{slang_word}' not detected in gemini transcription")
        else:
            # Check all verified slang words
            for slang_word in VERIFIED_SLANG_WORDS:
                print(f"\nChecking for '{slang_word}':")
                gemini_has_slang, whisper_has_slang, gemini_matches, whisper_matches = verify_slang_word_in_call(call_id, slang_word)
                
                print(f"  Gemini transcript {'has' if gemini_has_slang else 'does NOT have'} '{slang_word}'")
                if gemini_has_slang:
                    for timestamp, context in gemini_matches:
                        print(f"    - Gemini: {timestamp} - '{context}'")
                
                print(f"  Whisper transcript {'has' if whisper_has_slang else 'does NOT have'} '{slang_word}'")
                if whisper_has_slang:
                    for timestamp, context in whisper_matches:
                        print(f"    - Whisper: {timestamp} - '{context}'")
                
                # Print summary
                if gemini_has_slang and whisper_has_slang:
                    print(f"  VERIFIED: '{slang_word}' appears in both transcriptions - should COUNT as slang")
                elif gemini_has_slang and not whisper_has_slang:
                    print(f"  NOT VERIFIED: '{slang_word}' only appears in gemini - should NOT count as slang")
                else:
                    print(f"  NOT FOUND: '{slang_word}' not detected in gemini transcription")
    else:
        # Run the full cross-verification
        cross_verify_slang_words(limit=args.limit, specific_slang=args.slang_word)
