"""Download the public datasets and build data/raw/ for every component.

Usage:
    python -m scripts.download_data                  # every component
    python -m scripts.download_data turbofan         # NASA C-MAPSS only (or name subsets: FD001 FD003)
    python -m scripts.download_data battery bearing  # NASA PCoE batteries, FEMTO gearbox bearings
    python -m scripts.download_data hydraulic power  # UCI hydraulic rig, NASA PCoE IGBTs

Large archives (battery 0.2 GB, gearbox 1.2 GB, hydraulic 0.08 GB, IGBT 0.24 GB) are kept in a cache outside the project
(AEROSENTINEL_CACHE, default ~/.cache/aerosentinel); only the small per-cycle tables go to data/raw/.
"""

import io
import os
import sys
import urllib.request
import zipfile
from pathlib import Path

from src.config import RAW_DATA_DIR, SUBSETS

# NASA Prognostics Center of Excellence data repository, mirrored by the PHM Society.
MIRROR = "https://phm-datasets.s3.amazonaws.com/NASA/"
URL = MIRROR + "6.+Turbofan+Engine+Degradation+Simulation+Data+Set.zip"
BATTERY_URL = MIRROR + "5.+Battery+Data+Set.zip"
BEARING_URL = MIRROR + "10.+FEMTO+Bearing.zip"
IGBT_URL = MIRROR + "8.+IGBT+Accelerated+Aging.zip"
HYDRAULIC_URL = "https://archive.ics.uci.edu/static/public/447/condition+monitoring+of+hydraulic+systems.zip"
CACHE = Path(os.environ.get("AEROSENTINEL_CACHE", Path.home() / ".cache" / "aerosentinel"))


def files_for(subset):
    return [f"train_{subset}.txt", f"test_{subset}.txt", f"RUL_{subset}.txt"]


def _fetch(url, path):
    """Stream a download to disk (skipped if already cached)."""
    if path.exists():
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    print(f"Downloading {url} ...", flush=True)
    tmp = path.with_suffix(".part")
    with urllib.request.urlopen(url, timeout=600) as response, open(tmp, "wb") as out:
        while chunk := response.read(1 << 20):
            out.write(chunk)
    tmp.replace(path)
    return path


def turbofan(subsets):
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


def battery():
    from src.components import battery_data, splits

    if (RAW_DATA_DIR / "train_PCOE.csv").exists():
        print("Battery tables already present")
        return
    archive = _fetch(BATTERY_URL, CACHE / "battery.zip")
    mat_dir = CACHE / "battery"
    mat_dir.mkdir(parents=True, exist_ok=True)
    outer = zipfile.ZipFile(archive)
    for info in outer.infolist():
        if info.filename.endswith(".zip"):  # one inner zip per test campaign
            inner = zipfile.ZipFile(io.BytesIO(outer.read(info)))
            for f in inner.infolist():
                if f.filename.lower().endswith(".mat"):
                    (mat_dir / Path(f.filename).name).write_bytes(inner.read(f))
    table, eol = battery_data.build(mat_dir)
    print("  battery cells train/test:", splits.write_battery(table, eol, RAW_DATA_DIR))


def bearing():
    from src.components import bearing_data, splits

    if (RAW_DATA_DIR / "train_FEMTO.csv").exists():
        print("Bearing tables already present")
        return
    archive = _fetch(BEARING_URL, CACHE / "femto.zip")
    inner = CACHE / "FEMTOBearingDataSet.zip"
    if not inner.exists():
        outer = zipfile.ZipFile(archive)
        inner.write_bytes(outer.read(next(n for n in outer.namelist() if n.endswith("FEMTOBearingDataSet.zip"))))
    print("Extracting vibration features (about 2 minutes) ...", flush=True)
    table = bearing_data.build(inner)
    print("  bearings train/test:", splits.write_bearing(table, RAW_DATA_DIR))


def hydraulic():
    from src.components import hydraulic_data, splits

    if (RAW_DATA_DIR / "train_UCI.csv").exists():
        print("Hydraulic tables already present")
        return
    archive = _fetch(HYDRAULIC_URL, CACHE / "hydraulic.zip")
    folder = CACHE / "hydraulic"
    if not (folder / "profile.txt").exists():
        zipfile.ZipFile(archive).extractall(folder)
    print("Reducing the hydraulic rig cycles (about 20 s) ...", flush=True)
    print("  hydraulic sessions train/test:", splits.write_hydraulic(hydraulic_data.build(folder), RAW_DATA_DIR))


def power():
    from src.components import power_data, splits

    if (RAW_DATA_DIR / "train_IGBT.csv").exists():
        print("IGBT tables already present")
        return
    archive = _fetch(IGBT_URL, CACHE / "igbt.zip")
    folder = CACHE / "igbt"
    if not (folder / "IGBTAgingData_04022009").exists():
        outer = zipfile.ZipFile(archive)
        inner = next(n for n in outer.namelist() if n.endswith("IGBTAgingData_04022009.zip"))
        zipfile.ZipFile(io.BytesIO(outer.read(inner))).extractall(folder)
    print("Extracting IGBT switching features (about 2 minutes) ...", flush=True)
    table = power_data.build(folder / "IGBTAgingData_04022009" / "Data")
    print("  IGBT devices train/test:", splits.write_power(table, RAW_DATA_DIR))


ALL = ["turbofan", "battery", "bearing", "hydraulic", "power"]


def main(args):
    args = [a.upper() if a.upper().startswith("FD") else a.lower() for a in args] or ALL
    subsets = [a for a in args if a in SUBSETS]
    if "turbofan" in args or subsets:
        turbofan(subsets or list(SUBSETS))
    if "battery" in args:
        battery()
    if "bearing" in args or "gearbox" in args:
        bearing()
    if "hydraulic" in args:
        hydraulic()
    if "power" in args:
        power()
    from scripts.make_samples import main as make_samples
    print("Sample files (one unit per profile):")
    make_samples()
    unknown = [a for a in args if a not in SUBSETS and a not in (*ALL, "gearbox")]
    if unknown:
        sys.exit(f"Unknown argument(s): {', '.join(unknown)}. Use {', '.join(ALL)} or {', '.join(SUBSETS)}.")


if __name__ == "__main__":
    main(sys.argv[1:])
