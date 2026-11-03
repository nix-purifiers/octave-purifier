"""Rebuild actual compiled package archives and their native registry environments."""

from pathlib import Path
import re
import subprocess

repo = Path(__file__).resolve().parent.parent
system = subprocess.check_output(
    ["nix", "eval", "--impure", "--raw", "--expr", "builtins.currentSystem"], text=True
).strip()
outputs = subprocess.check_output(
    [
        "nix",
        "build",
        "--no-link",
        "--print-out-paths",
        str(repo) + "#checks." + system + ".environment",
        str(repo) + "#checks." + system + ".project",
    ],
    text=True,
).splitlines()
requisites = subprocess.check_output(
    ["nix-store", "-q", "--requisites", *outputs], text=True
).splitlines()
selected = [
    path
    for path in requisites
    if re.search(
        r"-octave-purified-(control|signal)-[0-9.]+$|-octave-[0-9.]+-purifierproof-[0-9.]+$",
        path,
    )
]
assert len(selected) == 3, selected
environments = [
    str(Path(outputs[0]) / "packages"),
    str(Path(outputs[1]) / "environment"),
]
for output in [*selected, *environments]:
    drv = subprocess.check_output(
        ["nix-store", "-q", "--deriver", str(Path(output).resolve())], text=True
    ).strip()
    subprocess.run(["nix-store", "--realise", drv, "--check"], check=True)

print("Compiled Octave package archives and native registries rebuilt identically")
