import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
# --- end bootstrap ---

import envloader
envloader.load_env_upwards(start=ROOT, keys=[ "OPENAI_API_KEY", "DEEPGRAM_API_KEY"])
import json
import os
import pickle
import logging
from datetime import datetime
from openai import OpenAI


# --- Logger Setup ---
logger = logging.getLogger(__name__)
logger.propagate = False
logger.setLevel(logging.INFO)
if not logger.handlers:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    logger.addHandler(handler)


# --- Core Data Processing ---

def process_deepgram_output(result_dict):
    """
    Processes raw Deepgram output to produce formatted text and sentence timings
    with character offsets, which are crucial for interactivity.
    """
    final_text = ""
    sentence_timings = []
    char_offset = 0
    
    paragraphs = result_dict.get('channels', [{}])[0].get('alternatives', [{}])[0].get('paragraphs', {}).get('paragraphs', [])
    
    for p in paragraphs:
        speaker_label = f"[Speaker {p.get('speaker', 'Unknown')}]: "
        final_text += speaker_label
        
        for s in p.get('sentences', []):
            sentence_text = s.get('text', '') + ' '
            start_char = len(final_text)
            end_char = start_char + len(sentence_text)
            
            sentence_timings.append({
                "text": sentence_text.strip(),
                "start_time": s.get('start', 0) * 1000,
                "end_time": s.get('end', 0) * 1000,
                "start_char": start_char,
                "end_char": end_char
            })
            final_text += sentence_text
        
        final_text += "\n\n"

    return final_text.strip(), sentence_timings

