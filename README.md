# Slang Detection System

A comprehensive system for evaluating transcriptions to detect slang usage in customer service interactions.

## System Overview

This system analyzes conversational transcripts to identify and flag slang words used by customer service agents. It processes transcripts from a database, evaluates them against a list of predefined slang words, and generates reports with improvement suggestions.

## Components

The system consists of several interconnected Python modules:

### slang_with_verification.py

The main entry point and processing script that:
- Reads transcriptions from the database
- Evaluates them for slang word usage
- Scores the interactions (0 or 2 points)
- Stores evaluation results back in the database

### slang_helper.py

Database connection and utility functions:
- `get_db_connection()`: Establishes connection to the database
- `get_transcription_cursor()`: Retrieves transcriptions for processing
- `get_unprocessed_transcription_cursor()`: Gets only unprocessed transcriptions
- `get_max_transcription_id()`: Gets highest used transcription ID
- `insert_evaluation()`: Stores evaluation results
- Various counting functions for statistics

### slang_common.py

Shared constants and utility functions:
- `SLANG_WORDS`: List of slang words to check
- `QUESTION_RESPONSE_SLANG`: Slang that may be acceptable in question contexts
- `SLANG_ALTERNATIVES`: Mapping of slang words to proper alternatives
- `extract_agent_lines()`: Extracts agent speech from transcriptions
- `is_near_question()`: Determines if a slang word is near a question

### cross_verify_slang.py

Verification using Whisper transcriptions:
- `get_whisper_transcription()`: Gets alternative transcription
- `should_count_slang()`: Verifies if slang appears in both transcription types
- `VERIFIED_SLANG_WORDS`: Slang words that require double verification

## Database Structure

The system connects to a database containing two main tables:
1. A transcriptions table with call recordings and their text transcriptions
2. An evaluations table where results are stored

The connection parameters are configured in `slang_helper.py`.

## How to Run

The script can be run from the terminal with various options:

```bash
# Basic usage - process all unprocessed transcriptions
python slang_with_verification.py

# Run in test mode with just 10 entries
python slang_with_verification.py --test

# Process a specific number of entries
python slang_with_verification.py --limit 50

# Process all records, even if already processed
python slang_with_verification.py --process-all

# Specify a custom batch size (default is 10)
python slang_with_verification.py --batch-size 20

# Start processing from a specific transcription ID
python slang_with_verification.py --start-id 1000

# Disable verification against Whisper transcriptions
python slang_with_verification.py --no-slang-verification

# Disable special handling of response slang near questions
python slang_with_verification.py --no-question-context
```

## Workflow

1. The script connects to the database and retrieves transcriptions
2. Each transcription is processed to extract agent lines
3. Agent lines are analyzed for slang word usage
4. Special context (like proximity to questions) is considered
5. For certain slang words, verification with Whisper transcriptions is performed
6. The interaction is scored:
   - 2 points (pass) if no slang is used
   - 0 points (fail) if any slang is detected
7. Evaluation results with improvement suggestions are stored in the database
8. Detailed statistics are provided during and after processing

## Dependencies

- Python 3.6+
- Database access libraries (likely psycopg2 for PostgreSQL)
- Regular expressions (re)
- Collections module (Counter)

## Example Output

When running the script, you'll see output like this:

```
Running in full mode, batch size: 10, starting ID: 100, skipping processed call_ids, verifying 'yeah', 'yup' against whisper transcriptions, ignoring responses like 'yeah' near questions
Highest existing transcription_id: 99
Total records in database: 500
Unprocessed records available: 45

DEBUG: Processing call_id: 12345
...
INFO: 'yeah' found near a question - NOT counting it as slang
      Context: 'yeah, I understand your concern'
...
DEBUG: Found slang word 'gonna' at 00:03:15 - context: 'we are gonna look into that'
...
DEBUG: Slang word summary for call_id 12345:
  - 'gonna': 1 occurrences

DEBUG: Evaluation result: FAILED (Score: 0/2)
Processed call_id 12345 → transcription_id: 100 (1/45)
...

Processing complete!
Records processed: 45
Last transcription_id used: 144
``` 