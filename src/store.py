"""Past records of every unit: its sensor readings and the forecasts made for it, kept in a database.

Real logs arrive in pieces: this week's cycles of engine 34, next week's, and so on. The models read a unit's
whole history (rolling trends, health against its own early cycles), so a new piece is joined to the readings
already stored for that unit before it is scored. The result is the forecast a single complete log would give.

Where the records live:
  DATABASE_URL set (environment or .streamlit/secrets.toml), e.g. a Neon Postgres connection string
      -> that database
  not set -> a local SQLite file, data/history.db, so the feature works offline

Tables (created on first use):
  readings  one row per unit and cycle: the raw readings as JSON, so all five components share one table
  forecasts one row per unit per analysis: the latest cycle, predicted life, 80% range and risk band

A unit is identified by component, fleet (the model profile, e.g. FD001 or PCOE) and its id in the file, so
engine 34 of FD001 and engine 34 of FD003 stay apart.
"""

import json
import logging
import math
import os
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
from sqlalchemy import JSON, Column, DateTime, Float, Integer, MetaData, String, Table, create_engine, func, insert, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from src.config import ROOT

logger = logging.getLogger("aerosentinel")

LOCAL_DB = ROOT / "data" / "history.db"
MAX_STORE_ROWS = 250_000  # bigger uploads are scored but not stored (a free Neon project holds 0.5 GB)
CHUNK = 2_000  # rows per insert statement (7 parameters each; keeps under SQLite and Postgres limits)

metadata = MetaData()
readings = Table(
    "readings", metadata,
    Column("component", String(16), primary_key=True),
    Column("fleet", String(16), primary_key=True),
    Column("unit", String(32), primary_key=True),
    Column("cycle", Float, primary_key=True),
    Column("data", JSON, nullable=False),
    Column("source", String(255)),
    Column("stored_at", DateTime(timezone=True)),
)
forecasts = Table(
    "forecasts", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("component", String(16), nullable=False, index=True),
    Column("fleet", String(16), nullable=False),
    Column("unit", String(32), nullable=False),
    Column("cycle", Float, nullable=False),
    Column("cycles_seen", Integer),
    Column("predicted_rul", Float),
    Column("rul_low", Float),
    Column("rul_high", Float),
    Column("risk_band", String(24)),
    Column("source", String(255)),
    Column("job_id", String(32)),
    Column("created_at", DateTime(timezone=True)),
)


def _url(url):
    """SQLAlchemy URL. Neon hands out 'postgresql://...'; that needs the psycopg 3 driver named."""
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    if url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://"):]
    return url


def _clean(value):
    """JSON-safe scalar: numpy types to Python, NaN to None."""
    if hasattr(value, "item"):
        value = value.item()
    if isinstance(value, float) and math.isnan(value):
        return None
    return value


