"""NARROW-06 · text that stopped being true, on the surfaces people read today.

Each case names the claim, where it lived, and what made it false:

1. "Flint is a commercial MVP (S1)": `DEC-066` changed the goal to open source,
   self-use. The claim sat in the reason a source candidate was not adopted, in code
   (`flint/sources/candidates.py`) and in the seed the registry is built from.
   Whether Reddit's non-commercial free tier now fits is left open for me to judge;
   the text says that instead of answering it;
2. "`start-demo.sh` has never run on a real Mac": it ran end to end on this Mac,
   exit 0 (`docs/trace/MAC-01.md` section 7.1), and the stack it started is up;
3. README and the macOS setup doc each described the model wiring differently, and
   both went stale with `NARROW-04`: the demo stack now takes a keyed hosted model
   through `FLINT_DEMO_PROVIDER`;
4. the setup doc still called the Python version undecided; `DEC-068` decided it;
5. `AGENTS.md` mirrors `CLAUDE.md` for other agents and still carried the pre-`DEC-066`
   goal. It now matches `CLAUDE.md` word for word below the title line.

Dated records (handoff notes, steward reports, old plans, traces) keep what they said
then; they are not checked here.
"""
from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
README = REPO / "README.md"
SETUP = REPO / "docs" / "macOS-安装.md"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_no_live_surface_calls_flint_a_commercial_mvp() -> None:
    for path in (REPO / "flint" / "sources" / "candidates.py",
                 REPO / "assets" / "source_registry_seed.yaml"):
        text = _read(path)
        assert "商用 MVP" not in text, path
        assert "DEC-066" in text, f"{path} should say what changed the goal"


def test_the_readme_no_longer_says_the_mac_script_never_ran() -> None:
    text = _read(README)
    assert "还没有在 macOS 实机上跑过" not in text
    assert "docs/trace/MAC-01.md" in text


def test_readme_and_setup_doc_tell_the_same_model_story() -> None:
    for path in (README, SETUP):
        text = _read(path)
        assert "FLINT_DEMO_PROVIDER" in text, path
        assert "harness/demo_model.py" in text, path
        for stale in ("演示栈目前只接不要密钥", "尚未落到代码上", "还没有落到代码上",
                      "演示栈没有接它们"):
            assert stale not in text, (path, stale)


def test_the_setup_doc_no_longer_calls_the_python_version_open() -> None:
    text = _read(SETUP)
    assert "Python 版本有一处未决" not in text
    assert "DEC-068" in text


def test_agents_md_mirrors_the_charter_below_its_title() -> None:
    agents = _read(REPO / "AGENTS.md").splitlines()
    claude = _read(REPO / "CLAUDE.md").splitlines()
    assert agents[0].startswith("# AGENTS.md")
    assert claude[0].startswith("# CLAUDE.md")
    assert agents[1:] == claude[1:]
