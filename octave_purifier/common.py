import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile


def environment():
    env = {k: v for k, v in os.environ.items() if not k.startswith("OCTAVE")}
    env["OCTAVE_PATH"] = os.environ["OCTAVE_PURIFIER_NATIVE"]
    env["OCTAVE_HISTFILE"] = os.devnull
    return env


def native(code, env=None, cwd=None):
    result = subprocess.run(
        [
            os.environ["OCTAVE_PURIFIER_ORIGINAL"],
            "--no-init-all",
            "--quiet",
            "--eval",
            code,
        ],
        env=env or environment(),
        cwd=cwd,
        capture_output=True,
        text=True,
    )
    if result.returncode:
        raise ValueError(result.stdout + result.stderr)
    return result.stdout


def metadata(path):
    with tempfile.TemporaryDirectory(prefix="octave-metadata-") as tmp:
        out = Path(tmp) / "metadata.json"
        env = dict(environment(), PURIFIER_SOURCE=str(path), PURIFIER_OUTPUT=str(out))
        native(
            'd=purifier_metadata(getenv("PURIFIER_SOURCE"));fid=fopen(getenv("PURIFIER_OUTPUT"),"w");fputs(fid,jsonencode(d));fclose(fid);',
            env=env,
        )
        return json.loads(out.read_text())


def inputs(root, extra):
    names = sorted(
        set((["DESCRIPTION"] if (root / "DESCRIPTION").exists() else []) + list(extra))
    )
    result = {}
    for name in names:
        path = root / name
        if (
            Path(name).is_absolute()
            or ".." in Path(name).parts
            or not path.is_file()
            or path.is_symlink()
        ):
            raise ValueError("Selection inputs must be regular project files")
        result[name] = {"sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    return result


def load(root, companion):
    data = json.loads(companion.read_text())
    if data.get("version") != 1 or data.get("purifier") != "octave":
        raise ValueError("Unsupported Octave lock")
    if data["sdk"] != os.environ["OCTAVE_PURIFIER_SDK_VERSION"]:
        raise ValueError("Octave SDK changed; update the lock")
    if data["inputs"] != inputs(root, data["extraInputs"]):
        raise ValueError("Selection inputs changed; update the lock")
    return data