class HistoryStore:
    def __init__(self, url=None):
        url = url or os.environ.get("DATABASE_URL")
        if url:
            self.backend = "Neon" if "neon.tech" in url else "Postgres" if url.startswith("postgres") else "Database"
            self.engine = create_engine(_url(url), pool_pre_ping=True, pool_recycle=300)  # Neon idles connections out
        else:
            LOCAL_DB.parent.mkdir(parents=True, exist_ok=True)
            self.backend = "Local file"
            self.engine = create_engine(f"sqlite:///{LOCAL_DB}")
        metadata.create_all(self.engine)

    # ---------- reading back ----------
    def past(self, component, fleet, units):
        """Stored readings of these units as a table (unit, cycle, ...), empty when there are none."""
        units = [str(u) for u in units]
        with self.engine.connect() as conn:
            rows = conn.execute(select(readings.c.unit, readings.c.cycle, readings.c.data).where(
                readings.c.component == component, readings.c.fleet == fleet, readings.c.unit.in_(units))).all()
        if not rows:
            return pd.DataFrame()
        return pd.DataFrame([{**(json.loads(d) if isinstance(d, str) else d), "unit": u, "cycle": c} for u, c, d in rows])

    def merge(self, df, component, fleet, columns):
        """The upload joined to each unit's stored readings, and what was joined.

        A unit's new rows replace stored rows at the same cycles. A piece that starts later than the stored
        record continues it; one that starts at or before the stored first cycle is a complete log and is
        taken as it is (nothing joined), so re-uploading a full file never doubles it up."""
        stored = self.past(component, fleet, df["unit"].unique())
        if stored.empty:
            return df, {}
        keep = [c for c in columns if c in df.columns]
        key = df["unit"].astype(str)
        joined, added = [], {}
        for unit, piece in stored.groupby("unit"):
            new = df[key == unit]
            first_new = new["cycle"].min()
            if first_new <= piece["cycle"].min():
                continue
            older = piece[piece["cycle"] < first_new]
            if older.empty:
                continue
            older = older.assign(unit=new["unit"].iloc[0])  # back to the upload's own id type
            joined.append(older.reindex(columns=keep))
            added[unit] = {"cycles": len(older), "from": float(older["cycle"].min()), "to": float(older["cycle"].max())}
        if not joined:
            return df, {}
        merged = pd.concat([*joined, df[keep]], ignore_index=True).sort_values(["unit", "cycle"], kind="stable")
        return merged.reset_index(drop=True), added

    def forecasts_of(self, component, fleet, unit):
        """Every forecast made for one unit, oldest first."""
        with self.engine.connect() as conn:
            rows = conn.execute(select(forecasts).where(
                forecasts.c.component == component, forecasts.c.fleet == fleet, forecasts.c.unit == str(unit))
                .order_by(forecasts.c.created_at, forecasts.c.id)).mappings().all()
        return pd.DataFrame([dict(r) for r in rows])

    def summary(self):
        """Units on record: component, fleet, unit, cycles stored, last cycle, last stored."""
        with self.engine.connect() as conn:
            rows = conn.execute(select(readings.c.component, readings.c.fleet, readings.c.unit,
                                       func.count().label("cycles"), func.max(readings.c.cycle).label("last_cycle"),
                                       func.max(readings.c.stored_at).label("stored_at"))
                                .group_by(readings.c.component, readings.c.fleet, readings.c.unit)).mappings().all()
        return pd.DataFrame([dict(r) for r in rows])

    # ---------- writing ----------
    def save(self, df, component, fleet, columns, units=None, source=None, job_id=None):
        """Store an analysed upload's readings (replacing the same cycles) and its forecasts. Returns rows stored."""
        now = datetime.now(UTC)
        stored = 0
        keep = [c for c in columns if c in df.columns and c not in ("unit", "cycle")]
        with self.engine.begin() as conn:
            if len(df) <= MAX_STORE_ROWS:
                # Upsert: a cycle already on record is replaced by the new reading. One multi-row statement per
                # chunk keeps a remote database (Neon) to a handful of round trips, whatever the number of units.
                rows = [{"component": component, "fleet": fleet, "unit": str(r["unit"]), "cycle": float(r["cycle"]),
                         "data": {c: _clean(r[c]) for c in keep}, "source": source, "stored_at": now}
                        for r in df.drop_duplicates(["unit", "cycle"], keep="last").to_dict("records")]
                upsert = (pg_insert if conn.dialect.name == "postgresql" else sqlite_insert)(readings)
                upsert = upsert.on_conflict_do_update(
                    index_elements=["component", "fleet", "unit", "cycle"],
                    set_={"data": upsert.excluded.data, "source": upsert.excluded.source, "stored_at": upsert.excluded.stored_at})
                for i in range(0, len(rows), CHUNK):
                    conn.execute(upsert.values(rows[i:i + CHUNK]))
                stored = len(rows)
            if units is not None:
                conn.execute(insert(forecasts), [{
                    "component": component, "fleet": fleet, "unit": str(r["unit"]), "cycle": float(r["cycle"]),
                    "cycles_seen": _clean(r.get("cycles_seen")),
                    **{k: _clean(r.get(k)) for k in ("predicted_rul", "rul_low", "rul_high", "risk_band")},
                    "source": source, "job_id": job_id, "created_at": now,
                } for r in units.to_dict("records")])
        return stored


_stores = {}


def get_store(url=None):
    """One store per database URL, or None when the database cannot be reached (the analysis then runs without it)."""
    key = url or os.environ.get("DATABASE_URL") or str(LOCAL_DB)
    if key not in _stores:
        try:
            _stores[key] = HistoryStore(url)
        except Exception:  # noqa: BLE001 - a missing database must never stop an analysis
            logger.exception("history store unavailable")
            return None
    return _stores[key]


def local_path():
    return Path(LOCAL_DB)
