-- Compare bye-bye occurrences across databases

-- 1. First, identify transcripts in gemini transcriptions that have "bye-bye" in the AGENT text
WITH gemini_transcripts_with_bye_bye AS (
    SELECT 
        call_id,
        transcription
    FROM 
        slang.transcriptions_gemini
    WHERE 
        -- Look for AGENT lines containing bye-bye (case insensitive)
        transcription ~* 'AGENT:.*\bbye-bye\b'
)

-- 2. Export list of call_ids with bye-bye (for manual verification)
SELECT 
    call_id,
    -- Extract a snippet of the line with bye-bye for easier verification
    (regexp_matches(transcription, 'AGENT:.*\bbye-bye\b.*', 'i'))[0] AS bye_bye_line
FROM 
    gemini_transcripts_with_bye_bye
ORDER BY 
    call_id;

-- 3. Run this query on the senna-database to check the same call IDs
-- Replace the VALUES list with call_ids from previous query
WITH call_ids_to_check(call_id) AS (
    VALUES 
    (123), -- replace with actual call_ids from previous query
    (456),
    (789)
)
SELECT 
    c.call_id,
    -- Check if the final transcript contains bye-bye in an AGENT line
    (a.final_transcript ~* 'AGENT:.*\bbye-bye\b') AS has_bye_bye_in_whisper,
    -- Extract the matching line if it exists
    (regexp_matches(a.final_transcript, 'AGENT:.*\bbye-bye\b.*', 'i'))[0] AS matching_line
FROM 
    call_ids_to_check c
LEFT JOIN 
    public.audio_file_processing_data a ON c.call_id = a.call_id
ORDER BY 
    c.call_id;

-- 4. For a specific call_id, examine both transcripts side by side (run separately on each database)
-- Replace 123 with the actual call_id you want to check

-- On gemini transcriptions:
SELECT 
    call_id,
    -- Extract the last few AGENT lines to compare
    (regexp_matches(transcription, '(AGENT:.*\n){1,5}$', 'g'))[0] AS last_agent_lines
FROM 
    slang.transcriptions_gemini
WHERE 
    call_id = 123;

-- On whisper transcriptions:
SELECT 
    call_id,
    -- Extract the last few AGENT lines to compare
    (regexp_matches(final_transcript, '(AGENT:.*\n){1,5}$', 'g'))[0] AS last_agent_lines
FROM 
    public.audio_file_processing_data
WHERE 
    call_id = 123;