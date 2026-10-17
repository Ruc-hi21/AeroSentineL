"""Write the console's one-unit sample files to data/samples/ from the test files in data/raw/.

Usage: python -m scripts.make_samples   (also run by python -m scripts.download_data)
"""

from src.components.splits import write_samples
from src.config import RAW_DATA_DIR, SAMPLES_DIR


def main():
    for profile, (path, rows, true) in write_samples(RAW_DATA_DIR, SAMPLES_DIR).items():
        print(f"  {profile:<6} {path.name:<28} {rows:>4} rows, true remaining life {true:g}")


if __name__ == "__main__":
    main()
