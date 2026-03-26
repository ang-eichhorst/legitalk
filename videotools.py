"""

videotools.py

Purpose: Provides utilities for downloading audio from various video streams (YouTube, Granicus, etc.) using yt-dlp and ffmpeg, with duration validation and CAPTCHA handling.

BoM: Audio download and validation utility.

"""

import yt_dlp

import argparse

import os

import sys

import shutil

import subprocess

import json

import webbrowser

 

class YouTubeBlockError(Exception):

    """Raised when YouTube blocks the request (429, 403, or human verify)."""

    pass

 

class DownloadValidationError(Exception):

    """Raised when the downloaded file fails duration or size validation."""

    pass

 

class MediaUnavailableError(Exception):

    """Raised when the video is deleted, removed, or generally unavailable."""

    pass

 

class PrivateVideoError(Exception):

    """Raised when the video is marked private by the poster."""

    pass

 

class UpcomingStreamError(Exception):

    """Raised when the stream is upcoming (Waiting for Live)."""

    pass

 

class LiveBroadcastError(Exception):

    """Raised when a live broadcast is still in progress."""

    pass

 

def handle_captcha(url, cookie_file="youtube_cookies.txt"):

    """

    Alerts user to CAPTCHA/Block, opens browser, and refreshes cookies.

    """

    # Capability Check: Does the burner profile exist on this machine?

    # This avoids popping a browser on a machine that can't sync the cookies anyway.

    appdata = os.environ.get('APPDATA')

    profile_found = False

    if appdata:

        profile_path = os.path.join(appdata, "Mozilla", "Firefox", "Profiles", "ndlkaawr.burner")

        if os.path.exists(profile_path):

            profile_found = True

           

    if not profile_found:

        # If we can't find the profile, we can't sync.

        # Skip interactive mode to avoid hanging the process.

        print(f"!!! YouTube Challenge Detected, but Firefox burner profile was not found.")

        print("!!! Skipping interactive solve (Automatic return to headless behavior).")

        return False

 

    print(f"\n{'!'*60}")

    print(f"!!! YOUTUBE CHALLENGE/CAPTCHA DETECTED !!!")

    print(f"I need your help to verify this IP address.")

    print(f"Opening browser to: {url}")

    print(f"1. IMPORTANT: Solve the CAPTCHA in your FIREFOX 'burner' profile.")

    print(f"2. Play 1-2 seconds of the video while logged into your BURNER account in that FIREFOX profile.")

    print(f"3. Come back here and press Enter to resume.")

    print(f"{'!'*60}\n")

   

    # Open the URL

    webbrowser.open(url)

    input("Press Enter after solving in Firefox (burner profile)...")

   

    print("Refreshing local cookies from Firefox (burner profile)...")

    refresh_cmd = [

        sys.executable, '-m', 'yt_dlp',

        '--cookies-from-browser', 'firefox:ndlkaawr.burner',

        '--cookies', cookie_file, '--skip-download',

        '--remote-components', 'ejs:github',

        url

    ]

    try:

        # Run explicitly so user sees output

        subprocess.run(refresh_cmd, check=True)

        print(f"Cookies updated in {cookie_file}.")

        return True

    except Exception as e:

        print(f"Failed to refresh cookies: {e}")

        return False

 

def get_ytdlp_duration(url):

    """

    Retrieves the duration of a video from yt-dlp metadata.

    """

    try:

        ydl_opts = {'quiet': True, 'skip_download': True}

        # Check for cookies to help bypass blocks even for metadata checks

        cookie_file = "youtube_cookies.txt"

        if os.path.exists(cookie_file):

            ydl_opts['cookiefile'] = cookie_file

           

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:

            info = ydl.extract_info(url, download=False)

            return info.get('duration')

    except:

        return None

 

def get_local_duration(filepath):

    """

    Retrieves the duration of a local audio file using ffprobe.

    """

    cmd = [

        'ffprobe', '-v', 'error',

        '-show_entries', 'format=duration',

        '-of', 'default=noprint_wrappers=1:nokey=1',

        filepath

    ]

    try:

        out = subprocess.check_output(cmd, text=True).strip()

        return float(out)

    except:

        return None

 

