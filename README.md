# Legitalk
This repository is an adaptation of Tom Evslin's source code to work for Connecticut public meetings. 

# SmartTranscripts

This repository contains the open-source components of `sfgovernmentconnection.com` and provides a set of shareware building blocks for anyone who wants to create "SmartTranscripts" from YouTube or other video sources. SmartTranscripts have the searchability of text but easily play clips from the original video source of any selected snippet for verification or to get the depth of audio and video. SmartTranscripts link to the original video, which must be available online to the user.   

## Overview

The goal of this project is to provide a flexible framework for converting video of meetings into interactive, searchable, and shareable web pages. This can be done for a single meeting or as a fully automated "factory" that continuously processes new meetings as they are posted. 

### Use Cases

1.  **Single Meeting Transcript:** You can create a SmartTranscript for a single meeting by providing its video URL, a name for the meeting, and its date. This is useful for one-off transcriptions without setting up a full pipeline.

2.  **Automated Factory:** To automatically process meetings from a specific public body, you will need to write your own version of `customgetter.py`. This script is responsible for finding the latest meeting videos as they are posted online. Once you have a custom getter, the `factory.py` script can be run on a schedule to automate the entire process.

## Installation

This project was developed and tested using Python 3.13.5.


1.  **Clone the repository:**
    ```bash
    git clone https://github.com/tevslin/smarttranscripts.git # Or your forked repository
    cd smarttranscripts
    ```
