import csv


def save_data(extracted_data):
    save_to_csv(extracted_data)


def save_to_csv(cadets, output_file):
    if not cadets:
        print("No data to save.")
        return

    # Define the headers based on your NurseCadet attributes
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

    with open(output_file, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for cadet in cadets:
            # vars(cadet) converts the object attributes into a dictionary
            writer.writerow(vars(cadet))

    print(f"Successfully saved {len(cadets)} records to {output_file}")
