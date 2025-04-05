import re

# List of slang words to check
SLANG_WORDS = [
    'nope', 'gonna', 'gunna', 'gotcha', 
    'lemme', 'okey dokey', 'all righty', 'cool', 'ain\'t', 
    'bye-bye', 'yup', 'yep', 'ya', 'yeah', 'okay dokey', 'okey dokey'
]

# List of slang words that are acceptable in question context
QUESTION_RESPONSE_SLANG = ['yeah', 'yup', 'yep', 'ya']

# Define slang words that need verification
VERIFIED_SLANG_WORDS = ['bye-bye']

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
    
    # Regular expression to match lines containing "AGENT:" (with or without timestamp)
    for line in transcription.split('\n'):
        if 'AGENT:' in line.strip():
            agent_lines.append(line.strip())
    
    return agent_lines

def is_near_question(agent_lines, current_index):
    """
    Check if the current line is near a question mark in agent lines
    Returns True if there's a question mark in the current, previous or next agent line
    """
    # Check current line
    current_line = agent_lines[current_index]
    if '?' in current_line:
        return True
        
    # Check previous line if available
    if current_index > 0:
        prev_line = agent_lines[current_index - 1]
        if '?' in prev_line:
            return True
            
    # Check next line if available
    if current_index < len(agent_lines) - 1:
        next_line = agent_lines[current_index + 1]
        if '?' in next_line:
            return True
            
    return False