def verify_and_check_duration(url, filepath, expected, tolerance):

    """

    Performs pre-download and post-download duration validation.

    """

    # Pre-check (Remote)

    if not os.path.exists(filepath): # Only check remote if file doesn't exist yet/we are about to download

        remote = get_ytdlp_duration(url)

        if remote and expected:

            delta = abs(remote - expected)

            if delta > tolerance:

                return False, f"Pre-download mismatch: Remote {remote}s vs Expected {expected}s (Diff: {delta}s)"

   

    # Post-check (Local) - only if file exists

    if os.path.exists(filepath) and expected:

        local = get_local_duration(filepath)

        if local:

            delta = abs(local - expected)

            if delta > tolerance:

                # Cleanup handled by caller? Or here?

                # Caller expects file to be valid if success.

                return False, f"Post-download mismatch: Local {local}s vs Expected {expected}s (Diff: {delta}s)"

   

    return True, "Verified"

 

def download_audio(stream_url, output_filename, expected_duration=None, tolerance=300, audio_codec='mp3'):

    """

    Orchestrates the download and extraction of audio from a stream with validation and retries.

    """

    log_file_path = 'progress.log'

    base_filename = output_filename.rsplit('.', 1)[0]

    temp_filename = f"{base_filename}.part"

    final_filename = output_filename

 

    # If the final file already exists, we're done.

    if os.path.exists(final_filename):

        print(f"'{final_filename}' already exists. Skipping download.")

        return final_filename

       

    # If a partial file exists, remove it to start fresh.

    if os.path.exists(temp_filename):

        os.remove(temp_filename)

 

    # 0. PRE-CHECK: Active Live Broadcast Detection

    # We do this first to avoid following an active stream or chasing fragments.

    if "youtube.com" in stream_url or "youtu.be" in stream_url:

        try:

            probe_opts = {'quiet': True, 'skip_download': True, 'noplaylist': True}

            cookie_file = "youtube_cookies.txt"

            if os.path.exists(cookie_file): probe_opts['cookiefile'] = cookie_file

           

            with yt_dlp.YoutubeDL(probe_opts) as ydl:

                info = ydl.extract_info(stream_url, download=False)

                if info.get('is_live') or info.get('live_status') == 'is_live':

                    # post_live sometimes still acts like a moving target during processing

                    raise LiveBroadcastError(f"Live Broadcast ({info.get('live_status')}) in progress. Waiting for completion.")

        except LiveBroadcastError:

            raise

        except Exception as e:

            # Probe failed? We'll let the main loop try, but we've attempted to skip.

            pass

 

    with open(log_file_path, 'a', encoding='utf-8') as log_file:

        original_stdout = sys.stdout

        original_stderr = sys.stderr

        sys.stdout = log_file

        sys.stderr = log_file

 

        try:

            # Pre-Download Check

            if expected_duration:

                ok, msg = verify_and_check_duration(stream_url, final_filename, expected_duration, tolerance)

                if not ok:

                    sys.stdout = original_stdout

                    print(msg)

                    sys.stdout = log_file

                    raise DownloadValidationError(msg)

 

            # OPTIMIZATION: If it's a direct MP4 link, use ffmpeg to stream and extract audio directly.

            # This avoids downloading the huge video file first.

            if stream_url.lower().endswith('.mp4') or 'm3u8' in stream_url.lower():

                print(f"Detected MP4 URL. Using direct ffmpeg streaming for: {stream_url}")

                import subprocess

               

                # ffmpeg -i "url" -vn -acodec libmp3lame -q:a 2 "output.mp3"

                # -vn: Disable video recording

                # -acodec libmp3lame: Use LAME mp3 encoder

                # -q:a 2: Variable bit rate, quality level 2 (good balance)

                # -y: Overwrite output files without asking

               

                cmd = [

                    'ffmpeg',

                    '-y',

                    '-i', stream_url,

                    '-vn',

                    '-acodec', 'libmp3lame',

                    '-q:a', '2',

                    final_filename

                ]

               

                # Run ffmpeg, capturing output to the log file we opened

                # We need to flush the python buffers to ensure log file order is roughly correct

                sys.stdout.flush()

                sys.stderr.flush()

               

                result = subprocess.run(cmd, stdout=log_file, stderr=log_file, text=True)

               

                if result.returncode == 0 and os.path.exists(final_filename):

                    # Post-Download Check

                    ffmpeg_ok = True

                    if expected_duration:

                         ok, msg = verify_and_check_duration(stream_url, final_filename, expected_duration, tolerance)

                         if not ok:

                             sys.stdout = original_stdout

                             print(f"FFmpeg direct stream duration mismatch: {msg}. Falling back to yt-dlp.")

                             sys.stdout = log_file

                             os.remove(final_filename)

                             ffmpeg_ok = False

 

                    if ffmpeg_ok:

                         # Restore stdout to print success message

                        sys.stdout = original_stdout

                        print(f"Successfully streamed and extracted audio to {final_filename}")

                        return final_filename

                else:

                    print(f"FFmpeg direct stream failed with return code {result.returncode}. Falling back to yt-dlp.")

           

            # RESILIENCE: Strategy for format fallback.

            # We split these into separate 'fresh' attempts to ensure that if yt-dlp

            # fails a high-quality download (e.g. 403 on a fragment), it tries the

            # more resilient (but lower quality) formats in a distinct second call.

           

            formats_to_try = []

            if audio_codec == 'm4a':

                # Attempt 1: High Quality Progressive (Standard m4a/mp4)

                formats_to_try.append({

                    'fmt': 'bestaudio[ext=m4a]/bestaudio/best[ext=mp4]',

                    'post': [],

                    'ext_hints': ['.m4a', '.mp4']

                })

                # Attempt 2: Resilient Progressive (Low bitrate/Old devices)

                # These often bypass PO-Token/Bot-Detection blocks more easily.

                formats_to_try.append({

                    'fmt': '139/251/250/249/18',

                    'post': [],

                    'ext_hints': ['.m4a', '.webm', '.opus', '.mp4']

                })

                # Attempt 3: HLS Rescue (Segmented streams)

                formats_to_try.append({

                    'fmt': '95/94/93/92/91/bestaudio/best',

                    'post': [],

                    'ext_hints': ['.m4a', '.mp4', '.ts']

                })

            else: # mp3

                # Attempt 1: Quality

                formats_to_try.append({

                    'fmt': 'bestaudio/best',

                    'post': [{'key': 'FFmpegExtractAudio','preferredcodec': 'mp3','preferredquality': '192'}],

                    'ext_hints': ['.mp3']

                })

                # Attempt 2: Resilient

                formats_to_try.append({

                    'fmt': '139/251/250/249/18',

                    'post': [{'key': 'FFmpegExtractAudio','preferredcodec': 'mp3','preferredquality': '192'}],

                    'ext_hints': ['.mp3']

                })

                # Attempt 3: HLS Rescue

                formats_to_try.append({

                    'fmt': '95/94/93/92/91/bestaudio/best',

                    'post': [{'key': 'FFmpegExtractAudio','preferredcodec': 'mp3','preferredquality': '192'}],

                    'ext_hints': ['.mp3']

                })

 

            last_block_err = None

            last_validation_err = None

 

            for i, fmt_config in enumerate(formats_to_try):

                if i > 0:

                    sys.stdout = original_stdout

                    print(f"  - Retry: Attempting backup format '{fmt_config['fmt']}'...")

                    sys.stdout = log_file

                   

                # Cleanup before attempt

                if os.path.exists(temp_filename): os.remove(temp_filename)

               

                # Set Remote Components programmatically for GCE environment

                os.environ['YT_DLP_REMOTE_COMPONENTS'] = 'ejs:github'

               

                ydl_opts = {

                    'format': fmt_config['fmt'],

                    'outtmpl': f'{temp_filename}',

                    'postprocessors': fmt_config['post'],

                    'noplaylist': True,

                    'progress': True,

                    'remote_components': ['ejs:github'], 

                    'fragment_retries': 0,

                    'ignoreerrors': False,

                }

                if audio_codec == 'm4a':

                     ydl_opts['outtmpl'] = f'{temp_filename}.%(ext)s'

 

                # --- YouTube Specific Workarounds ---

                if "youtube.com" in stream_url or "youtu.be" in stream_url:

                    # Use Cookies if available

                   

                    # 2. Use Cookies if available

                    cookie_file = "youtube_cookies.txt"

                    if os.path.exists(cookie_file):

                        print(f"  - Using existing cookie file: {cookie_file}")

                        ydl_opts['cookiefile'] = cookie_file

                    else:

                        print(f"  [!] WARNING: {cookie_file} not found. YouTube may block this attempt.")

                # ------------------------------------

 

                # Attempt download with retry on CAPTCHA

                success = False

                try:

                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:

                        # Pre-check: Don't download active live streams (unstable for transcription)

                        info = ydl.extract_info(stream_url, download=False)

                        if info.get('is_live') or info.get('live_status') == 'is_live':

                            raise LiveBroadcastError("Live Broadcast in progress. Waiting for completion.")

                           

                        ydl.download([stream_url])

                    success = True

                except (LiveBroadcastError, PrivateVideoError, UpcomingStreamError, MediaUnavailableError):

                    # Re-raise specific diagnostic errors immediately

                    raise

                except Exception as e:

                    err_msg = str(e).lower()

                    # Broadened detection for blocks/challenges

                    if "private video" in err_msg:

                        log_file.flush()

                        sys.stdout = original_stdout

                        print(f"  - Private Video Detected: {err_msg}")

                        sys.stdout = log_file

                        raise PrivateVideoError(err_msg)

                    elif "begin in" in err_msg:

                        log_file.flush()

                        sys.stdout = original_stdout

                        print(f"  - Upcoming Stream Detected: {err_msg}")

                        sys.stdout = log_file

                        raise UpcomingStreamError(err_msg)

                    elif any(x in err_msg for x in ["deleted", "unavailable", "removed"]):

                        log_file.flush()

                        sys.stdout = original_stdout

                        print(f"  - Media Unavailable: {err_msg}")

                        sys.stdout = log_file

                        raise MediaUnavailableError(err_msg)

                    elif any(x in err_msg for x in ["429", "402", "confirm you", "sign in", "bot"]):

                        # Check for Headless Mode (GCE/Server)

                        if os.environ.get('HEADLESS') == 'true':

                            log_file.flush()

                            sys.stdout = original_stdout

                            print(f"!!! YouTube Block Detected in HEADLESS mode (Format {fmt_config['fmt']}). !!!")

                            sys.stdout = log_file

                            # Store and continue to fallback

                            last_block_err = YouTubeBlockError(err_msg)

                            success = False

                        else:

                            # Flush and Restore stdout to interact with user

                            log_file.flush()

                            sys.stdout = original_stdout

                            sys.stderr = original_stderr

                           

                            if handle_captcha(stream_url):

                                print("Retrying download with fresh cookies...")

                                # Re-redirect to log

                                sys.stdout = log_file

                                sys.stderr = log_file

                               

                                ydl_opts['cookiefile'] = "youtube_cookies.txt"

                                try:

                                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:

                                        ydl.download([stream_url])

                                    success = True

                                except Exception as e2:

                                    log_file.flush()

                                    sys.stdout = original_stdout

                                    print(f"  - Retry failed: {e2}")

                                    sys.stdout = log_file

                                    last_block_err = YouTubeBlockError(str(e2))

                                    success = False

                            else:

                                # User failed to refresh or cancelled

                                sys.stdout = log_file

                                sys.stderr = log_file

                                last_block_err = YouTubeBlockError("CAPTCHA solve failed or cancelled by user.")

                                success = False

                    else:

                        log_file.flush()

                        sys.stdout = original_stdout

                        print(f"  - Download error with format {fmt_config['fmt']}: {e}")

                        sys.stdout = log_file

               

                if not success:

                    continue # Try next format if current failed (even after retry)

 

                # Locate Output

                found_temp = None

                if audio_codec == 'mp3':

                     candidate = f"{temp_filename}.mp3"

                     if os.path.exists(candidate): found_temp = candidate

                else:

                     for ext in fmt_config['ext_hints']:

                         candidate = f"{temp_filename}{ext}"

                         if os.path.exists(candidate):

                             found_temp = candidate

                             break

               

                if found_temp:

                    # Dynamic Rename: Preserve actual extension

                    actual_ext = os.path.splitext(found_temp)[1]

                    base_filename = output_filename.rsplit('.', 1)[0]

                    actual_final_filename = f"{base_filename}{actual_ext}"

                   

                    if os.path.exists(actual_final_filename): os.remove(actual_final_filename)

 

                    shutil.move(found_temp, actual_final_filename)

                   

                    # Post-Download Check

                    if expected_duration:

                         ok, msg = verify_and_check_duration(stream_url, actual_final_filename, expected_duration, tolerance)

                         if not ok:

                             sys.stdout = original_stdout

                             print(f"  - {msg}")

                             sys.stdout = log_file

                             # Duration Fail -> Delete and Retry next format

                             os.remove(actual_final_filename)

                             last_validation_err = DownloadValidationError(msg)

                             continue

                   

                    # Success

                    sys.stdout = original_stdout

                    print(f"Successfully downloaded and moved audio to {actual_final_filename}")

                    return actual_final_filename

           

            # If loop finishes without return, raise aggregated errors if any

            if last_block_err:

                raise last_block_err

            if last_validation_err:

                raise last_validation_err

 

            sys.stdout = original_stdout

            print(f"Download failed after trying available formats.")

            return None

 

        except (YouTubeBlockError, DownloadValidationError, MediaUnavailableError, PrivateVideoError, UpcomingStreamError, LiveBroadcastError):

            raise

        except Exception as e:

            print(f"An unexpected error occurred during download: {e}")

            return None

        finally:

            sys.stdout = original_stdout

            sys.stderr = original_stderr

 

