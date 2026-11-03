"""Validate the lock protocol without import-from-derivation."""

import json
from pathlib import Path
import shutil
import subprocess
import tempfile

repo = Path(__file__).resolve().parent.parent
with tempfile.TemporaryDirectory() as temporary:
    root = Path(temporary) / "project"
    shutil.copytree(
        repo / "examples/minimal",
        root,
        ignore=shutil.ignore_patterns(".octave-purifier", "*.oct"),
    )
    companion = root / "octave-purifier.lock.json"
    original = json.loads(companion.read_text())

    def inspect():
        expression = f"let f=builtins.getFlake {json.dumps(str(repo))};lock=f.lib.octave-purifier.readLock {{src=/. + {json.dumps(str(root))};}};in {{inherit(lock)problems outputs;fetches=map(e: e.path)lock.entries;}}"
        return json.loads(
            subprocess.check_output(
                [
                    "nix",
                    "eval",
                    "--impure",
                    "--json",
                    "--option",
                    "allow-import-from-derivation",
                    "false",
                    "--expr",
                    expression,
                ],
                text=True,
            )
        )

    valid = inspect()
    assert valid["problems"] == [] and valid["outputs"]["packages"] == [
        "default",
        "environment",
        "project",
    ]
    companion.unlink()
    assert inspect()["problems"]
    for mutation in [
        lambda d: d.update(purifier="other"),
        lambda d: d["entries"][0].update(hash="invalid"),
        lambda d: d["nodes"][0].update(entry="../escape.tgz"),
        lambda d: d.update(project=None),
        lambda d: d.update(sdk=None),
    ]:
        data = json.loads(json.dumps(original))
        mutation(data)
        companion.write_text(json.dumps(data))
        assert inspect()["problems"]
    companion.write_text(json.dumps(original))
    (root / "DESCRIPTION").write_text("# stale\n")
    assert inspect()["problems"]

print("Octave lock validation passed without IFD")