2.  **Install FFmpeg:**

    This project requires `ffmpeg` to process audio from video files. If FFMPEG is not already properly installed, you will need to install it.

    *   **On macOS (using Homebrew):**
        ```bash
        brew install ffmpeg
        ```
    *   **On Windows:**
        Download a build from the official [FFmpeg website](https://ffmpeg.org/download.html) and add the `bin` directory to your system's PATH.

3.  **Verify FFmpeg Installation:**
    Run the `check_ffmpeg.py` script to confirm `ffmpeg` is correctly installed and accessible.
    ```bash
    python check_ffmpeg.py
    ```

4.  **Create and activate a Python virtual environment (recommended):**
    ```bash
    python -m venv venv
    # On Windows:
    .\venv\Scripts\activate
    # On macOS/Linux:
    source venv/bin/activate
    ```
3.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```
4.  **Configure environment variables:**
    Copy `sample.env` to `.env` and fill in your API keys for OpenAI and Deepgram.
    ```bash
    cp sample.env .env
    # Open .env in your text editor and add your keys
    ```

## Quick Start: Single SmartTranscript

You can quickly generate a SmartTranscript for an individual meeting by providing its URL, a name, and a date.

Here's an example using a YouTube video:

```bash
python factory.py \
    --url "https://www.youtube.com/watch?v=XtF_Q5nF1kU" \
    --committee "Schools Committee" \
    --date "2025-10-10" \
    --jurisdiction "Sample Jurisdiction"
```
This command will:
*   Download the audio from the YouTube video.
*   Transcribe the audio using Deepgram.
*   Use OpenAI to identify speakers and generate an agenda.
*   Create an interactive HTML SmartTranscript in the `localhost/meetings/Schools_Committee/2025-10-10/` directory.

After generation, you will need to start a local web server from the `localhost` directory (see 'Local Hosting' below) and then navigate to the appropriate URL in your browser (e.g., `http://localhost:8000/meetings/Schools_Committee/2025-10-10/transcript.html`). Directly opening the HTML file will not work due to browser security restrictions.

## File Descriptions

### Root Directory Files

*   **`factory.py`**: The main orchestration script. It can be run to process a single meeting via command-line arguments or in batch mode to process all meetings for committees defined in `committees.json`.
*   **`setup_s3_cloudfront.py`**: A utility for creating and configuring an AWS infrastructure (S3 bucket, CloudFront distribution, Route 53 records) if you want to host your SmartTranscripts on AWS. They can be hosted locally or any modern web server capable of serving static web pages.
*   **`upload_framework.py`**: A script to upload the core "framework" files (CSS, JS) to your S3 bucket if you are using one. It uses a manifest to upload only the necessary files.
*   **`sync_meetings.py`**: A script to synchronize all generated meeting transcripts from your local `meetings` directory to the S3 bucket and invalidate the CloudFront cache.
*   **`meetingreporter.py`**: A core module that takes transcription data and generates the final, interactive HTML SmartTranscript page.
*   **`transcription.py`**: A module responsible for sending audio files to the Deepgram API for transcription.
*   **`videotools.py`**: A utility for downloading audio from various video stream URLs using `yt-dlp`.
*   **`check_ffmpeg.py`**: A standalone script to verify if `ffmpeg` is correctly installed and accessible in your system's PATH. Run this script to confirm your `ffmpeg` setup.
*   **`customgetter.py`**: An example "getter" script that finds recent meetings for a specific Granicus-based site. You will need to create your own version of this to support other jurisdictions or sources.
*   **`envloader.py`**: A small utility to load environment variables from `.env` files.
*   **`committees.json`**: A JSON file that defines the committees to be processed in batch mode, including their names, IDs, and optionally members.
*   **`requirements.txt`**: A list of all the Python packages required to run the scripts in this repository.
*   **`sample.env`**: A file for managing environment variables like API keys and bucket names. You will need to create your own .env with API keys for OpenAI and Deepgram.
*   **`.gitignore`**: Specifies files and directories that should be ignored by Git.
*   **`viewer_template.html`**: The HTML template into which meeting-specific data is injected to create the final SmartTranscript.

### `localhost` Directory Files

These files form the front-end framework for the SmartTranscript viewer. They are served alongside the generated HTML for each meeting.

*   **`index.html`**: The main landing page for the collection of transcripts. Not needed if you are only making single SmartTranscripts.
*   **`viewer_logic.js`**: The primary JavaScript file that "hydrates" the static HTML of a transcript, adding all interactivity like click-to-play, search, and sharing.
*   **`directory.js`**: Scans the `meetings` directory to build the folder hierarchy for the navigation pane.
*   **`toc_viewer.js`**: Controls the left-hand "Table of Contents" pane, including pinning, unpinning, and the flyout menu behavior.
*   **`navigation.js`**: Handles the logic for the navigation pane, which allows browsing meetings by committee and date.
*   **`style.css`**: The main stylesheet that defines the look and feel of the SmartTranscript viewer.
*   **`dropdown_styles.css`**: Specific styles for the dropdown menus used in the viewer.
*   **`loader.js`**: Manages the loading of other JavaScript modules.
*   **`tour.js` / `tour.css`**: Code for a guided tour feature to introduce users to the interface.
*   **`youtubePlayer.js`**: A wrapper for the YouTube IFrame API to standardize video player controls. Only required if the souce of you videos is YouTube.
*   **`cls.html`**: A utility page that clears `localStorage` and `sessionStorage` to let testers simulate a first-time user experience.

## Hosting Your SmartTranscripts

The generated HTML files are static and can be hosted on any modern web server. Tools are provided for hosting on AWS but this is not a requirement.

### Local Hosting

For local development and testing, you can easily start a web server from within the `localhost` directory. This requires Python to be installed.

```bash
# Navigate to the localhost directory
cd implementations/smarttranscripts/localhost

# Start a simple Python web server
python -m http.server 8000
```
You can then access your transcripts at `http://localhost:8000` in your web browser.

### S3 / CloudFront Hosting

For a production environment, as used by `sfgovernmentconnection.com`, you can host the files on AWS. This repository includes several tools to facilitate this:

*   **`setup_s3_cloudfront.py`**: Use this script to create the S3 bucket and CloudFront distribution that will serve your website.
*   **`upload_framework.py`**: Run this script to upload the core JavaScript and CSS files to your bucket.
*   **`sync_meetings.py`**: After running the factory to generate new transcripts locally, run this script to upload them to S3 and update the meeting index.

## Disclaimer

This software is provided "as is", without warranty of any kind, express or implied, including but not limited to the warranties of merchantability, fitness for a particular purpose and noninfringement. In no event shall the authors or copyright holders be liable for any claim, damages or other liability, whether in an action of contract, tort or otherwise, arising from, out of or in connection with the software or the use or other dealings in the software.

There is no assurance that bugs will be fixed or that the code will be updated.

## Contributing

Contributions are welcome! If you would like to add new capabilities, fix bugs, or add support for other jurisdictions, please feel free to file a pull request. Providing custom getter scripts and parsers for other municipalities is a particularly valuable way to contribute.

## 2026 Legitalk hosting manual

In 2026 Legitalk was hosted on an Ubuntu shell running inside a Dell laptop that remained plugged into power and open. 

    1. Open Ubuntu terminal on Dell.

A virtual connection was set up with my Mac using Tailscale.

    2. Check Tailscale connection is open on both computers, log-in using appropriate admin passwords. You should see codeamin@CTM-StephenB-LT:

    3. Open terminal in Mac and type ssh wsl to connect to the Dell through the virtual connection 

Then


    cd legitalk

    source venv/bin/activate 

Run the command. It looks something like this for standard legitalk: 

For a YouTube video

    python factory.py --url "https://www.youtube.com/watch?v=MzgJEc7_0A8" --committee "Human Services Committee" --date "2026-04-07-Neglect-Forum" --jurisdiction "Connecticut" && python sync_meetings.py && python factory.py --url "https://www.youtube.com/watch?v=-rAWwIPaxaM" --committee "Human Services Committee" --date "2026-04-07-Committee" --jurisdiction "Connecticut" && python sync_meetings.py && python factory.py --url "https://www.youtube.com/watch?v=J121Wh1IJi4" --committee "Public Health Committee" --date "2026-04-07" --jurisdiction "Connecticut" && python sync_meetings.py

Add a title beyond the date i.e. "2026-04-07-Neglect-Forum" if there are multiple meetings for the same committee in a day. Otherwise just the date "2026-04-07" is fine. 

&& joins together multiple commands. Python sync_meetings.py can be run at the end of each video to commit it to AWS. 

For a CT-N video 

    python factory.py --url "https://video.ct-n.com/vod/_definst_/OD2026FEB02/mp4:SENATE+2%2D4+G%2Emp4/playlist.m3u8" --committee "Senate" --date "2026-02-04" --jurisdiction "Connecticut" && python sync_meetings.py && python factory.py --url "https://video.ct-n.com/vod/_definst_/OD2026MAR23/mp4:SENATE+3%2D26+G%2Emp4/playlist.m3u8" --committee "Senate" --date "2026-03-26" --jurisdiction "Connecticut" && python sync_meetings.py && python factory.py --url "https://video.ct-n.com/vod/_definst_/OD2026FEB02/mp4:HOUSE+OPEN+DAY+2%2D4+G%2Emp4/playlist.m3u8" --committee "House" --date "2026-02-04" --jurisdiction "Connecticut" && python sync_meetings.py && python factory.py --url "https://video.ct-n.com/vod/_definst_/OD2026FEB02/mp4:HOUSE+2%2D5+G%2Emp4/playlist.m3u8" --committee "House" --date "2026-02-05" --jurisdiction "Connecticut" && python sync_meetings.py && python factory.py --url "https://video.ct-n.com/vod/_definst_/OD2026FEB23/mp4:HOUSE+2%2D26+G%2Emp4/playlist.m3u8" --committee "House" --date "2026-02-26" --jurisdiction "Connecticut" && python sync_meetings.py && python factory.py --url "https://video.ct-n.com/vod/_definst_/OD2026MAR23/mp4:HOUSE+3%2D25+G%2Emp4/playlist.m3u8" --committee "House" --date "2026-03-25" --jurisdiction "Connecticut" && python sync_meetings.py

Running CT-N and Youtube videos together is acceptable. To find the m3u8 for the CT-N video inspect the code source in Google chrome. 

Troubleshooting! You may need to update yt-dlp in the virtual environment

For out of session season, I set up a localhost/other folder that does not create a committee tag on the website and runs a separate search matrix. To access you will need specific page link i.e. https://theconnecticutmirror.com/other/Early_Childhood_Education_Endowment/2026-05-18/transcript.html 

    python factory.py --url "https://video.ct-n.com/vod/_definst_/OD2026MAY18/mp4:EARLY+CHILD+5%2D18+G%2Emp4/playlist.m3u8" --committee "Early Childhood Education Endowment" --date "2026-05-18" --jurisdiction "Connecticut" --meetings localhost/other --search-url "/other/search.html" && python sync_meetings.py

When you are choosing names for meetings, don't put '&' within like I did here, i.e. "Planning & Zoning" because it will register as '%26'. Just avoid

    python factory.py --url "https://www.youtube.com/watch?v=PskuvDUjJTs" --committee "Norwalk Planning & Zoning Commission 07-15-2026" --date "2026-07-15" --jurisdiction "Connecticut" --meetings localhost/other --search-url "/other/search.html" && python sync_meetings.py && python factory.py --url "https://www.youtube.com/watch?v=bwmZG5D7XHk" --committee "Norwalk Planning & Zoning Commission 07-29-2026" --date "2026-07-29" --jurisdiction "Connecticut" --meetings localhost/other --search-url "/other/search.html" && python sync_meetings.py

I've been updated code changes but the goal is not necessarily to bog down the repo with every transcript + supporting material. That lives in AWS...

## 2026 Legitalk AWS set-up
### Initial set-up
Set up an S3 container. You also need CloudFront and Route 53.  

Multi-factor authentication through the Google Authenticator app. 

If you want stuff to be deleted from the website you need to delete it from S3. 