def get_structured_data_from_llm(transcript_text, sentence_timings, hint_text):
    """
    Calls the LLM with a unified prompt to get both speaker names and a
    timestamped agenda in a single, structured JSON object.
    """
    # 1. Create Timestamp-Injected Transcript for the Prompt
    insertions = []
    for sentence in sentence_timings:
        start_char = sentence.get('start_char')
        if start_char is not None:
            timestamp = f"[{sentence['start_time'] / 1000.0:.2f}] "
            insertions.append((start_char, timestamp))
    
    insertions.sort(key=lambda x: x[0], reverse=True)
    text_parts = list(transcript_text)
    for pos, stamp in insertions:
        text_parts.insert(pos, stamp)
    prompt_transcript = "".join(text_parts)

    # 2. Construct the Unified Prompt
    prompt = f"""
You are an expert legislative aide. Your task is to analyze the provided transcript of a public meeting and generate a single, valid JSON object containing a list of all identified speakers and a detailed, timestamped agenda.

**Input Transcript Details:**
- The transcript is a raw text dump from a transcription service.
- Speakers are initially labeled `[Speaker 0]`, `[Speaker 1]`, etc.
- Timestamps in the format `[123.45]` are injected at the start of each sentence, representing the start time in seconds.

**Rules for Speaker Identification:**
1.  Analyze the entire transcript to deduce the real names of the speakers.
2.  Use context, roll calls, introductions, and direct address (e.g., "Supervisor Walton," "President Mandelman") to map the generic speaker ID number to a specific person's name and title.
3.  Use the provided hint list of official members to help identify and correctly spell the names of regular participants.
4.  For each unique speaker, create an object in the `speakers` array.
5.  Provide a concise `reason` for each name assignment and a `confidence_level` from 0 to 10.
6.  CRITICAL: If the <hint> section is provided and lists official members, any speaker responding to a roll call vote (e.g., "Aye", "Nay", "Present") MUST be identified as one of those listed members.
7.  **Overlaps/Context Shifts:** If a single `speaker_id` (e.g., `[Speaker 3]`) is assigned to multiple different people at different times (due to diarization errors or overlap), create **multiple entries** for that `speaker_id` in the `speakers` array.
    - For the "main" speaker associated with that ID, omit `start_time` and `end_time`.
    - For the "temporary" or "overlapping" speaker, you MUST provide `start_time` and `end_time` (in seconds) defining the specific range where this person is speaking.
    - Only create these time-bound overrides if your `confidence_level` is **8 or higher**. If unsure, default to the main speaker or a generic label.

**Rules for Agenda Generation:**
- Core Principle: Every time a speaker begins substantive remarks about a bill, create a new agenda item, even if the same bill was discussed earlier or by the same speaker. 
- Identifying a bill discussion:
1.  A bill discussion begins when a speaker first mentions a bill number or bill title and proceeds with substantive remarks, including policy explanation, support or opposition, questions, testimony, or analysis.
2.  Brief procedural remarks such as “Thank you, Madam Chair” do not start an agenda item.
3.  Edge cases such as “I’ll be brief on House Bill 5421” do start a new agenda item.

- Bill number normalization:
1.  Bills may be referenced in multiple formats, including numeric, comma-separated, or fully spelled-out forms.
2.  Examples include 
    - 5421 or 5,421
    - fifty four twenty one
    - seven thousand and two
    - seven oh oh two
3.  All recognizable variants referring to the same bill must be normalized to a standard numeric format, such as HB 5421 or SB 7002.

- Agenda item creation rules:
1.  Create a new agenda item each time a speaker begins substantive remarks on a bill.
2.  This rule applies to legislators, committee staff, agency officials, and members of the public.
3.  If the same speaker returns later to speak again on the same bill, create a new agenda item.
4.  If a speaker continuously discusses multiple bills in a single uninterrupted segment, create separate agenda items for each bill using the timestamp where each bill is first mentioned.
5.  If discussion is continuous and focused on a single bill, do not split the agenda item unless the speaker clearly transitions to another bill.

**Example of a good `agenda_items` entry:**
```json
{{
  "title": "Unfinished Business (Items 24–26)",
  "start_time": 327.895,
  "summary": "Three ordinances were finally passed, covering emergency procurement, HSS plans for CY2026, and a legal settlement."
}}
```

**Output Format:**
The output MUST be a single, valid JSON object with two top-level keys: `speakers` and `agenda_items`. The keys within each object (`speaker_id`, `speaker_name`, `reason`, `confidence_level`, `start_time`, `end_time`, `title`, `summary`) must be named exactly as specified. Do not include any other text or explanations outside of the JSON object.

<transcript>
{prompt_transcript}
</transcript>

<hint>
{hint_text}
</hint>
"""
    # 3. Call the API
    try:
        # Save the prompt for debugging
        with open("temp_prompt.txt", "w", encoding="utf-8") as f:
            f.write(prompt)

        if 'OPENAI_API_KEY' not in os.environ:
            from dotenv import load_dotenv
            load_dotenv()
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        
        logger.info("Sending unified prompt to GPT-5 for combined generation...")
        
        completion = client.chat.completions.create(
            model="gpt-5",
            messages=[
                {"role": "system", "content": "You are an expert legislative aide. Your output must be a single, valid JSON object containing 'speakers' and 'agenda_items' keys."},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"},
            timeout=600.0, # Add a 10-minute timeout
        )
        
        logger.info("Successfully received response from GPT-5.")
        
        # Save the completion for debugging
        with open("temp_completion.txt", "w", encoding="utf-8") as f:
            f.write(str(completion))

        response_content = completion.choices[0].message.content
        return json.loads(response_content)
    except Exception as e:
        logger.error(f"An error occurred with the OpenAI API call: {e}")
        # Save the exception for debugging
        with open("temp_error.txt", "w", encoding="utf-8") as f:
            f.write(str(e))
        return None

def generate_static_html(template_path, output_path, meeting_data):
    """
    Generates a static HTML file by injecting meeting data into a template,
    ensuring character offsets in the data island match the generated HTML.
    """
    try:
        with open(template_path, 'r', encoding='utf-8') as f:
            template_content = f.read()

        # --- Prepare Static Data ---
        agenda_html = ""
        agenda_items = meeting_data.get('agenda_items', [])
        if not agenda_items:
            logger.warning(f"No agenda items found for {meeting_data.get('title')}. Agenda will be empty.")
        
        for i, item in enumerate(agenda_items):
            title = item.get("title", "Untitled")
            start_time = item.get("start_time", 0)
            summary = item.get("summary", "")
            agenda_html += f'<li><a href="#item-{i}">{title} ({format_time(start_time)})</a><div class="agenda-summary">{summary}</div></li>\n'

        agenda_time_map = {item.get('start_time'): f'id="item-{i}"' for i, item in enumerate(agenda_items)}
        speaker_map = meeting_data.get('speaker_map', {})
        speaker_overrides = meeting_data.get('speaker_overrides', [])
        
        # --- New Stateful HTML and Data Generation ---
        rebuilt_transcript_html = ""
        plain_text_for_offsets = ""
        recalculated_sentence_timings = []
        
        current_speaker = -1
        current_speaker_name = ""

        paragraphs = meeting_data.get('paragraphs', [])
        for para in paragraphs:
            speaker_id = para.get('speaker')
            para_start = para.get('start', 0)
            
            # Resolve speaker name with overrides
            resolved_name = speaker_map.get(speaker_id, f"Speaker {speaker_id}")
            for override in speaker_overrides:
                if override['id'] == speaker_id and override['start'] <= para_start <= override['end']:
                    resolved_name = override['name']
                    break
            
            if speaker_id != current_speaker or resolved_name != current_speaker_name:
                if current_speaker != -1:
                    rebuilt_transcript_html += '</p>\n' # Close previous speaker's paragraph
                
                speaker_label_html = f'<p><strong>[{resolved_name}]:</strong> '
                speaker_label_text = f"[{resolved_name}]: "
                rebuilt_transcript_html += speaker_label_html
                plain_text_for_offsets += speaker_label_text
                current_speaker = speaker_id
                current_speaker_name = resolved_name
            else:
                # It's the same speaker, just add a newline for the new paragraph
                rebuilt_transcript_html += "\n"
                plain_text_for_offsets += "\n"

            for sentence in para.get('sentences', []):
                start_time_sec = sentence.get('start', 0)
                anchor_id = ""
                for agenda_time, id_str in agenda_time_map.items():
                    if abs(agenda_time - start_time_sec) < 1.0:
                        anchor_id = id_str
                        break
                
                sentence_text = sentence.get('text', '').strip() + ' '
                
                start_char = len(plain_text_for_offsets)
                end_char = start_char + len(sentence_text) - 1

                recalculated_sentence_timings.append({
                    "text": sentence_text.strip(),
                    "start_time": start_time_sec * 1000,
                    "end_time": sentence.get('end', 0) * 1000,
                    "start_char": start_char,
                    "end_char": end_char,
                    "speaker_id": speaker_id
                })

                rebuilt_transcript_html += f'<span class="utterance" data-start-time="{start_time_sec}">{sentence_text}</span>'
                plain_text_for_offsets += sentence_text
        
        if paragraphs: # Close the very last paragraph tag
            rebuilt_transcript_html += '</p>\n'

        # The data island now contains metadata, but not sentence timings,
        # as that data lives in the span tags themselves.
        meeting_data_for_island = {
            "title": meeting_data.get('title'),
            "video_url": meeting_data.get('video_url'),
            "speakers": meeting_data.get('speakers', [])
        }

        # --- Perform Replacements ---
        content = template_content
        jurisdiction=meeting_data.get('jurisdiction','')
        if jurisdiction:
            jurisdiction+=' '
        content = content.replace('{{PAGE_TITLE}}', jurisdiction+meeting_data.get('title', 'SmartTranscript'))
        content = content.replace('{{OG_TITLE}}', jurisdiction+meeting_data.get('title', 'SmartTranscript'))
        
        og_description = agenda_items[0].get('summary', 'A public meeting transcript.') if agenda_items else 'A public meeting transcript.'
        content = content.replace('{{OG_DESCRIPTION}}', og_description)
        #content=content.replace('{{APP_TITLE}}',jurisdiction+'SmartTranscripts')
        content=content.replace('{{APP_TITLE}}', 'Legitalk')
        content = content.replace('{{MEETING_TITLE}}', meeting_data.get('title', 'SmartTranscript'))
        title = meeting_data.get('title', '')
        committee_name = title.split(' - ')[0]
        date_part = title.split(' - ', 1)[1] if ' - ' in title else ''
        speaker_names = list(dict.fromkeys(speaker_map.values()))  # unique, insertion-ordered
        content = content.replace('{{COMMITTEE_NAME}}', committee_name)
        content = content.replace('{{MEETING_DATE}}', date_part)
        content = content.replace('{{SPEAKER_LIST}}', ', '.join(speaker_names))
        content = content.replace('{{SEARCH_URL}}', meeting_data.get('search_url', '/search.html'))
        content = content.replace('{{AGENDA_HTML}}', agenda_html)
        content = content.replace('{{TRANSCRIPT_HTML}}', rebuilt_transcript_html)
        content = content.replace('{{MEETING_DATA_JSON}}', json.dumps(meeting_data_for_island, indent=2))

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(content)
            
        logger.info(f"Successfully generated static HTML: {output_path}")

    except Exception as e:
        logger.error(f"Error generating static HTML: {e}")
        raise



def format_time(seconds):
    """Helper to format seconds into HH:MM:SS."""
    h = int(seconds / 3600)
    m = int((seconds % 3600) / 60)
    s = int(seconds % 60)
    return f"{h:02d}:{m:02d}:{s:02d}"

# --- Main Factory Function ---

def video_to_static_transcript(
    deepgram_data,
    template_path,
    output_path,
    meeting_title,
    video_url,
    jurisdiction='',
    hints_file_path=None,
    hints_text=None,
    structured_out_path=None,
    search_url='/search.html',
):

    """
    Main factory function to orchestrate the creation of a single, static
    SmartTranscript HTML file from a cached Deepgram result.
    """
    logger.info(f"Starting static transcript generation for: {meeting_title}")
    
    # 1. Load Hints
    hint_text = ""
    if hints_text:
        hint_text = hints_text
    elif hints_file_path:
        try:
            with open(hints_file_path, 'r', encoding='utf-8') as f:
                hint_text = f.read()
        except Exception as e:
            logger.error(f"Could not load hints file: {e}")
            # Continue without hints
    
    # 2. Process Deepgram Output
    if 'results' in deepgram_data:
        deepgram_results = deepgram_data['results']
    else:
        deepgram_results = deepgram_data
        
    transcript_text, sentence_timings = process_deepgram_output(deepgram_results)

    # 3. Get Structured Data from LLM
    if structured_out_path and os.path.exists(structured_out_path):
        with open(structured_out_path, "r", encoding="utf-8") as f:
            structured_data = json.load(f)
            logger.info(f"Read structured LLM data from {structured_out_path}")
    else:
        structured_data = get_structured_data_from_llm(transcript_text, sentence_timings, hint_text)
    if not structured_data:
        logger.error("Failed to get structured data from LLM. Aborting.")
        raise ValueError("Failed to get structured data from LLM.")
    if structured_out_path and  not os.path.exists(structured_out_path):
        try:
            with open(structured_out_path, "w", encoding="utf-8") as f:
                f.write(json.dumps(structured_data, ensure_ascii=False, indent=2))
            logger.info(f"Wrote structured LLM JSON → {structured_out_path}")
        except Exception as e:
            logger.warning(f"Could not write structured JSON to {structured_out_path}: {e}")

    # 4. Assemble Final Data Object for the Template
    
    speaker_map = {}
    speaker_overrides = []

    for sp in structured_data.get('speakers', []):
        speaker_id_val = sp.get('speaker_id') or sp.get('id')
        speaker_name = sp.get('speaker_name') or sp.get('name')
        
        start_time = sp.get('start_time')
        end_time = sp.get('end_time')

        if speaker_id_val is not None and speaker_name:
            try:
                # Ensure the value is a string before splitting
                speaker_id_str = str(speaker_id_val)
                # Extract the integer from a string like "Speaker 0" or "Speaker 0.0" or just "0"
                speaker_id_int = int(float(speaker_id_str.split(' ')[-1]))
                
                if start_time is not None and end_time is not None:
                    # This is a time-bound override
                    speaker_overrides.append({
                        "id": speaker_id_int,
                        "name": speaker_name,
                        "start": float(start_time),
                        "end": float(end_time)
                    })
                else:
                    # This is a default mapping
                    speaker_map[speaker_id_int] = speaker_name
            except (ValueError, IndexError):
                logger.warning(f"Could not parse speaker_id: '{speaker_id_val}'")

    final_meeting_data = {
        "title": meeting_title,
        "video_url": video_url,
        "speakers": structured_data.get('speakers', []),
        "agenda_items": structured_data.get('agenda_items', []),
        "speaker_map": speaker_map,
        "speaker_overrides": speaker_overrides,
        "paragraphs": deepgram_results.get('channels', [{}])[0].get('alternatives', [{}])[0].get('paragraphs', {}).get('paragraphs', []),
        "jurisdiction": jurisdiction,
        "search_url": search_url,
    }

    # 5. Generate the Static HTML
    generate_static_html(template_path, output_path, final_meeting_data)

    logger.info("Process complete.")
