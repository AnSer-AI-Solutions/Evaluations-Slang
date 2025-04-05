# "Bye-Bye" Transcript Verification

This set of tools helps identify and verify instances where "bye-bye" appears in transcripts. It addresses the issue where the word "bye-bye" might be incorrectly identified in the gemini transcriptions but doesn't actually appear in the original audio (as verified by the whisper transcriptions).

## Available Tools

1. **cross_verify_bye_bye.py**: Standalone tool to compare transcripts between gemini and whisper transcriptions
2. **slang_with_verification.py**: Modified version of slang.py that cross-checks "bye-bye" occurrences with whisper transcriptions
3. **bye_bye_analysis.sql**: SQL queries to analyze and compare "bye-bye" occurrences across transcript types

## How to Use

### 1. Cross-Verify Specific Call IDs

To check a specific call ID that you suspect might have the "bye-bye" issue:

```bash
python cross_verify_bye_bye.py --call-id 12345
```

This will:
- Check if "bye-bye" appears in both the gemini and whisper transcriptions
- Display the last few lines of both transcripts for comparison
- Show the context in which "bye-bye" appears

### 2. Run Full Verification Across All Transcripts

To scan through all transcripts looking for discrepancies:

```bash
python cross_verify_bye_bye.py
```

To limit the number of transcripts checked:

```bash
python cross_verify_bye_bye.py --limit 100
```

### 3. Use Enhanced Slang Detection with Verification

The modified slang detection script will automatically cross-reference with whisper transcriptions when evaluating "bye-bye" occurrences:

```bash
python slang_with_verification.py --verify-bye-bye
```

This script works just like the regular slang.py but adds automatic verification for "bye-bye" instances against the whisper transcriptions. It will only count "bye-bye" as slang if it appears in both transcript types.

### 4. SQL Analysis

The `bye_bye_analysis.sql` file contains SQL queries that you can run directly against the databases to:
1. Find all gemini transcriptions with "bye-bye"
2. Check if the corresponding whisper transcriptions also contain "bye-bye"
3. Examine specific call IDs in detail

## Understanding the Results

When using these tools, you'll see results classified as:

- **Confirmed matches**: "bye-bye" appears in both gemini and whisper transcriptions
- **False positives**: "bye-bye" appears only in gemini transcriptions but not in whisper transcriptions

The false positives are the cases you're looking for - where gemini transcriptions incorrectly identified a word or phrase as "bye-bye" when the agent didn't actually say it.

## Database Configuration

The tools use two database connections:
- Gemini transcriptions: Using the connection details in the .env file (DEV_DB_*)
- Whisper transcriptions: Using the senna-database connection (PRODUCTION_DB_*)

Make sure both database connections are properly configured in the .env file before running these tools.