from process import process
from save import save_data


def main():
    print("processing data")
    base_folder = "D:/census/JPGandTIFF/108598756"
    # base_folder = "data"
    extracted_data = process(base_folder)
    save_data(extracted_data)


if __name__ == "__main__":
    main()
