"""Dashboard smoke tests with Streamlit's AppTest: every page renders without an exception,
for every component's results (turbofan, battery, gearbox, hydraulic, power electronics)."""

import pytest

from src.config import DATASET, MODEL_VERSION, RAW_DATA_DIR, ROOT
from src.models.artifacts import available_subsets, model_dir
from src.pipeline import analyze

streamlit_testing = pytest.importorskip("streamlit.testing.v1")
APP = str(ROOT / "app" / "streamlit_app.py")
ADMIN_APP = str(ROOT / "app" / "admin_app.py")  # the admin console, a separate app on its own port
TEST_FILE = RAW_DATA_DIR / f"test_{DATASET}.txt"
FILES = {"turbofan": TEST_FILE, "battery": RAW_DATA_DIR / "sample_PCOE.csv", "bearing": RAW_DATA_DIR / "test_FEMTO.csv",
         "hydraulic": RAW_DATA_DIR / "test_UCI.csv", "power": RAW_DATA_DIR / "sample_IGBT.csv"}
PROFILE = {"turbofan": DATASET, "battery": "PCOE", "bearing": "FEMTO", "hydraulic": "UCI", "power": "IGBT"}
pytestmark = pytest.mark.skipif(
    not (model_dir(MODEL_VERSION, DATASET) / "metadata.json").exists() or not TEST_FILE.exists(),
    reason="trained model or dataset not available",
)
PAGES = ["overview", "fleet_detail", "upload", "engine", "engine_detail", "health", "rul_risk", "explainability", "twin",
         "export"]
ADMIN_PAGES = ["admin_models"]
COMPONENTS = [c for c in FILES if FILES[c].exists() and PROFILE[c] in available_subsets()]


def run_page(page, result=None, source=TEST_FILE.name, app=APP):
    at = streamlit_testing.AppTest.from_file(app, default_timeout=60)
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
    next(b for b in at.button if b.label == "Use this sample").click().run()
    run = next(b for b in at.button if "Run analysis" in b.label)
    run.click().run()
    assert not at.exception, at.exception
    assert at.session_state["result"].status == "COMPLETED"
    assert at.session_state["result"].subset == DATASET
    at.switch_page("views/fleet_detail.py").run()  # its Data check tab profiles the file that was analysed
    assert not at.exception, at.exception



def test_empty_page_points_to_ingest_only():
    """Samples live on Ingest data only: an empty page shows no sample button."""
    at = run_page("twin")
    assert not at.exception, at.exception
    assert not any("sample" in b.label.lower() for b in at.button)


def test_engine_page_steps_through_units(results):
    at = run_page("engine", results["turbofan"])
    first = at.session_state["selected_unit"]
    next(b for b in at.button if b.label == "Next").click().run()
    assert not at.exception, at.exception
    assert at.session_state["selected_unit"] != first


def test_samples_are_one_unit_each_and_recognised():
    """Every sample file holds one unit and is routed to its own model with no hint but the file name."""
    import io

    from app.components import SAMPLE_INFO, SAMPLES
    assert {i["state"] for i in SAMPLE_INFO.values()} == {"failing", "healthy"}
    for key, path in SAMPLES.items():
        assert path.exists(), path
        result = analyze(io.BytesIO(path.read_bytes()), name=path.name)
        assert result.status == "COMPLETED", (key, result.error)
        assert result.subset == SAMPLE_INFO[key]["profile"], key
        assert len(result.units) == 1, key


@pytest.mark.parametrize("page", ADMIN_PAGES)
def test_admin_page_renders_before_any_upload(page):
    at = run_page(page, app=ADMIN_APP)
    assert not at.exception, at.exception


@pytest.mark.parametrize("component", COMPONENTS)
@pytest.mark.parametrize("page", ADMIN_PAGES)
def test_admin_page_renders_with_results(page, component, results):
    at = run_page(page, results[component], FILES[component].name, app=ADMIN_APP)
    assert not at.exception, at.exception


def test_overview_is_the_landing_page_even_with_data_loaded(results):
    """Fleet overview never changes after an upload: the landing page, with its sample button, stays as it is."""
    at = run_page("overview", results["turbofan"])
    assert not at.exception, at.exception
    assert not any("sample" in b.label.lower() or "NASA" in b.label for b in at.button)  # samples: Ingest data only
    assert any("Which component fails next" in str(e.proto) for e in at.get("html"))  # the landing page itself
