from process import process
from save import save_data
import constants


def main():
    print("processing data")
    base_folder = constants.BASE_PATH
    # base_folder = "data"
    output_file = constants.NURSE_OUTPUT
    extracted_data = process(base_folder)
    save_data(extracted_data, output_file)


if __name__ == "__main__":
    main()
