"""Write the console's sample files to data/samples/: a failing and a healthy held-out unit per component.

Turbofan and hydraulic samples come from the test files in data/raw/; battery, gearbox and IGBT samples are
cut from the held-out units' full records in the download cache (~/.cache/aerosentinel).

Usage: python -m scripts.make_samples   (also run by python -m scripts.download_data)
"""

from pathlib import Path

from src.components.splits import write_samples
from src.config import RAW_DATA_DIR, SAMPLES_DIR

CACHE = Path.home() / ".cache" / "aerosentinel"


def main():
    for old in SAMPLES_DIR.glob("*_*.*"):  # the set is rewritten whole
        old.unlink()
    for key, s in write_samples(RAW_DATA_DIR, SAMPLES_DIR, CACHE).items():
        print(f"  {key:<14} {s['file']:<34} {s['rows']:>4} rows, true remaining life {s['true_life']:g} {s['life_unit']}")


if __name__ == "__main__":
    main()
