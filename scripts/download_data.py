"""Download NASA C-MAPSS (FD001-FD004) into data/raw/.

Usage:
    python -m scripts.download_data              # all four subsets
    python -m scripts.download_data FD001 FD003  # only these
"""

import io
import sys
import urllib.request
import zipfile

from src.config import RAW_DATA_DIR, SUBSETS

# NASA Prognostics Center of Excellence data set #6, mirrored by the PHM Society.
URL = "https://phm-datasets.s3.amazonaws.com/NASA/6.+Turbofan+Engine+Degradation+Simulation+Data+Set.zip"


def files_for(subset):
    return [f"train_{subset}.txt", f"test_{subset}.txt", f"RUL_{subset}.txt"]


def main(subsets):
    RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)
    wanted = [name for s in subsets for name in files_for(s) if not (RAW_DATA_DIR / name).exists()]
    if not wanted:
        print(f"{', '.join(subsets)} already present in {RAW_DATA_DIR}")
        return

    print(f"Downloading {URL} ...")
    with urllib.request.urlopen(URL, timeout=300) as response:
        outer = zipfile.ZipFile(io.BytesIO(response.read()))

    # The archive wraps the data in a nested CMAPSSData.zip.
    inner_name = next(n for n in outer.namelist() if n.endswith("CMAPSSData.zip"))
    inner = zipfile.ZipFile(io.BytesIO(outer.read(inner_name)))

    for name in wanted:
        member = next(n for n in inner.namelist() if n.endswith(name))
        (RAW_DATA_DIR / name).write_bytes(inner.read(member))
        print(f"  saved {name}")


if __name__ == "__main__":
    requested = [s.upper() for s in sys.argv[1:]] or list(SUBSETS)
    unknown = [s for s in requested if s not in SUBSETS]
    if unknown:
        sys.exit(f"Unknown subset(s): {', '.join(unknown)}. Choose from {', '.join(SUBSETS)}.")
    main(requested)
