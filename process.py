import os
from google import genai
from google.genai import types
import json
from nurse import NurseCadet
import csv
import time
import threading
from queue import Queue, Empty
from tqdm import tqdm

RPM_LIMIT = 200
COOLDOWN = 30


def process(base_path):
    paths = get_image_paths(base_path)
    client = genai.Client()

    # Put all paths into a thread-safe Queue
    path_queue = Queue()
    for p in paths:
        path_queue.put(p)

    nurses = []
    # Lock to ensure adding to the nurses list is thread-safe
    results_lock = threading.Lock()
    pbar = tqdm(total=len(paths), desc="Processing Nurse Cards", unit="file")

    def dedicated_worker():
        """A persistent thread that manages its own 60s rhythm."""
        while True:
            try:
                path = path_queue.get_nowait()
            except Empty:
                break

            start_time = time.time()

            nurse = worker_task(path, client)

            if nurse:
                with results_lock:
                    nurses.append(nurse)
            pbar.update(1)
            elapsed = time.time() - start_time
            wait_time = max(0, COOLDOWN - elapsed)
            if not path_queue.empty():
                time.sleep(wait_time)
            path_queue.task_done()

    threads = []
    for _ in range(RPM_LIMIT):
        t = threading.Thread(target=dedicated_worker)
        t.start()
        threads.append(t)

    for t in threads:
        t.join()
    pbar.close()
    return nurses


def worker_task(path, client):
    filename = os.path.basename(path)
    nurse, error_msg = extract_data(client, path)
    if nurse:
        is_blank = (
            not nurse.first_name and not nurse.serial_number and not nurse.last_name
        ) or (
            nurse.first_name == "null"
            and nurse.serial_number == "null"
            and nurse.last_name == "null"
        )
        if is_blank:
            log_error(filename, "Blank Card / No data found")
            return None
        return nurse
    else:
        log_error(filename, error_msg or "Unknown Error")
        return None


def extract_data(client, path):
    try:
        with open(path, "rb") as f:
            image_bytes = f.read()

        response = llm(image_bytes, client)

        if not response or not response.text:
            return None, "Empty response from Gemini (Check safety filters)"

        data = json.loads(response.text)
        return NurseCadet(data, path), None

    except json.JSONDecodeError:
        return None, "JSON Parsing Error (Model returned invalid format)"
    except Exception as e:
        return None, f"System Error: {str(e)}"


def get_image_paths(base_path):
    jpg_files = []
    for root, _, files in os.walk(base_path):
        for file in files:
            if file.lower().endswith(".jpg"):
                full_path = os.path.join(root, file)
                jpg_files.append(full_path)
    return jpg_files


def llm(image_bytes, client: genai.Client):
    return client.models.generate_content(
        model="gemini-2.0-flash",
        contents=[
            types.Content(
                parts=[
                    types.Part(text=prompt),
                    types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg"),
                ]
            )
        ],
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=NurseCadet.get_response_schema(),
        ),
    )


def log_error(filename, reason, error_csv_path="errors_2_0.csv"):
    """Helper to append errors or blank card notices to a CSV."""
    file_exists = os.path.isfile(error_csv_path)
    with open(error_csv_path, mode="a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["filename", "reason"])
        writer.writerow([filename, reason])


prompt = """
ACT AS: An expert archival transcription assistant specializing in US Nurse Cadet Corps historical records.

TASK: 
1. Identify if the card is "Form 300A" or "Form 300A (Revised May 1944)".
2. Transcribe the handwritten and typed text into a structured JSON format.

EXTRACTION RULES:
* Serial Number: Extract the number found at the top.
* Name: Extract Last Name, First Name, and Middle Name/Initial separately.
* Home Address: If the card is a '300A Revised' version, extract the Street, City, County, and State. For standard '300A', return null for these fields.
* Date of Birth: Extract the DOB ONLY if the card is a '300A Revised' version.
* Admission Dates: Extract the 'Date of admission to corps' and 'Date of admission to school (originally)'.
* Graduation/Withdrawal: Look for the 'Termination Dates' section at the bottom to find the date and identify if it was a Graduation or Withdrawal.
* School of Nursing: 
    - On Form 300A Revised, the school Name, City, and State are located on the right side and run VERTICALLY.
    - On Form 300A, this info is located HORIZONTALLY.
    - Extract Name, City, and State for the school.

ACCURACY REQUIREMENTS:
* Transcribe the handwriting exactly as written, even if messy. 
* If a field is blank, return null.
* Do not include conversational filler; return only the JSON object.

HANDLING ILLEGIBLE TEXT:
- If a handwritten field is completely illegible or blurred, return null. 
DATES:
 - Dates should be returned as MM-DD-YYYY regardless of how are they are written in card.

BLANK CARDS or Irrelevant Photos:
 - If card is blank return null for everything.
"""
