import os
import csv
import time
import threading
import json
import io
import sys  # Added for clean exit
from queue import Queue, Empty
from tqdm import tqdm
from PIL import Image
from google import genai
from google.genai import types
from save import save_data
import constants
from nurse import NurseCadet

# --- NEW GLOBAL TRACKING ---
CALL_LIMIT = 10000
llm_call_count = 0
count_lock = threading.Lock()
stop_event = threading.Event()
# ---------------------------

RPM_LIMIT = 50
COOLDOWN = 30

cache_lock = threading.Lock()
error_lock = threading.Lock()


def process(base_path):
    master_cache = load_processed_cache()
    unprocessed_folders = get_unprocessed_folders(base_path)
    for folder in unprocessed_folders:
        if stop_event.is_set():
            print(f"\nLimit of {CALL_LIMIT} calls reached. Exiting.")
            sys.exit(0)
        error = process_folder(folder, master_cache)
        if error == 0:
            mark_folder_processed(folder)
    return


def process_folder(folder_path, cache_set):
    paths = get_image_paths(folder_path)
    if len(paths) == 0:
        return -1
    client = genai.Client()
    path_queue = Queue()
    for p in paths:
        path_queue.put(p)

    save_lock = threading.Lock()
    nurses = []
    pbar = tqdm(
        total=len(paths),
        desc=f"Processing {os.path.basename(folder_path)}",
        unit="file",
    )

    def dedicated_worker():
        while not stop_event.is_set():  # Check if we should stop
            try:
                path = path_queue.get_nowait()
            except Empty:
                break

            start_time = time.time()
            filename = os.path.basename(path)

            if already_processed(path, cache_set):
                log_error(path, "File already processed")
                pbar.update(1)
                path_queue.task_done()
                continue

            nurse = worker_task(path, client)

            if nurse:
                with save_lock:
                    nurses.append(nurse)
                    mark_file_done(filename, cache_set)
                    if len(nurses) >= constants.MAX_NURSES_TO_SAVE:
                        save_data(nurses)
                        nurses.clear()

            pbar.update(1)
            elapsed = time.time() - start_time
            wait_time = max(0, COOLDOWN - elapsed)

            if not path_queue.empty() and not stop_event.is_set():
                time.sleep(wait_time)
            path_queue.task_done()

    threads = []
    for _ in range(min(RPM_LIMIT, len(paths))):
        t = threading.Thread(target=dedicated_worker)
        t.start()
        threads.append(t)

    for t in threads:
        t.join()

    if len(nurses) > 0:
        save_data(nurses)

    pbar.close()
    if stop_event.is_set():
        print(
            f"\nTarget of {CALL_LIMIT} LLM calls reached. Data saved. Exiting script."
        )
        sys.exit(0)
    return 0


def worker_task(path, client):
    # Check limit before calling LLM
    global llm_call_count
    with count_lock:
        if llm_call_count >= CALL_LIMIT:
            stop_event.set()
            return None
        # Increment here ensures we count every attempt
        llm_call_count += 1

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
            log_error(path, "Blank Card / No data found")
            return None
        return nurse
    else:
        log_error(path, error_msg or "Unknown Error")
        return None


def extract_data(client, path):
    try:
        with open(path, "rb") as f:
            image_bytes = f.read()
        image_bytes = reduce_resolution(image_bytes, scale=0.5)

        # The actual LLM call
        response = llm(image_bytes, client)

        if not response or not response.text:
            return None, "Empty response from Gemini (Check safety filters)"

        data = json.loads(response.text)
        return NurseCadet(data, path), None

    except json.JSONDecodeError:
        return None, "JSON Parsing Error (Model returned invalid format)"
    except Exception as e:
        return None, f"System Error: {str(e)}"


def reduce_resolution(image_bytes, scale=0.5):
    """Halves width and height, reducing total pixels to 25%."""
    img = Image.open(io.BytesIO(image_bytes))
    new_size = (int(img.width * scale), int(img.height * scale))

    # LANCZOS is high-quality for downsampling
    img = img.resize(new_size, Image.Resampling.LANCZOS)

    output = io.BytesIO()
    # JPEG format is efficient for vision tasks; quality 85 is the sweet spot
    img.save(output, format="JPEG", quality=85)
    return output.getvalue()


def get_image_paths(base_path):
    jpg_files = []
    for root, dirs, files in os.walk(base_path):
        if "trash" in dirs:
            dirs.remove("trash")

        for file in files:
            if file.lower().endswith(".jpg"):
                full_path = os.path.join(root, file)
                jpg_files.append(full_path)
    return jpg_files


def llm(image_bytes, client: genai.Client):
    return client.models.generate_content(
        model="gemini-3-flash-preview",
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


def log_error(filename, reason):
    """Helper to append errors or blank card notices to a CSV."""
    file_exists = os.path.isfile(constants.ERRORS_OUTPUT)
    with error_lock:
        with open(constants.ERRORS_OUTPUT, mode="a", newline="", encoding="utf-8") as f:
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


def get_unprocessed_folders(base_path):
    processed_names = set()
    if os.path.exists(constants.PROCESSED_FOLDERS):
        with open(constants.PROCESSED_FOLDERS, "r") as f:
            processed_names = {line.strip() for line in f if line.strip()}

    if not os.path.exists(constants.UNPROCESSED_FOLDERS):
        return []

    full_paths = []
    with open(constants.UNPROCESSED_FOLDERS, "r") as file:
        for line in file:
            folder_name = line.strip()
            if folder_name and folder_name not in processed_names:
                full_paths.append(os.path.join(base_path, folder_name))

    return full_paths


def mark_folder_processed(full_path):
    """
    Extracts the folder name from a full path, removes it from
    unprocessed.txt, and adds it to processed.txt
    """
    folder_name = os.path.basename(full_path)

    if os.path.exists(constants.UNPROCESSED_FOLDERS):
        with open(constants.UNPROCESSED_FOLDERS, "r") as f:
            lines = f.readlines()
        with open(constants.UNPROCESSED_FOLDERS, "w") as f:
            for line in lines:
                if line.strip() != folder_name:
                    f.write(line)

    with open(constants.PROCESSED_FOLDERS, "a") as f:
        f.write(folder_name + "\n")


def load_processed_cache():
    """Initializes the set from the CSV once at startup."""
    processed_set = set()
    if os.path.exists(constants.NURSE_OUTPUT):
        with open(constants.NURSE_OUTPUT, mode="r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                name = row.get("file")
                if name:
                    processed_set.add(name)
    if os.path.exists(constants.ERRORS_OUTPUT):
        with open(constants.ERRORS_OUTPUT, mode="r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                name = row.get("filename")
                if name:
                    processed_set.add(name)
    return processed_set


def already_processed(filename, cache_set):
    """Instant lookup in the thread-safe set."""
    with cache_lock:
        return filename in cache_set


def mark_file_done(filename, cache_set):
    """Updates both the shared set and the physical CSV file."""
    with cache_lock:
        cache_set.add(filename)