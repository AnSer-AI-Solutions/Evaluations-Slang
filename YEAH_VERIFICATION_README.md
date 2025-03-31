# "Yeah" Context Analysis for Slang Detection

This enhancement to the slang detection system reduces false negatives by analyzing the context in which words like "yeah", "yup", "yep", and "ya" are used in agent responses.

## How It Works

The system checks if these casual affirmative responses are used near questions:

1. When an agent says "yeah", "yup", "yep", or "ya" in a line that is:
   - The same line as a question mark, OR
   - Immediately before a line with a question mark, OR
   - Immediately after a line with a question mark
   
   It's considered an acceptable response and not counted as slang.

2. Otherwise, these words are still counted as slang that should be replaced with more professional language like "yes".

This approach recognizes that these casual responses are natural and expected when asking or answering questions, but should be avoided in other contexts during professional customer interactions.

## Example

In this transcript of agent lines only:

```
[00:00] AGENT: Good afternoon, how may I help you?
[00:12] AGENT: Yeah, I can definitely help with that. What's your account number?
[00:21] AGENT: Was that A as in Alpha or E as in Echo?
[00:34] AGENT: Yeah, I see your account now. Thank you.
[00:50] AGENT: Yeah, and just to confirm, you wanted to schedule that for next week?
```

- First "yeah": Not counted as slang (follows a question)
- Second "yeah": Not counted as slang (follows a question)
- Third "yeah": Counted as slang (not near a question)

## Benefits

This context-aware approach:

1. Reduces false negatives where agents are penalized for natural speech patterns
2. Focuses only on agent speech patterns (ignores caller lines)
3. Still encourages professional language in non-question contexts
4. Better matches human evaluation of what constitutes appropriate language

## Command Line Options

The contextual analysis for "yeah" and similar words is enabled by default. If you want to disable it, use:

```bash
python slang_with_verification.py --no-question-context
```

This will cause all instances of "yeah" to be counted as slang, regardless of context.
