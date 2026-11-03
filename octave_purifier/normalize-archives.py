"""Normalize native binary-package container metadata, preserving compiled bytes."""

import gzip
from pathlib import Path
import sys
import tarfile

for archive in Path(sys.argv[1]).glob("*.tar.gz"):
    target = archive.with_suffix(".normalized")
    with tarfile.open(archive, "r:gz") as source, target.open("wb") as stream:
        with gzip.GzipFile(
            filename="", fileobj=stream, mode="wb", mtime=0
        ) as compressed:
            with tarfile.open(
                fileobj=compressed, mode="w", format=tarfile.GNU_FORMAT
            ) as output:
                for member in sorted(
                    source.getmembers(), key=lambda member: member.name
                ):
                    payload = source.extractfile(member) if member.isfile() else None
                    member.uid = member.gid = member.mtime = 0
                    member.uname = member.gname = ""
                    member.pax_headers = {}
                    output.addfile(member, payload)
                    if payload is not None:
                        payload.close()
    target.replace(archive)
