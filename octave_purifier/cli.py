import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile

from .capture import capture
from .common import environment, load


def locate(project=None, companion=None):
    root = Path(
        project or os.environ.get("OCTAVE_PURIFIER_PROJECT", Path.cwd())
    ).resolve()
    external = companion or os.environ.get("OCTAVE_PURIFIER_LOCK")
    if external:
        return root, Path(external).resolve()
    if project or os.environ.get("OCTAVE_PURIFIER_PROJECT"):
        return root, root / "octave-purifier.lock.json"
    for parent in [root, *root.parents]:
        if (parent / "octave-purifier.lock.json").exists():
            return parent, parent / "octave-purifier.lock.json"
    return root, root / "octave-purifier.lock.json"


def realize(root, companion, target="environment"):
    state = root / ".octave-purifier"
    state.mkdir(exist_ok=True)
    profile = state / (target + "-profile")
    result = subprocess.run(
        [
            "nix",
            "build",
            "--impure",
            "--file",
            str(Path(__file__).parent.parent / "nix/realize.nix"),
            "--argstr",
            "project",
            str(root),
            "--argstr",
            "companion",
            str(companion),
            "--argstr",
            "target",
            target,
            "--argstr",
            "sdk",
            os.environ["OCTAVE_PURIFIER_SDK"],
            "--arg",
            "profile",
            "true",
            "--out-link",
            str(profile),
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode:
        raise ValueError(result.stdout + result.stderr)
    return Path(json.loads(profile.resolve().read_text())["output"])


def source_archive(root, target):
    with tarfile.open(target, "w:gz") as bundle:
        bundle.add(
            root,
            arcname="project",
            filter=lambda info: (
                None
                if any(
                    p in (".git", ".octave-purifier", "__pycache__")
                    for p in Path(info.name).parts
                )
                else info
            ),
        )


def prepare(root, companion):
    data = load(root, companion)
    output = realize(root, companion)
    key = hashlib.sha256(
        (str(root) + str(output) + os.environ["OCTAVE_PURIFIER_SDK"]).encode()
    ).hexdigest()[:20]
    state = root / ".octave-purifier" / key
    state.mkdir(exist_ok=True)
    (state / "packages").mkdir(exist_ok=True)
    local = state / "local-registry"
    local.touch(exist_ok=True)
    archive = state / "project.tar.gz"
    if data["project"] is not None:
        source_archive(root, archive)
    env = dict(
        environment(),
        OCTAVE_PURIFIER_FROZEN="1",
        OCTAVE_PURIFIER_PREFIX=str(state / "packages"),
        OCTAVE_PURIFIER_LOCAL_LIST=str(local),
        OCTAVE_PURIFIER_GLOBAL_LIST=str(output / "global-registry"),
        OCTAVE_PURIFIER_MANIFEST=str(output / "manifest.json"),
        OCTAVE_PURIFIER_PROJECT=str(root),
        OCTAVE_PURIFIER_PROJECT_ARCHIVE=str(archive),
    )
    return env


def execute(args, root, companion, native=False):
    original = os.environ[
        "OCTAVE_PURIFIER_ORIGINAL_GUI"
        if native == "octave"
        else "OCTAVE_PURIFIER_ORIGINAL"
    ]
    if not companion.exists():
        print(
            "octave-purifier: no lockfile; using ordinary impure resolution",
            file=sys.stderr,
        )
        if native:
            os.execv(
                original,
                [original, *args],
            )
        os.execvp(args[0], args)
    env = prepare(root, companion)
    if native:
        if any(a in ("--no-init-path",) for a in args):
            raise ValueError("Locked native package search paths cannot be disabled")
        os.execve(
            original,
            [original, *args],
            env,
        )
    env["PATH"] = (
        str(Path(sys.argv[0]).resolve().parent) + os.pathsep + env.get("PATH", "")
    )
    env["OCTAVE_PURIFIER_LOCK"] = str(companion)
    os.execvpe(args[0], args, env)


def main():
    try:
        args = sys.argv[1:]
        if args and args[0] in ("--native=octave", "--native=octave-cli"):
            root, companion = locate()
            execute(args[1:], root, companion, native=args[0].split("=", 1)[1])
        parser = argparse.ArgumentParser()
        parser.add_argument(
            "command", choices=["lock", "prefetch", "exec", "bundle", "publish"]
        )
        parser.add_argument("requirements", nargs="*")
        parser.add_argument("--project", type=Path)
        parser.add_argument("--lock", type=Path)
        parser.add_argument("--update", action="store_true")
        parser.add_argument("--input", action="append", default=[])
        parser.add_argument("--tag")
        passthrough = []
        if "--" in args:
            index = args.index("--")
            passthrough, args = args[index + 1 :], args[:index]
        selected = parser.parse_args(args)
        root, companion = locate(selected.project, selected.lock)
        if selected.command == "lock":
            capture(
                root, companion, selected.requirements, selected.update, selected.input
            )
        elif selected.command == "exec":
            if not passthrough:
                raise ValueError("exec requires a command after --")
            execute(passthrough, root, companion)
        else:
            load(root, companion)
            output = realize(
                root,
                companion,
                "environment" if selected.command == "prefetch" else "release",
            )
            if selected.command == "publish":
                if not selected.tag:
                    raise ValueError("publish requires --tag")
                subprocess.run(
                    [
                        os.environ["OCTAVE_PURIFIER_GH"],
                        "release",
                        "upload",
                        selected.tag,
                        *map(str, sorted(output.iterdir())),
                        "--clobber",
                    ],
                    check=True,
                )
            else:
                print(output)
    except (ValueError, KeyError, OSError, subprocess.CalledProcessError) as error:
        print(f"octave-purifier: {error}", file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
