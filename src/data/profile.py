"""Choose which subset's model fits a file: by its name first, then by its operating conditions."""

import re

from src.config import AUTO_SUBSET, SUBSETS
from src.preprocessing.conditions import count_conditions

NAME_PATTERN = re.compile(r"FD00[1-4]", re.IGNORECASE)


def detect_subset(df, name=None):
    """Return (subset, reason). A name is trusted only if its condition count matches the data."""
    conditions = count_conditions(df)
    multi = conditions > 1
    match = NAME_PATTERN.search(str(name)) if name else None
    if match:
        subset = match.group(0).upper()
        if (SUBSETS[subset]["conditions"] > 1) == multi:
            return subset, f"named in the file ({name})"
    if multi:
        return AUTO_SUBSET["multi"], f"{conditions} operating conditions found in the data"
    return AUTO_SUBSET["single"], "a single operating condition found in the data"
