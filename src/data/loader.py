"""Read C-MAPSS sensor files from disk or from an uploaded file."""

import io
from pathlib import Path

import pandas as pd

from src.config import DATASET, RAW_COLUMNS, RAW_DATA_DIR
from src.errors import InvalidDataError


def _read_text(source):
    if isinstance(source, (str, Path)):
        return Path(source).read_text()
    content = source.read()  # file-like object, e.g. a Streamlit upload
    return content.decode("utf-8", errors="replace") if isinstance(content, bytes) else content


def read_sensor_file(source):
    """Read raw C-MAPSS text (whitespace separated, no header) or a CSV with named columns."""
    text = _read_text(source)
    if not text.strip():
        raise InvalidDataError("The file is empty.")

    first_line = text.lstrip().split("\n", 1)[0]
    try:
        if any(ch.isalpha() for ch in first_line):
            df = pd.read_csv(io.StringIO(text))
            df.columns = [str(c).strip() for c in df.columns]  # strip BOM or whitespace from headers
            return df
        df = pd.read_csv(io.StringIO(text), sep=r"\s+", header=None)
    except (pd.errors.ParserError, UnicodeDecodeError) as exc:
        raise InvalidDataError(f"Could not parse the file: {exc}") from exc

    if df.shape[1] != len(RAW_COLUMNS):
        raise InvalidDataError(
            f"Expected {len(RAW_COLUMNS)} columns (unit, cycle, 3 settings, 21 sensors), "
            f"found {df.shape[1]}."
        )
    df.columns = RAW_COLUMNS
    return df


def load_train(dataset=DATASET):
    return read_sensor_file(RAW_DATA_DIR / f"train_{dataset}.txt")


def load_test(dataset=DATASET):
    return read_sensor_file(RAW_DATA_DIR / f"test_{dataset}.txt")


def load_test_rul(dataset=DATASET):
    """True RUL at the last cycle of each test unit, indexed by unit number."""
    values = pd.read_csv(RAW_DATA_DIR / f"RUL_{dataset}.txt", header=None).iloc[:, 0]  # one RUL per line
    return pd.Series(values.to_numpy(), index=range(1, len(values) + 1), name="true_rul")
