"""Download NASA C-MAPSS FD001 into data/raw/.

Usage: python -m scripts.download_data
"""

import io
import urllib.request
import zipfile

from src.config import DATASET, RAW_DATA_DIR

# NASA Prognostics Center of Excellence data set #6, mirrored by the PHM Society.
URL = "https://phm-datasets.s3.amazonaws.com/NASA/6.+Turbofan+Engine+Degradation+Simulation+Data+Set.zip"
FILES = [f"train_{DATASET}.txt", f"test_{DATASET}.txt", f"RUL_{DATASET}.txt"]


def main():
    RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)
    if all((RAW_DATA_DIR / name).exists() for name in FILES):
        print(f"{DATASET} already present in {RAW_DATA_DIR}")
        return

    print(f"Downloading {URL} ...")
    with urllib.request.urlopen(URL, timeout=120) as response:
        outer = zipfile.ZipFile(io.BytesIO(response.read()))

    # The archive wraps the data in a nested CMAPSSData.zip.
    inner_name = next(n for n in outer.namelist() if n.endswith("CMAPSSData.zip"))
    inner = zipfile.ZipFile(io.BytesIO(outer.read(inner_name)))

    for name in FILES:
        member = next(n for n in inner.namelist() if n.endswith(name))
        (RAW_DATA_DIR / name).write_bytes(inner.read(member))
        print(f"  saved {name}")


if __name__ == "__main__":
    main()
