import re
from collections import Counter
from slang_helper import (get_transcription_cursor, insert_evaluation, get_max_transcription_id, 
                          get_db_connection, get_total_transcription_count, 
                          get_unprocessed_transcription_cursor, get_unprocessed_count)
import sys
import argparse

# List of slang words to check
SLANG_WORDS = [
    'nope', 'gonna', 'gunna', 'gotcha', 
    'lemme', 'okey dokey', 'all righty', 'cool', 'ain\'t'
]

# Mapping of slang words to proper alternatives
SLANG_ALTERNATIVES = {
    'yup': 'yes',
    'yep': 'yes',
    'nope': 'no',
    'ya': 'you/yes',
    'yeah': 'yes',
    'gonna': 'going to',
    'gunna': 'going to',
    'gotcha': 'I understand',
    'lemme': 'let me',
    'okey dokey': 'okay',
    'all righty': 'alright',
    'uhhhh': 'um',
    'cool': 'good/great',
    'ain\'t': 'is not/are not',
    'bye-bye': 'goodbye',
    'buh-buy': 'goodbye',
    'k': 'okay',
    'kay': 'okay'
}

def extract_agent_lines(transcription):
    """Extract only the lines spoken by the agent from the transcription"""
    agent_lines = []
    context_lines = []
    
    # Regular expression to match lines containing "AGENT:" (with or without timestamp)
    for line in transcription.split('\n'):
        if 'AGENT:' in line.strip():
            agent_lines.append(line.strip())
            context_lines.append(line.strip())
    
    return agent_lines, '\n'.join(context_lines)

def count_slang_words(agent_lines):
    """Count occurrences of each slang word in the text and track timestamps"""
    slang_counts = {}
    found_references = []
    
    # Initialize counts for all slang words
    for word in SLANG_WORDS:
        slang_counts[word] = 0
    
    for line in agent_lines:
        # Extract timestamp (assuming it's at the beginning of the line before AGENT:)
        parts = line.split('AGENT:', 1)
        if len(parts) < 2:
            continue
            
        timestamp = parts[0].strip()
        agent_text = parts[1].strip()
        agent_text_lower = agent_text.lower()
        
        # Check for each slang word in the line
        for word in SLANG_WORDS:
            # Create a regex pattern to match the word as a whole word, case insensitive
            pattern = r'\b' + re.escape(word) + r'\b'
            
            # Find all occurrences of this slang word in the line
            for match in re.finditer(pattern, agent_text_lower):
                start_pos = match.start()
                end_pos = match.end()
                
                # Extract some context around the slang word (10 chars before and after if available)
                start_context = max(0, start_pos - 10)
                end_context = min(len(agent_text_lower), end_pos + 10)
                
                context_text = agent_text_lower[start_context:end_context]
                
                # Update counts
                slang_counts[word] += 1
                
                # Add detailed reference with timestamp and context
                proper_alternative = SLANG_ALTERNATIVES.get(word, "")
                reference = f"{timestamp} - '{word}' (proper: '{proper_alternative}') in '{context_text}'"
                found_references.append(reference)
                
                # DEBUG: Print slang word occurrence immediately when found
                print(f"DEBUG: Found slang word '{word}' at {timestamp} - context: '{context_text}'")
    
    return slang_counts, found_references

def evaluate_transcription(call_id, transcription, transcription_id):
    """Evaluate a transcription for slang word usage"""
    agent_lines, context = extract_agent_lines(transcription)
    slang_counts, found_references = count_slang_words(agent_lines)
    
    # DEBUG: Print summary of slang words found
    print(f"\nDEBUG: Slang word summary for call_id {call_id}:")
    for word, count in slang_counts.items():
        if count > 0:
            print(f"  - '{word}': {count} occurrences")
    
    # Check if any slang word is used
    has_slang = any(count > 0 for count in slang_counts.values())
    
    # Score 2 if no slang is used, 0 if any slang is used
    score = 0 if has_slang else 2
    passed = score > 0
    
    # Create explanation
    if has_slang:
        used_slang = [f"'{word}' ({count} time{'s' if count > 1 else ''})" for word, count in slang_counts.items() if count > 0]
        explanation = f"Agent used inappropriate slang: {', '.join(used_slang)}"
        
        # Add proper alternatives
        alternatives = []
        for word in [w for w, c in slang_counts.items() if c > 0]:
            proper = SLANG_ALTERNATIVES.get(word, "")
            if proper:
                alternatives.append(f"'{word}' → '{proper}'")
        
        if alternatives:
            explanation += f"\n\nProper alternatives: {', '.join(alternatives)}"
            
        improvement_suggestion = "Use proper English in customer interactions. Avoid casual slang and informal language."
    else:
        explanation = "Agent used proper English with no slang words."
        improvement_suggestion = ""
    
    # Prepare evaluation data
    evaluation_data = {
        'transcription_id': transcription_id,
        'call_id': call_id,
        'intern_ai_grade': 'Yes' if passed else 'No',
        'score': score,
        'max_score': 2,
        'criteria': "No Slang (Using Proper English)",
        'passed': passed,
        'explanation': explanation,
        'improvement_suggestion': improvement_suggestion,
        'found_references': found_references,
        'context': context,
        'original_transcription': transcription
    }
    
    # DEBUG: Print evaluation result
    print(f"DEBUG: Evaluation result: {'PASSED' if passed else 'FAILED'} (Score: {score}/{evaluation_data['max_score']})")
    
    return evaluation_data

