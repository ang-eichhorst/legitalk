import json, os, sys
from datetime import datetime
import importlib.util
import check_ffmpeg

from videotools import download_audio
from transcription import transcribe_audio
import meetingreporter

# --- Defaults ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
WIP_DIR = os.path.join(BASE_DIR, 'wip')
MEETINGS_DIR = os.path.join(BASE_DIR,'localhost', 'meetings')
COMMITTEES_FILE = os.path.join(BASE_DIR, 'committees.json')
TEMPLATE_FILE = os.path.join(BASE_DIR, 'viewer_template.html')


def process_single_meeting(
    video_url: str,
    meeting_date: str,
    committee_name: str,
    members: list = None,
    wip_dir: str = WIP_DIR,
    meetings_dir: str = MEETINGS_DIR,
    parent_committee: str = None,
    structured_only: bool = False,
    jurisdiction: str = '',
    download_url: str = None,
    search_url: str = '/search.html',
):
    """Run the full pipeline for a single meeting and return output paths."""
    committee_folder = committee_name.replace(" ", "_")
    parent_dir = parent_committee.replace(" ", "_") if parent_committee else None

    # Use download_url if provided, otherwise fallback to video_url
    actual_download_url = download_url if download_url else video_url

    # Hierarchical folder structure
    if parent_dir:
        wip_meeting_path = os.path.join(wip_dir, parent_dir, committee_folder, meeting_date)
        final_meeting_path = os.path.join(meetings_dir, parent_dir, committee_folder, meeting_date)
    else:
        wip_meeting_path = os.path.join(wip_dir, committee_folder, meeting_date)
        final_meeting_path = os.path.join(meetings_dir, committee_folder, meeting_date)

    os.makedirs(wip_meeting_path, exist_ok=True)
    os.makedirs(final_meeting_path, exist_ok=True)
    
    if os.path.exists(os.path.join(final_meeting_path, 'transcript.html')):
        print(f"  - Skipping {meeting_date}: Final transcript.html already exists.")
        return None

    meta = {
        "video_url": video_url,
        "date": meeting_date,
        "committee": committee_name,
        "parent_committee": parent_committee,
        "jurisdiction": jurisdiction,
    }
    with open(os.path.join(wip_meeting_path, "meta.json"), "w") as f:
        json.dump(meta, f, indent=4)

    # --- Download ---
    audio_path = os.path.join(wip_meeting_path, "audio.mp3")
    if not os.path.exists(audio_path):
        print(f"  - Downloading audio for {meeting_date}...")
        result = download_audio(actual_download_url, audio_path)
        if not result and not os.path.exists(audio_path):
            raise RuntimeError(f"Download failed for {meeting_date}")
    else:
        print(f"  - Audio already exists for {meeting_date}.")

    # --- Transcribe ---
    transcript_path = os.path.join(wip_meeting_path, "deepgram_raw.json")
    if not os.path.exists(transcript_path):
        print(f"  - Transcribing {meeting_date}...")
        transcript_json = transcribe_audio(audio_path)
        if not transcript_json:
            raise RuntimeError(f"Transcription failed for {meeting_date}")
        with open(transcript_path, "w") as f:
            f.write(json.dumps(json.loads(transcript_json), indent=4))
    else:
        print(f"  - Transcription already exists for {meeting_date}.")

    # --- Generate structured transcript and optional HTML ---
    with open(transcript_path, "r") as f:
        deepgram_data = json.load(f)

    hint_text = ""
    if members:
        hint_text = "\n".join(f"{m['name']} ({m.get('title','')})" for m in members)

    structured_path = os.path.join(wip_meeting_path, "structured.json")
    html_path = os.path.join(final_meeting_path, "transcript.html")

    print(f"  - Generating structured transcript for {meeting_date}...")
    meetingreporter.video_to_static_transcript(
        deepgram_data=deepgram_data,
        hints_file_path=None,
        hints_text=hint_text,
        template_path=TEMPLATE_FILE,
        output_path=None if structured_only else html_path,
        meeting_title=f"{committee_name} - {meeting_date}",
        video_url=video_url,
        structured_out_path=structured_path,
        jurisdiction=jurisdiction,
        search_url=search_url,
    )

    if structured_only:
        print(f"✅ Structured data only: {structured_path}")
    else:
        print(f"✅ Full SmartTranscript created at {html_path}")

    return {
        "structured": structured_path,
        "html": None if structured_only else html_path,
    }


