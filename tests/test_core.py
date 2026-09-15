from pathlib import Path
import pytest
from classicvoice.core import PRESETS, build_espeak_command


def test_presets_have_unique_keys_and_labels():
    assert len({p.key for p in PRESETS}) == len(PRESETS)
    assert len({p.label for p in PRESETS}) == len(PRESETS)


def test_espeak_command_contains_selected_settings():
    cmd = build_espeak_command("espeak-ng", "Hola   mundo", Path("out.wav"), PRESETS[0], 150, 40, 90)
    joined = " ".join(cmd)
    assert "-s 150" in joined
    assert "-p 40" in joined
    assert "-a 90" in joined
    assert cmd[-1] == "Hola mundo"


def test_empty_text_is_rejected():
    with pytest.raises(ValueError):
        build_espeak_command("espeak-ng", "  ", Path("out.wav"), PRESETS[0])
