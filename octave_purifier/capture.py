import base64
import hashlib
import json
from pathlib import Path
import tempfile
import tarfile

from .common import environment, inputs, load, native


def capture(root, companion, requirements=(), update=False, extra=()):
    if companion.exists() and not update:
        load(root, companion)
        return
    previous = json.loads(companion.read_text()) if companion.exists() else {}
    requirements = list(requirements or previous.get("requirements", []))
    extra = list(extra or previous.get("extraInputs", []))
    with tempfile.TemporaryDirectory(prefix="octave-capture-") as tmp:
        tmp = Path(tmp)
        selected = list(requirements)
        project_index = None
        if (root / "DESCRIPTION").exists():
            archive = tmp / "project.tar.gz"
            with tarfile.open(archive, "w:gz") as bundle:
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
            project_index = len(selected)
            selected.append(str(archive))
        env = dict(
            environment(),
            OCTAVE_PURIFIER_CAPTURE=str(tmp),
            XDG_CONFIG_HOME=str(tmp / "config"),
            PURIFIER_SELECTION=json.dumps(selected),
            PURIFIER_STATE=str(tmp),
        )
        if selected:
            native(
                's=getenv("PURIFIER_STATE");pkg("local_list",fullfile(s,"local"));pkg("global_list",fullfile(s,"global"));pkg("prefix",fullfile(s,"prefix"),fullfile(s,"prefix"));args=jsondecode(getenv("PURIFIER_SELECTION"));pkg("install",args{:});',
                env=env,
                cwd=root,
            )
            descriptions = json.loads((tmp / "metadata.json").read_text())
            archives = json.loads((tmp / "archives.json").read_text())
            selections = json.loads((tmp / "selected.json").read_text())
            origins = (
                {
                    d["archive"]: d["url"]
                    for d in (
                        json.loads(x)
                        for x in (tmp / "origins.jsonl").read_text().splitlines()
                    )
                }
                if (tmp / "origins.jsonl").exists()
                else {}
            )
        else:
            descriptions, archives, selections, origins = [], [], [], {}
        entries, nodes, project = [], [], None
        for index, (desc, archive, selection) in enumerate(
            zip(descriptions, archives, selections, strict=True)
        ):
            if index == project_index:
                project = desc
                continue
            url = origins.get(selection)
            if not isinstance(url, str) or not url.startswith("https://"):
                raise ValueError("Selected packages require native HTTPS archive URLs")
            name, version = desc["name"], desc["version"]
            path = f"archives/{name}/{version}.tar.gz"
            digest = base64.b64encode(
                hashlib.sha256(Path(archive).read_bytes()).digest()
            ).decode()
            entries.append(
                {"path": path, "url": url, "hash": "sha256-" + digest, "mirrors": []}
            )
            nodes.append({"name": name, "native": desc, "entry": path})
        names = [n["name"] for n in nodes]
        if len(set(names)) != len(names) or (
            project is not None and project["name"] in names
        ):
            raise ValueError(
                "Selected packages and the project must have distinct native names"
            )
        data = {
            "version": 1,
            "purifier": "octave",
            "sdk": __import__("os").environ["OCTAVE_PURIFIER_SDK_VERSION"],
            "requirements": requirements,
            "extraInputs": extra,
            "inputs": inputs(root, extra),
            "project": project,
            "nodes": nodes,
            "entries": entries,
        }
        companion.parent.mkdir(parents=True, exist_ok=True)
        temporary = companion.with_suffix(companion.suffix + ".tmp")
        temporary.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")
        temporary.replace(companion)
