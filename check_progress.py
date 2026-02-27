import csv
import os
from pathlib import Path
import constants


def summarize_data_processing():
    # Initialize global totals
    total_stats = {
        "processed": 0,
        "processed_blank": 0,
        "need_rerun": 0,
        "not_run_at_all": 0,
        "total_files": 0,
    }

    folder_summaries = []

    # 1. Load Reference Data into memory for faster lookups
    nurses_seen = set()
    if os.path.exists(constants.NURSE_OUTPUT):
        with open(constants.NURSE_OUTPUT, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                nurses_seen.add(row["file"])

    error_map = {}
    if os.path.exists(constants.ERRORS_OUTPUT):
        with open(constants.ERRORS_OUTPUT, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                error_map[row["filename"]] = row["reason"]

    # 2. Process folders
    if not os.path.exists(constants.ALL_FOLDERS):
        print("Error: folder with all folders not found.")
        return

    with open("data/general_folder.txt", "r") as f:
        folder_names = [line.strip() for line in f if line.strip()]

    for folder_name in folder_names:
        folder_path = Path(constants.BASE_PATH) / folder_name

        # --- LOGIC CHANGE: Ignore folder if it does not exist ---
        if not folder_path.exists():
            print(f"Skipping: {folder_name} (Path not found)")
            continue

        # Stats for this specific folder
        stats = {
            "folder": folder_name,
            "processed": 0,
            "processed_blank": 0,
            "need_rerun": 0,
            "not_run_at_all": 0,
            "total_files": 0,
        }

        # Gather all jpgs (case-insensitive)
        jpg_files = [
            str(p)
            for p in folder_path.glob("*")
            if p.suffix.lower() in [".jpg", ".jpeg"]
        ]
        stats["total_files"] = len(jpg_files)

        for file_path in jpg_files:
            if file_path in nurses_seen:
                stats["processed"] += 1
            elif file_path in error_map:
                reason = error_map[file_path]
                if reason == "Blank Card / No data found":
                    stats["processed_blank"] += 1
                elif reason == "File already processed":
                    continue
                else:
                    stats["need_rerun"] += 1
            else:
                stats["not_run_at_all"] += 1

        # Add to global totals
        for key in total_stats:
            if key != "folder" and key != "percent_complete":
                total_stats[key] += stats.get(key, 0)

        folder_summaries.append(stats)

    # 3. Write Output
    output_fields = [
        "folder",
        "total_files",
        "processed",
        "processed_blank",
        "need_rerun",
        "not_run_at_all",
        "percent_complete",
    ]

    with open(constants.SUMMARIZE_PROCESSING, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=output_fields)
        writer.writeheader()

        for s in folder_summaries:
            total = s["total_files"]
            s["percent_complete"] = (
                f"{(s['processed'] + s['processed_blank']) / total:.2%}"
                if total > 0
                else "0.00%"
            )
            writer.writerow(s)

        # Write Aggregate Total Row
        total_sum = total_stats["total_files"]
        total_stats["folder"] = "GRAND TOTAL"
        total_stats["percent_complete"] = (
            f"{(total_stats['processed'] + total_stats['processed_blank']) / total_sum:.2%}"
            if total_sum > 0
            else "0.00%"
        )
        writer.writerow(total_stats)

    print(f"Audit complete. Summary saved to {constants.SUMMARIZE_PROCESSING}")


if __name__ == "__main__":
    summarize_data_processing()
