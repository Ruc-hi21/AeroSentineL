"""Dashboard smoke tests with Streamlit's AppTest: every page renders without an exception,
for every component's results (turbofan, battery, gearbox, hydraulic, power electronics)."""

import pytest

from src.config import DATASET, MODEL_VERSION, RAW_DATA_DIR, ROOT
from src.models.artifacts import available_subsets, model_dir
from src.pipeline import analyze

streamlit_testing = pytest.importorskip("streamlit.testing.v1")
APP = str(ROOT / "app" / "streamlit_app.py")
TEST_FILE = RAW_DATA_DIR / f"test_{DATASET}.txt"
FILES = {"turbofan": TEST_FILE, "battery": RAW_DATA_DIR / "sample_PCOE.csv", "bearing": RAW_DATA_DIR / "test_FEMTO.csv",
         "hydraulic": RAW_DATA_DIR / "test_UCI.csv", "power": RAW_DATA_DIR / "sample_IGBT.csv"}
PROFILE = {"turbofan": DATASET, "battery": "PCOE", "bearing": "FEMTO", "hydraulic": "UCI", "power": "IGBT"}
pytestmark = pytest.mark.skipif(
    not (model_dir(MODEL_VERSION, DATASET) / "metadata.json").exists() or not TEST_FILE.exists(),
    reason="trained model or dataset not available",
)
PAGES = ["overview", "upload", "engine", "twin", "health", "rul_risk", "explainability", "evaluation",
         "error_analysis", "export"]
COMPONENTS = [c for c in FILES if FILES[c].exists() and PROFILE[c] in available_subsets()]


def run_page(page, result=None, source=TEST_FILE.name):
    at = streamlit_testing.AppTest.from_file(APP, default_timeout=60)
    if result is not None:
        at.session_state["result"] = result
        at.session_state["source_name"] = source
    at.switch_page(f"views/{page}.py")
    return at.run()


@pytest.fixture(scope="module")
def results():
    return {c: analyze(FILES[c], subset=PROFILE[c]) for c in COMPONENTS}


@pytest.mark.parametrize("page", PAGES)
def test_page_renders_before_any_upload(page):
    at = run_page(page)
    assert not at.exception, at.exception


@pytest.mark.parametrize("component", COMPONENTS)
@pytest.mark.parametrize("page", PAGES)
def test_page_renders_with_results(page, component, results):
    at = run_page(page, results[component], FILES[component].name)
    assert not at.exception, at.exception


def test_upload_sample_and_analyze():
    at = run_page("upload")
    next(b for b in at.button if "sample file" in b.label).click().run()
    run = next(b for b in at.button if "Run analysis" in b.label)
    run.click().run()
    assert not at.exception, at.exception
    assert at.session_state["result"].status == "COMPLETED"
    assert at.session_state["result"].subset == DATASET
    assert any("Analysis complete" in s.value for s in at.success)


def test_empty_page_launches_sample():
    at = run_page("twin")
    launch = next(b for b in at.button if "Load NASA sample" in b.label)
    launch.click().run()
    assert not at.exception, at.exception
    assert at.session_state["result"].status == "COMPLETED"


def test_engine_page_steps_through_units(results):
    at = run_page("engine", results["turbofan"])
    first = at.session_state["selected_unit"]
    next(b for b in at.button if b.label == "Next").click().run()
    assert not at.exception, at.exception
    assert at.session_state["selected_unit"] != first
