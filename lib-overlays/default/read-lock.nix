{ lib }:
{
  src,
  lockFile ? src + "/octave-purifier.lock.json",
}:
let
  raw = if builtins.pathExists lockFile then builtins.fromJSON (builtins.readFile lockFile) else { };
  data = if builtins.isAttrs raw then raw else { };
  entries = data.entries or [ ];
  nodes = data.nodes or [ ];
  safe = s: builtins.isString s && builtins.match "[a-zA-Z0-9_+-]+" s != null;
  relative =
    s:
    builtins.isString s
    && s != ""
    && !(lib.hasPrefix "/" s)
    && !(builtins.elem ".." (lib.splitString "/" s));
  valid =
    (data.version or null) == 1
    && (data.purifier or null) == "octave"
    && builtins.isString (data.sdk or null)
    && builtins.isList (data.requirements or null)
    && builtins.all builtins.isString data.requirements
    && builtins.isList (data.extraInputs or null)
    && builtins.all relative data.extraInputs
    && builtins.isAttrs (data.inputs or null)
    &&
      builtins.attrNames data.inputs == builtins.sort builtins.lessThan (
        lib.unique (
          (lib.optional (builtins.pathExists (src + "/DESCRIPTION")) "DESCRIPTION") ++ data.extraInputs
        )
      )
    && builtins.all (
      name:
      relative name
      && builtins.pathExists (src + "/${name}")
      && builtins.isAttrs data.inputs.${name}
      && builtins.hashFile "sha256" (src + "/${name}") == (data.inputs.${name}.sha256 or null)
    ) (builtins.attrNames data.inputs)
    && data ? project
    && (data.project == null || (builtins.isAttrs data.project && safe (data.project.name or null)))
    && (data.project == null) == (!(data.inputs ? DESCRIPTION))
    && builtins.isList entries
    && builtins.isList nodes
    && builtins.all (
      e:
      builtins.isAttrs e
      && relative (e.path or null)
      && builtins.isString (e.url or null)
      && lib.hasPrefix "https://" e.url
      && builtins.isString (e.hash or null)
      && builtins.match "sha256-[A-Za-z0-9+/]{43}=" e.hash != null
      && (e.mirrors or null) == [ ]
      && !(e ? git)
    ) entries
    && builtins.all (
      n:
      builtins.isAttrs n
      && safe (n.name or null)
      && builtins.isAttrs (n.native or null)
      && n.native.name == n.name
      && builtins.isString (n.native.version or null)
      && builtins.isList (n.native.depends or null)
      && (n.entry or null) == "archives/${n.name}/${n.native.version}.tar.gz"
      && builtins.any (e: e.path == n.entry) entries
    ) nodes
    && builtins.length nodes == builtins.length entries
    && builtins.length (lib.unique (map (n: n.name) nodes)) == builtins.length nodes
    && builtins.length (lib.unique (map (e: e.path) entries)) == builtins.length entries;
in
{
  purifier = "octave";
  inherit data entries;
  problems = lib.optional (
    !valid
  ) "Octave lock is missing, stale or unsupported; run octave-purifier lock --update";
  outputs = {
    packages = [
      "default"
      "environment"
      "project"
    ];
    tests = [ "default" ];
    release = [ "default" ];
  };
}
