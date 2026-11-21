"""Read C-MAPSS sensor files from disk or from an uploaded file."""

import csv
import io
import re
from collections import Counter
from pathlib import Path

import pandas as pd

from src.components import spec_of_profile, to_canonical
from src.config import DATASET, RAW_COLUMNS, RAW_DATA_DIR
from src.errors import InvalidDataError

DELIMITERS = [",", ";", "\t", "|"]  # tried in this order; plain whitespace is the fallback (NASA C-MAPSS layout)
SAMPLE_LINES = 60  # lines inspected to work out the layout
_NUMBER = re.compile(r"^[+-]?(\d+([.,]\d*)?|[.,]\d+)([eE][+-]?\d+)?$")


def _decode(content):
    """Bytes to text: UTF-16 (Excel 'Unicode text' exports), UTF-8 with or without a BOM, else Latin-1."""
    if content[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return content.decode("utf-16")
    try:
        return content.decode("utf-8-sig")
    except UnicodeDecodeError:
        return content.decode("latin-1")


def _read_text(source):
    if isinstance(source, (str, Path)):
        return _decode(Path(source).read_bytes())
    content = source.read()  # file-like object, e.g. a Streamlit upload
    return _decode(content) if isinstance(content, bytes) else content


def _split(line, sep):
    return line.split() if sep is None else line.split(sep)


def _layout(lines):
    """(delimiter or None for whitespace, index of the first table line).

    A delimiter qualifies when most sample lines split into the same number (2 or more) of fields with it; of
    those, the one giving the most fields wins. That keeps decimal commas ('0,0023' in a semicolon file from
    European Excel) from being mistaken for the separator. Lines before the table, such as a title or notes,
    are skipped: the table starts at the first line whose field count matches the table's."""
    best = None
    for sep in [*DELIMITERS, None]:
        counts = [len(_split(line, sep)) for line in lines]
        common, n = Counter(counts).most_common(1)[0]
        if common >= 2 and n >= max(2, 0.6 * len(counts)) and (best is None or common > best[2]):
            best = (sep, next(i for i, c in enumerate(counts) if c == common), common)
    return (best[0], best[1]) if best else (None, 0)


def _is_header(fields):
    """A header row has at least one field that is not a number (so '1.2e-05' still counts as data)."""
    return any(f.strip() and not _NUMBER.match(f.strip().strip('"')) for f in fields)


def read_sensor_file(source):
    """Read a sensor table: NASA C-MAPSS text (whitespace separated, no header) or a table with named columns.

    The layout is worked out from the file itself: comma, semicolon, tab, pipe or whitespace separated,
    decimal commas (semicolon files from European Excel), UTF-8/UTF-16 text, and title lines above the table."""
    text = _read_text(source).replace("\r\n", "\n").replace("\r", "\n")
    lines = [line for line in text.split("\n") if line.strip() and not line.lstrip().startswith("#")]
    if not lines:
        raise InvalidDataError("The file is empty.")

    sep, start = _layout(lines[:SAMPLE_LINES])
    lines = lines[start:]
    header = _is_header(_split(lines[0], sep))
    sample = " ".join(lines[1:SAMPLE_LINES] if header else lines[:SAMPLE_LINES])
    decimal = "," if sep in (";", "\t", None) and re.search(r"\d,\d", sample) and "." not in sample else "."
    try:
        df = pd.read_csv(io.StringIO("\n".join(lines)), sep=r"\s+" if sep is None else sep, header=0 if header else None,
                         decimal=decimal, skipinitialspace=True, engine="python")
    except (pd.errors.ParserError, ValueError, csv.Error) as exc:
        raise InvalidDataError(f"Could not read the file as a table: {exc}") from exc
    df = df.dropna(axis=1, how="all")  # trailing separators leave empty columns
    if header:
        df.columns = [str(c).strip().strip('"') for c in df.columns]  # stray quotes or whitespace in headers
        return df

    if df.shape[1] != len(RAW_COLUMNS):
        raise InvalidDataError(
            f"Expected {len(RAW_COLUMNS)} columns (unit, cycle, 3 settings, 21 sensors), "
            f"found {df.shape[1]}. Files without a header row must use the NASA C-MAPSS layout; "
            "battery and bearing files need a header row."
        )
    df.columns = RAW_COLUMNS
    return df


def data_file(kind, profile=DATASET):
    """data/raw/<kind>_<profile>.txt for C-MAPSS subsets, .csv for other components."""
    ext = ".txt" if spec_of_profile(profile).key == "turbofan" else ".csv"
    return RAW_DATA_DIR / f"{kind}_{profile}{ext}"


def _load(kind, profile):
    return to_canonical(read_sensor_file(data_file(kind, profile)), spec_of_profile(profile))


def load_train(dataset=DATASET):
    return _load("train", dataset)


def load_test(dataset=DATASET):
    return _load("test", dataset)


def load_test_rul(dataset=DATASET):
    """True RUL at the last cycle of each test unit, indexed by unit number (in file order)."""
    values = pd.read_csv(RAW_DATA_DIR / f"RUL_{dataset}.txt", header=None).iloc[:, 0]  # one RUL per line
    if spec_of_profile(dataset).key == "turbofan":
        index = range(1, len(values) + 1)
    else:  # units are numbered by cell or bearing, in the order they appear in the test file
        index = pd.unique(load_test(dataset)["unit"])
    return pd.Series(values.to_numpy(), index=index, name="true_rul")
