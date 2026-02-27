import os
import csv
import time
import threading
from queue import Queue, Empty
from tqdm import tqdm
from google import genai
import constants
from process import worker_task, stop_event, COOLDOWN, RPM_LIMIT, CALL_LIMIT
from save import save_data


def get_rerun_paths():
    """
    Identifies files that need to be rerun based on the logic in check_progress.py:
    1. Not in NURSE_OUTPUT (successful extractions).
    2. In ERRORS_OUTPUT with a reason that isn't 'Blank Card' or 'File already processed'.
    """
    nurses_seen = set()
    if os.path.exists(constants.NURSE_OUTPUT):
        with open(constants.NURSE_OUTPUT, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get("file"):
                    nurses_seen.add(row["file"])

    error_map = {}
    if os.path.exists(constants.ERRORS_OUTPUT):
        with open(constants.ERRORS_OUTPUT, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                fname = row.get("filename")
                reason = row.get("reason")
                if fname:
                    if fname not in error_map or reason != "File already processed":
                        error_map[fname] = reason

    rerun_paths = []
    for path, reason in error_map.items():
        if path not in nurses_seen:
            # We rerun everything that isn't already a success and isn't a blank card.
            if reason not in ["Blank Card / No data found", "File already processed"]:
                if os.path.exists(path):
                    rerun_paths.append(path)

    return rerun_paths


def main():
    paths = get_rerun_paths()
    if not paths:
        print("No files found that need a rerun.")
        return

    print(f"Found {len(paths)} files to rerun.")

    client = genai.Client()
    path_queue = Queue()
    for p in paths:
        path_queue.put(p)

    save_lock = threading.Lock()
    nurses = []
    pbar = tqdm(total=len(paths), desc="Rerunning files", unit="file")

    def dedicated_worker():
        while not stop_event.is_set():
            try:
                path = path_queue.get_nowait()
            except Empty:
                break

            start_time = time.time()

            # Reuses worker_task which handles constants.CALL_LIMIT and stop_event
            nurse = worker_task(path, client)

            if nurse:
                with save_lock:
                    nurses.append(nurse)
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

    if nurses:
        save_data(nurses)

    pbar.close()
    if stop_event.is_set():
        print(f"\nExecution stopped (Call limit of {CALL_LIMIT} reached).")
    else:
        print(f"\nRerun complete.")


if __name__ == "__main__":
    main()
