# Nurse Cadet Data Extraction

This project is a tool for transcribing historical US Nurse Cadet Corps records (Form 300A and Form 300A Revised) from images using Gemini 3.0 Flash.

## Overview

The system walks through specified folders containing `.jpg` images of Nurse Cadet cards, sends them to a Gemini model with a structured prompt and schema, and saves the extracted data into a CSV file. It includes features for rate limiting, call limits, error logging, and progress tracking.

## Getting Started

### Prerequisites

1.  **Python 3.10+**
2.  **Google Gemini API Key:** You must have a valid API key from Google AI Studio.
3.  **Dependencies:** Install the required libraries using pip:
    ```bash
    pip install google-genai tqdm Pillow
    ```

### Configuration

Before running the script, update `constants.py` with your environment's paths:

- `BASE_PATH`: The root directory where your data folders are stored.
- `UNPROCESSED_FOLDERS`: A text file containing the names of folders to be processed (one per line).
- `PROCESSED_FOLDERS`: A text file where the script will record folders it has finished.
- `NURSE_OUTPUT`: The path for the output CSV containing extracted cadet data.
- `ERRORS_OUTPUT`: The path for the CSV logging any errors or blank cards.
- `MAX_NURSES_TO_SAVE`: How many records to buffer before appending to the CSV.

### Authentication

Set your Google API key as an environment variable:

```powershell
$env:GOOGLE_API_KEY = "your_api_key_here"
```

## How to Run

### 1. Start the Extraction Process

Run the main script to begin processing the images:

```bash
python main.py
```

The script will:

1.  Read the list of folders from the file specified in `UNPROCESSED_FOLDERS`.
2.  Process each image in those folders using a pool of threads.
3.  Respect rate limits (`RPM_LIMIT`) and a global `CALL_LIMIT` to manage costs/quota.
4.  Save progress incrementally to the output CSV.

### 2. Check Progress

You can run the audit script at any time to see a summary of the processing status:

```bash
python check_progress.py
```

This will generate a summary CSV in the `output/` directory showing the percentage of completion for each folder and identifying files that might need a rerun.

## Repository Structure

- `main.py`: The entry point that initializes the processing workflow.
- `nurse.py`: Defines the `NurseCadet` data model and the JSON schema used to ensure structured output from the LLM.
- `process.py`: Contains the core logic for image processing, LLM interaction, threading, and rate limiting. It also includes the image downsampling logic to optimize token usage.
- `save.py`: Handles the appending of extracted data to the CSV output.
- `check_progress.py`: A utility to compare the source images against the output files to provide a processing summary.
- `constants.py`: Centralized configuration for file paths and execution parameters.

## Technical Details

- **Image Optimization:** Images are downsampled to 50% resolution (25% total pixels) before being sent to the LLM to reduce latency and token costs while maintaining readability for transcription.
- **Concurrency:** The script uses `threading` to process multiple images in parallel, constrained by a defined RPM (Requests Per Minute) limit.
- **Resiliency:** Already processed files are cached in memory at startup to avoid redundant API calls. If the script is interrupted, it can be restarted and will pick up where it left off.