if __name__ == '__main__':

    parser = argparse.ArgumentParser(description="Download audio from a video stream.")

    parser.add_argument(

        '--url',

        type=str,

        default="https://archive-stream.granicus.com/OnDemand/_definst_/mp4:archive/sanfrancisco/sanfrancisco_df708991-dcbb-4e71-bc38-cbd85d20743c.mp4/playlist.m3u8",

        help="The URL of the video stream to download."

    )

    parser.add_argument(

        '--output',

        type=str,

        default="temp_audio.m4a",

        help="The desired final output filename (with extension)."

    )

    parser.add_argument(

        '--duration',

        type=float,

        default=None,

        help="Expected duration in seconds."

    )

    parser.add_argument(

        '--codec',

        type=str,

        default="m4a",

        help="Audio codec (m4a or mp3)."

    )

    args = parser.parse_args()

 

    # Clear old log

    if os.path.exists('progress.log'):

        os.remove('progress.log')

 

    print(f"--- Testing Audio Download ---")

    print(f"URL: {args.url}")

    print(f"Output will be saved to {args.output}")

    print(f"Codec: {args.codec}")

    if args.duration:

        print(f"Expected Duration: {args.duration}s")

    print(f"All verbose download output is being redirected to progress.log")

 

    result_path = download_audio(args.url, args.output, expected_duration=args.duration, audio_codec=args.codec)

 

    if result_path:

        print(f"\n--- SUCCESS ---")

        print(f"Audio successfully downloaded to: {result_path}")

    else:

        print(f"\n--- FAILURE ---")

        print(f"Audio download failed. Check progress.log for details.")
