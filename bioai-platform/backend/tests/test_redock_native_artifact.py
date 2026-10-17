"""The benchmark must consume native docked poses, not reinterpret SDF."""
from pathlib import Path
import runpy

import pytest

RUNNER = Path(__file__).resolve().parents[3] / "benchmark/fixtures/docking/run_redock_panel.py"


def test_native_pose_output_keeps_artifact_formats_distinct():
    read = runpy.run_path(str(RUNNER))["_native_pose_output"]
    native = "MODEL 1\nATOM native-pose\nENDMDL\n"
    result = {"result_pdbqt": native, "result_sdf": "different SDF export\n$$$$\n", "num_poses": 1}
    text, models = read(result)
    assert text == native
    assert models == {1: "ATOM native-pose\n"}


@pytest.mark.parametrize("result, message", [
    ({"result_sdf": "MODEL 1\nwrong artifact\nENDMDL\n", "num_poses": 1}, "native result_pdbqt"),
    ({"result_pdbqt": "SDF only\n$$$$\n", "num_poses": 1}, "no top model"),
    ({"result_pdbqt": "MODEL 1\nATOM\nENDMDL\n", "num_poses": 2}, "model count disagrees"),
])
def test_native_pose_output_rejects_missing_or_inconsistent_evidence(result, message):
    read = runpy.run_path(str(RUNNER))["_native_pose_output"]
    with pytest.raises(ValueError, match=message):
        read(result)
