"""Dashboard smoke tests with Streamlit's AppTest: every page renders without an exception."""

import pytest

from src.config import DATASET, MODEL_VERSION, MODELS_DIR, RAW_DATA_DIR, ROOT
from src.pipeline import analyze

streamlit_testing = pytest.importorskip("streamlit.testing.v1")
APP = str(ROOT / "app" / "streamlit_app.py")
TEST_FILE = RAW_DATA_DIR / f"test_{DATASET}.txt"
pytestmark = pytest.mark.skipif(
    not (MODELS_DIR / MODEL_VERSION / "metadata.json").exists() or not TEST_FILE.exists(),
    reason="trained model or dataset not available",
)
PAGES = ["overview", "upload", "twin", "health", "rul_risk", "explainability", "evaluation",
         "error_analysis", "export"]


def run_page(page, result=None):
    at = streamlit_testing.AppTest.from_file(APP, default_timeout=60)
    if result is not None:
        at.session_state["result"] = result
        at.session_state["source_name"] = TEST_FILE.name
    at.switch_page(f"views/{page}.py")
    return at.run()


@pytest.fixture(scope="module")
def result():
    return analyze(TEST_FILE)


@pytest.mark.parametrize("page", PAGES)
def test_page_renders_before_any_upload(page):
    at = run_page(page)
    assert not at.exception, at.exception


@pytest.mark.parametrize("page", PAGES)
def test_page_renders_with_results(page, result):
    at = run_page(page, result)
    assert not at.exception, at.exception


def test_upload_sample_and_analyze():
    at = run_page("upload")
    at.button[0].click().run()  # "use the sample" button
    run = next(b for b in at.button if "Run analysis" in b.label)
    run.click().run()
    assert not at.exception, at.exception
    assert at.session_state["result"].status == "COMPLETED"
    assert any("Analysis complete" in s.value for s in at.success)


def test_empty_page_launches_sample():
    at = run_page("twin")
    launch = next(b for b in at.button if "Launch" in b.label)
    launch.click().run()
    assert not at.exception, at.exception
    assert at.session_state["result"].status == "COMPLETED"
