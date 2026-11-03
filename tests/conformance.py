"""Exercise native compiled packages, mutable source and ordinary consumers."""

import hashlib
import json
import os
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
    / "bin"
)


def run(args, root, expected=0, env=None, **kwargs):
    result = subprocess.run(
        [str(x) for x in args],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
        **kwargs,
    )
    assert result.returncode == expected, (
        args,
        result.returncode,
        result.stdout,
        result.stderr,
    )
    return result


with tempfile.TemporaryDirectory(prefix="octave-conformance-") as temporary:
    temporary = Path(temporary)
    root = temporary / "project with spaces"
    shutil.copytree(
        repo / "examples/minimal",
        root,
        ignore=shutil.ignore_patterns(".octave-purifier"),
    )
    env = dict(
        os.environ,
        OCTAVE_PATH=str(temporary / "poison"),
        OCTAVE_SITE_INITFILE=str(temporary / "poison.m"),
    )
    (temporary / "poison.m").write_text('error("Poisoned startup");\n')
    run([cli / "octave-cli", "--quiet", "--eval", "pkg install ."], root, env=env)
    code = 'pkg load purifierproof; assert(purifier_answer(),42); disp(which("upfirdn")); disp(which("purifier_native"));'
    result = run([cli / "octave-cli", "--quiet", "--eval", code], root, env=env)
    assert (
        "/nix/store/" in result.stdout
        and ".octave-purifier" in result.stdout
        and "api-" in result.stdout
    )
    source = root / "src/purifier_native.cc"
    original = source.read_text()
    source.write_text(original.replace("octave_value(42)", "octave_value(43)"))
    run([cli / "octave-cli", "--quiet", "--eval", "pkg install ."], root, env=env)
    run([cli / "octave-cli", "--quiet", "--eval", code], root, expected=1, env=env)
    source.write_text(original)
    run([cli / "octave-cli", "--quiet", "--eval", "pkg install ."], root, env=env)
    run([cli / "octave-cli", "--quiet", "--eval", code], root, env=env)
    for forbidden in [
        "pkg install absentpurifierpackage",
        "pkg update",
        "pkg list -forge",
        "pkg prefix /tmp/unlocked",
    ]:
        rejected = run(
            [cli / "octave-cli", "--quiet", "--eval", forbidden],
            root,
            expected=1,
            env=env,
        )
        assert "octave-purifier:" in rejected.stderr, rejected
    description = root / "DESCRIPTION"
    saved = description.read_text()
    description.write_text(saved + "\n")
    stale = run(
        [cli / "octave-cli", "--quiet", "--eval", "disp(42)"], root, expected=1, env=env
    )
    assert "inputs changed" in stale.stderr
    description.write_text(saved)
    companion = temporary / "external.json"
    (root / "octave-purifier.lock.json").rename(companion)
    external = dict(
        env, OCTAVE_PURIFIER_PROJECT=str(root), OCTAVE_PURIFIER_LOCK=str(companion)
    )
    nested = root / "nested"
    nested.mkdir()
    run([cli / "octave-cli", "--quiet", "--eval", code], nested, env=external)
    profile = root / ".octave-purifier/environment-profile"
    references = subprocess.check_output(
        ["nix-store", "-q", "--requisites", profile.resolve()], text=True
    )
    assert "octave-purifier-" in references and "octave-purified-control" in references
    environment = Path(json.loads(profile.resolve().read_text())["output"])
    fallback = temporary / "fallback"
    fallback.mkdir()
    ordinary = run([cli / "octave-cli", "--quiet", "--eval", "disp(42)"], fallback)
    assert ordinary.stdout.strip() == "42" and "impure" in ordinary.stderr
    streams = run(
        [
            cli / "octave-purifier",
            "exec",
            "--project",
            fallback,
            "--",
            "python3",
            "-c",
            "import sys; print(sys.stdin.read().strip()); print('native-stderr',file=sys.stderr);sys.exit(7)",
        ],
        fallback,
        expected=7,
        input="native-stdin\n",
    )
    assert (
        streams.stdout.strip() == "native-stdin"
        and "native-stderr" in streams.stderr
        and "impure" in streams.stderr
    )
    wrong = fallback / "wrong_api.cc"
    wrong.write_text(
        '#include <octave/oct.h>\n#undef OCTAVE_API_VERSION\n#define OCTAVE_API_VERSION "api-purifier-incompatible"\nDEFUN_DLD(wrong_api,args,nargout,"ABI proof"){return octave_value(42); }\n'
    )
    run(
        [
            cli / "octave-purifier",
            "exec",
            "--project",
            fallback,
            "--",
            "mkoctfile",
            wrong,
            "-o",
            fallback / "wrong_api.oct",
        ],
        fallback,
    )
    incompatible = run(
        [cli / "octave-cli", "--quiet", "--eval", "wrong_api()"], fallback, expected=1
    )
    assert "does not match the running Octave" in incompatible.stderr
    artifacts = Path(
        run(
            [cli / "octave-purifier", "bundle", "--project", root, "--lock", companion],
            root,
        ).stdout.strip()
    )
    (archive,) = artifacts.glob("*.tar.gz")
    fake = temporary / "fake-gh"
    record = temporary / "publication.json"
    fake.write_text(
        "#!/usr/bin/env python3\nimport hashlib,json,os,pathlib,sys\npathlib.Path(os.environ['PUBLICATION_RECORD']).write_text(json.dumps({'args':sys.argv[1:],'hash':hashlib.sha256(pathlib.Path(sys.argv[4]).read_bytes()).hexdigest()}))\n"
    )
    fake.chmod(0o755)
    run(
        [
            cli / "octave-purifier",
            "publish",
            "--tag",
            "v0.1.0",
            "--project",
            root,
            "--lock",
            companion,
        ],
        root,
        env=dict(
            os.environ, OCTAVE_PURIFIER_GH=str(fake), PUBLICATION_RECORD=str(record)
        ),
    )
    published = json.loads(record.read_text())
    assert published == {
        "args": ["release", "upload", "v0.1.0", str(archive), "--clobber"],
        "hash": hashlib.sha256(archive.read_bytes()).hexdigest(),
    }
    # No companion and no scoped pkg: ordinary native installer consumes the source archive.
    consumer = temporary / "consumer"
    consumer.mkdir()
    consumer_code = f'pkg("global_list",{json.dumps(str(environment / "global-registry"))});pkg("local_list",{json.dumps(str(consumer / "registry"))});pkg("prefix",{json.dumps(str(consumer / "packages"))},{json.dumps(str(consumer / "packages"))});pkg("install",{json.dumps(str(archive))});pkg load purifierproof;assert(purifier_answer(),42);disp(which("pkg"));'
    consumed = run(
        [cli / "octave-cli", "--no-init-all", "--quiet", "--eval", consumer_code],
        consumer,
    )
    assert (
        "octave-purifier-native" not in consumed.stdout and "impure" in consumed.stderr
    )

print(
    "Native Octave compiled source, package activation, isolation and publication passed"
)
