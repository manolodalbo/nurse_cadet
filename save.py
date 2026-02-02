import csv
import constants
import os


def save_data(extracted_data):
    output_file = constants.NURSE_OUTPUT
    save_to_csv(extracted_data, output_file)


def save_to_csv(cadets, output_file):
    if not cadets:
        print("No data to save.")
        return
    fieldnames = [
        "card_type",
        "serial_number",
        "last_name",
        "first_name",
        "middle_name",
        "home_street",
        "home_city",
        "home_county",
        "home_state",
        "date_of_birth",
        "admission_corp_date",
        "admission_school_date",
        "termination_date",
        "termination_type",
        "school_name",
        "school_city",
        "school_state",
        "file",
    ]
    file_exists = os.path.isfile(output_file)
    with open(output_file, mode="a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)

        if not file_exists:
            writer.writeheader()

        for cadet in cadets:
            writer.writerow(vars(cadet))

    print(f"Successfully saved {len(cadets)} records to {output_file}")