def main():
    """
    Either run full committee factory (no args)
    or single-meeting mode if args are provided.

    Examples:
      python factory.py --url "..." --committee "Planning Commission" --date 2025-10-17
      python factory.py --url "..." --structured-only
    """
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--url", help="Video URL to process directly")
    parser.add_argument("--committee", help="Committee name for oneoff processing", default="UnknownCommittee")
    parser.add_argument("--master-list",help="Master list for batch processing",default=COMMITTEES_FILE)
    parser.add_argument("--date", help="Meeting date (YYYY-MM-DD)")
    parser.add_argument("--wip", help="WIP folder path", default=WIP_DIR)
    parser.add_argument("--meetings", help="Meetings folder path", default=MEETINGS_DIR)
    parser.add_argument("--members", help="Optional JSON file with committee members")
    parser.add_argument("--structured-only", action="store_true", help="Skip HTML generation and only output structured.json")
    parser.add_argument("--jurisdiction", help="Jurisdiction name (e.g., 'San Francisco Government')", default="")
    parser.add_argument("--search-url", help="URL for the Search link in the transcript header", default="/search.html")
    parser.add_argument("--getter-script", default="customgetter.py", help="Script to use for getting recent meetings in batch mode.")
    args = parser.parse_args()

    check_ffmpeg.check_ffmpeg_installed() # Call the check here

    if args.url:
        members = None
        if args.members and os.path.exists(args.members):
            with open(args.members, "r") as f:
                members = json.load(f)
        process_single_meeting(
            video_url=args.url,
            meeting_date=args.date or datetime.today().strftime("%Y-%m-%d"),
            committee_name=args.committee,
            members=members,
            wip_dir=args.wip,
            meetings_dir=args.meetings,
            structured_only=args.structured_only,
            jurisdiction=args.jurisdiction,
            search_url=args.search_url,
        )
        return

    # --- Batch mode ---
    print("--- Starting Factory Run ---")
    
    try:
        getter_script_path = os.path.abspath(args.getter_script)
        spec = importlib.util.spec_from_file_location("custom_meeting_getter", getter_script_path)
        custom_getter = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(custom_getter)
        get_recent_meetings_func = custom_getter.get_recent_meetings
        print(f"Dynamically loaded meeting getter from: {getter_script_path}")
    except Exception as e:
        print(f"Error: Could not import get_recent_meetings from '{args.getter_script}'. {e}")
        sys.exit(1)

    if not os.path.exists(args.master_list):
        print(f"Error: committees.json not found.")
        return

    with open(args.master_list, "r") as f:
        loaded_data = json.load(f)

    jurisdiction = loaded_data.get("jurisdiction", "")
    committees = loaded_data.get("committees", [])

    consecutive_failures = 0
    for committee in committees:
        if consecutive_failures >= 2:
            print("Exiting after 2 consecutive failures.")
            sys.exit(1)

        process_count = committee.get("process_count", 0)
        if process_count == 0:
            continue

        committee_name = committee.get("name", "UnknownCommittee")
        print(f"\n--- Processing Committee: {committee_name} ---")

        recent_meetings = get_recent_meetings_func(
            committee_id=committee.get("id"),
            count=process_count
        )

        for meeting in recent_meetings:
            try:
                output = process_single_meeting(
                    video_url=meeting.get("video_url"),
                    meeting_date=meeting.get("date"),
                    committee_name=committee_name,
                    members=committee.get("members", []),
                    wip_dir=args.wip,
                    meetings_dir=args.meetings,
                    parent_committee=committee.get("parent_committee"),
                    structured_only=args.structured_only,
                    jurisdiction=jurisdiction,
                    download_url=meeting.get("download_url"),
                )
                if output:
                    consecutive_failures = 0
                    print(f"  - Done: {output}")
            except Exception as e:
                print(f"  - ERROR: {e}")
                consecutive_failures += 1
                if consecutive_failures >= 2:
                    print("  - Aborting batch run.")
                    sys.exit(1)

    print("\n--- Factory Run Complete ---")


if __name__ == "__main__":
    main()
