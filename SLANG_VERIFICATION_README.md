# Slang Verification System

This system provides advanced verification for slang detection by comparing transcriptions from different sources (Gemini and Whisper) and analyzing the context in which potential slang words are used.

## Key Verification Features

1. **Cross-Verification with Multiple Transcription Types**:
   - Verifies slang words like "bye-bye" and "all righty" across both Gemini and Whisper transcriptions
   - Only counts these as slang if they appear in BOTH transcription types
   - Reduces false positives caused by transcription errors

2. **Question Context Analysis**:
   - Analyzes context for words like "yeah", "yup", "yep", and "ya"
   - Doesn't count these as slang when they appear near questions in agent speech
   - Recognizes natural language patterns in question-response scenarios

## Using the System

### All-in-One Verification

The main script `slang_with_verification.py` integrates both types of verification:

```bash
# Run with default settings (all verifications enabled)
python slang_with_verification.py

# Disable slang word cross-verification
python slang_with_verification.py --no-slang-verification

# Disable question context analysis
python slang_with_verification.py --no-question-context

# Process specific number of calls
python slang_with_verification.py --limit 100
```

### Standalone Cross-Verification

For detailed analysis of specific slang words across transcription types, use `cross_verify_slang.py`:

```bash
# Check all verified slang words
python cross_verify_slang.py

# Check a specific slang word
python cross_verify_slang.py --slang-word "bye-bye"
python cross_verify_slang.py --slang-word "all righty"

# Check a specific call ID
python cross_verify_slang.py --call-id 12345

# Check a specific slang word in a specific call
python cross_verify_slang.py --call-id 12345 --slang-word "bye-bye"
```

## How It Works

1. **For words like "bye-bye" and "all righty"**:
   - First checks if the word appears in the Gemini transcription
   - If found, checks if it also appears in the Whisper transcription
   - Only counts it as slang if it appears in both

2. **For words like "yeah", "yup", "yep", "ya"**:
   - Checks if the word appears near a question mark in agent lines
   - If it's used to ask or answer a question, doesn't count it as slang
   - If used in other contexts, counts it as slang

## Adding More Words for Verification

To add more words to the cross-verification system:

1. Edit `cross_verify_slang.py` and add the word to `VERIFIED_SLANG_WORDS` list
2. The system will automatically include this word in the verification process

No other code changes are needed, as the verification system is designed to handle any words in the `VERIFIED_SLANG_WORDS` list.
