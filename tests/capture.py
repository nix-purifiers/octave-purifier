"""Native graph changes, empty documents, tracked inputs and metadata binding."""

import json
from pathlib import Path
import shutil
import subprocess
import tempfile

repo = Path(__file__).resolve().parent.parent
cli = (
    Path(
        subprocess.check_output(
            ["nix", "build", str(repo) + "#", "--no-link", "--print-out-paths"],
            text=True,
        ).strip()
    )
    / "bin/octave-purifier"
)

with tempfile.TemporaryDirectory(prefix="octave-capture-proof-") as temporary:
    temporary = Path(temporary)
    root = temporary / "project"
    root.mkdir()
    (root / "selection.txt").write_text("tracked input\n")
    companion = temporary / "external.json"

    def call(*args):
        return subprocess.run(
            [cli, *args, "--project", root, "--lock", companion],
            capture_output=True,
            text=True,
            check=True,
        )

    call("lock", "--input", "selection.txt")
    empty = json.loads(companion.read_text())
    assert empty["nodes"] == empty["entries"] == [] and empty["project"] is None
    call("prefetch")
    before = companion.read_bytes()
    call("lock")
    assert companion.read_bytes() == before
    shutil.copytree(
        repo / "examples/minimal",
        root,
        dirs_exist_ok=True,
        ignore=shutil.ignore_patterns("octave-purifier.lock.json", ".octave-purifier"),
    )
    assert subprocess.run(
        [cli, "prefetch", "--project", root, "--lock", companion], capture_output=True
    ).returncode
    call("lock", "control", "signal", "--update")
    selected = json.loads(companion.read_text())
    assert selected["extraInputs"] == ["selection.txt"]
    assert {n["name"] for n in selected["nodes"]} == {"control", "signal"}
    call("prefetch")
    selected["nodes"][0]["native"]["title"] = "Invalid metadata"
    companion.write_text(json.dumps(selected))
    failed = subprocess.run(
        [cli, "prefetch", "--project", root, "--lock", companion],
        capture_output=True,
        text=True,
    )
    assert failed.returncode and "metadata differs" in failed.stderr, failed

print(
    "Native Octave empty graph, explicit dependency selection, update and archive metadata binding passed"
)
