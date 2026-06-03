from sandhyavandanam_guru import config
from sandhyavandanam_guru.ritual_loader import load_ritual


def test_pratah_loads_with_26_actions():
    ritual = load_ritual(config.RITUAL_DIR / "pratah_rigveda.yaml")
    assert ritual.sandhya_kind == "pratah"
    assert len(ritual.steps) == 26
    # Every step has a mantra reference and non-trivial content.
    for step in ritual.steps:
        assert step.mantra_id
        assert step.mantra_text.strip()
        assert step.translation.strip()


def test_step_ids_are_unique():
    ritual = load_ritual(config.RITUAL_DIR / "pratah_rigveda.yaml")
    ids = [s.id for s in ritual.steps]
    assert len(ids) == len(set(ids))


def test_first_and_last_steps():
    ritual = load_ritual(config.RITUAL_DIR / "pratah_rigveda.yaml")
    assert ritual.steps[0].id == "01_aachamanam"
    assert ritual.steps[-1].id == "26_rakshaa"