def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description='Evaluate transcriptions for slang word usage')
    parser.add_argument('--test', action='store_true', help='Run in test mode with 10 entries')
    parser.add_argument('--limit', type=int, help='Limit the number of entries to process')
    parser.add_argument('--batch-size', type=int, default=10, help='Number of records to fetch at once (default: 10)')
    parser.add_argument('--start-id', type=int, help='Starting ID for transcription_id (optional, auto-increments from last used ID if not specified)')
    parser.add_argument('--process-all', action='store_true', help='Process all call_ids even if already processed (default: skip processed)')
    return parser.parse_args()

def main():
    """Main function to process transcriptions"""
    args = parse_arguments()
    
    # Determine the limit based on command line arguments
    target_processed = None  # How many NEW records to process
    if args.test:
        target_processed = 10
    elif args.limit:
        target_processed = args.limit
    
    batch_size = args.batch_size
    
    # Get the highest existing transcription_id and increment by 1
    max_id = get_max_transcription_id()
    next_id = max_id + 1
    
    # Use provided start-id if specified, otherwise use next available ID
    transcription_id = args.start_id if args.start_id is not None else next_id
    
    # Get counts for reporting
    total_records = get_total_transcription_count()
    unprocessed_count = get_unprocessed_count() if not args.process_all else total_records
    
    # Determine mode for display
    mode_desc = "test mode" if args.test else ("limited mode" if args.limit else "full mode")
    limit_desc = f" (target: {target_processed} processed records)" if target_processed else ""
    skip_msg = "" if args.process_all else ", skipping processed call_ids"
    print(f"Running in {mode_desc}{limit_desc}, batch size: {batch_size}, starting ID: {transcription_id}{skip_msg}")
    print(f"Highest existing transcription_id: {max_id}")
    print(f"Total records in database: {total_records}")
    print(f"Unprocessed records available: {unprocessed_count}")
    
    # Variables to track progress
    processed_count = 0
    
    # Keep processing until we've reached the target or processed all records
    try:
        # If we're processing all records (including already processed ones)
        if args.process_all:
            # Use the original cursor that doesn't filter out processed records
            conn, cursor = get_transcription_cursor(
                limit=target_processed, 
                order_by="call_id"
            )
        else:
            # Use the more efficient cursor that excludes already processed records
            conn, cursor = get_unprocessed_transcription_cursor(
                limit=target_processed, 
                order_by="call_id"
            )
            
        try:
            # Process batches of records
            while True:
                # Break if we've reached our target
                if target_processed is not None and processed_count >= target_processed:
                    break
                
                # Fetch one batch of records
                batch = cursor.fetchmany(batch_size)
                if not batch:
                    print("No more records available to process.")
                    break
                
                # Process each record in the batch
                for call_id, transcription in batch:
                    # Skip if transcription is empty
                    if not transcription:
                        continue
                    
                    # DEBUG: Print a separator for each new call
                    print("\n" + "="*50)
                    print(f"DEBUG: Processing call_id: {call_id}")
                    print("="*50)
                    
                    # Process the record
                    evaluation_data = evaluate_transcription(call_id, transcription, transcription_id)
                    insert_evaluation(evaluation_data)
                    
                    # Update counters and display progress
                    processed_count += 1
                    progress = f"{processed_count}"
                    if target_processed:
                        progress += f"/{target_processed}"
                    
                    print(f"Processed call_id {call_id} → transcription_id: {transcription_id} ({progress})")
                    
                    # Increment the transcription_id for the next record
                    transcription_id += 1
                    
                    # Break if we've reached our target
                    if target_processed is not None and processed_count >= target_processed:
                        break
            
            # Print summary statistics
            print("\nProcessing complete!")
            print(f"Records processed: {processed_count}")
            if processed_count > 0:
                print(f"Last transcription_id used: {transcription_id - 1}")
                
        finally:
            # Always close cursor and connection
            cursor.close()
            conn.close()
    
    except Exception as e:
        print(f"Error during processing: {e}")
    
if __name__ == "__main__":
    main()