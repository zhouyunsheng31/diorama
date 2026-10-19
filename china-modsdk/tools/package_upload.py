#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build the zip the China developer platform accepts, entirely off-line.

The platform's own upload rules (官方「资源上传规则」和「打包错误信息汇整」) are
stricter than "a working pack": the archive is inspected before it is ever
loaded, and a rejected archive only tells you an error number. This script
applies those rules *before* upload so a failure is caught here instead of on a
phone:

* the zip root holds exactly two folders, ``behavior_pack_<name>`` and
  ``resource_pack_<name>`` - wrapping them in another folder is error 10;
* nothing else sits at the root (error 24);
* the behavior pack contains ``entities/`` and the resource pack contains
  ``textures/`` (error 24);
* ``min_engine_version`` is at least ``[1, 18, 0]`` (error 37);
* every JSON file is UTF-8 without a BOM and parses (errors 38/40);
* no ``.MCP`` files and no compiled leftovers (error 36);
* paths and folder names are ASCII (errors 16/27).

Usage::

    python3 tools/package_upload.py --out dist
"""

from __future__ import print_function

import argparse
import io
import json
import os
import re
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, os.pardir))
MOD_ROOT = os.path.join(ROOT, "DioramaMod", "behavior_packs")
RES_ROOT = os.path.join(ROOT, "DioramaMod", "resource_packs")

BEHAVIOR_PACK_DIR = "behavior_pack_diorama"
RESOURCE_PACK_DIR = "resource_pack_diorama"

#: Files the platform refuses to see in an archive (error 36).
FORBIDDEN_SUFFIXES = (".mcp", ".pyc", ".pyo")

#: Junk that must never be shipped.
SKIP_DIRS = frozenset(("__pycache__", ".git", ".idea", ".vscode"))
SKIP_FILES = frozenset((".DS_Store", "Thumbs.db"))

ASCII_RE = re.compile(r"^[\x20-\x7e]+$")

#: Error 37: the platform requires at least this engine version.
MIN_ENGINE_VERSION = (1, 18, 0)


class Report(object):
    def __init__(self):
        self.errors = []
        self.warnings = []

    def error(self, where, message):
        self.errors.append((where, message))

    def warn(self, where, message):
        self.warnings.append((where, message))

    def ok(self):
        return not self.errors


def _find_pack(root, candidates):
    """First existing pack directory under ``root``."""
    for name in candidates:
        path = os.path.join(root, name)
        if os.path.isdir(path):
            return path
    # Fall back to "the only directory here".
    found = [
        os.path.join(root, name)
        for name in sorted(os.listdir(root))
        if os.path.isdir(os.path.join(root, name))
    ]
    return found[0] if len(found) == 1 else None


def _iter_files(base):
    """Every file under ``base`` as a path relative to it, POSIX separators."""
    for dirpath, dirnames, filenames in os.walk(base):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for name in sorted(filenames):
            if name in SKIP_FILES:
                continue
            full = os.path.join(dirpath, name)
            rel = os.path.relpath(full, base).replace(os.sep, "/")
            yield rel, full


def _check_manifest(pack_dir, kind, report):
    names = ("manifest.json", "pack_manifest.json")
    path = None
    for name in names:
        candidate = os.path.join(pack_dir, name)
        if os.path.isfile(candidate):
            path = candidate
            break
    if path is None:
        report.error(pack_dir, "no manifest.json / pack_manifest.json")
        return None
    handle = open(path, "rb")
    try:
        raw = handle.read()
    finally:
        handle.close()
    if raw.startswith(b"\xef\xbb\xbf"):
        report.error(path, "manifest has a UTF-8 BOM")
        raw = raw[3:]
    try:
        manifest = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as exc:
        report.error(path, "manifest is not valid UTF-8 JSON: %s" % (exc,))
        return None
    header = manifest.get("header") or {}
    engine = header.get("min_engine_version")
    if not isinstance(engine, list) or len(engine) != 3:
        report.error(path, "header.min_engine_version must be [x, y, z]")
    elif tuple(engine) < MIN_ENGINE_VERSION:
        report.error(
            path,
            "min_engine_version %r is below the required %r"
            % (engine, list(MIN_ENGINE_VERSION)),
        )
    modules = manifest.get("modules")
    if not isinstance(modules, list) or not modules:
        report.error(path, "manifest has no modules")
    else:
        wanted = "data" if kind == "behavior" else "resources"
        types = [m.get("type") for m in modules if isinstance(m, dict)]
        if wanted not in types:
            report.error(path, "no module of type %r (found %r)" % (wanted, types))
    if not header.get("uuid"):
        report.error(path, "header.uuid is empty")
    return manifest


def _check_tree(pack_dir, kind, report):
    required = "entities" if kind == "behavior" else "textures"
    if not os.path.isdir(os.path.join(pack_dir, required)):
        report.error(
            pack_dir,
            "missing required directory %r (error 24: behavior packs need "
            "entities/, resource packs need textures/ or shader/)" % (required,),
        )
    for rel, full in _iter_files(pack_dir):
        if not ASCII_RE.match(rel):
            report.error(full, "non-ASCII path (error 27): %r" % (rel,))
        lowered = rel.lower()
        for suffix in FORBIDDEN_SUFFIXES:
            if lowered.endswith(suffix):
                report.error(full, "forbidden file type %r (error 36)" % (suffix,))
        if lowered.endswith(".json"):
            handle = open(full, "rb")
            try:
                raw = handle.read()
            finally:
                handle.close()
            if raw.startswith(b"\xef\xbb\xbf"):
                report.error(full, "JSON has a UTF-8 BOM (error 40)")
                raw = raw[3:]
            try:
                json.loads(raw.decode("utf-8"))
            except (ValueError, UnicodeDecodeError) as exc:
                report.error(full, "JSON does not parse (error 38): %s" % (exc,))


def collect(report):
    behavior = _find_pack(MOD_ROOT, ("diorama_behavior_pack",))
    resource = _find_pack(RES_ROOT, ("diorama_resource_pack",))
    if behavior is None:
        report.error(MOD_ROOT, "no behavior pack directory")
    if resource is None:
        report.error(RES_ROOT, "no resource pack directory")
    if behavior is None or resource is None:
        return None, None
    _check_manifest(behavior, "behavior", report)
    _check_manifest(resource, "resources", report)
    _check_tree(behavior, "behavior", report)
    _check_tree(resource, "resources", report)
    return behavior, resource


def build(out_dir, report=None):
    """Write the platform zip; returns its path, or ``None`` on errors."""
    report = report or Report()
    behavior, resource = collect(report)
    if behavior is None or resource is None or not report.ok():
        return None
    version = "0.0.0"
    manifest_path = os.path.join(behavior, "manifest.json")
    if os.path.isfile(manifest_path):
        handle = open(manifest_path, "rb")
        try:
            version = ".".join(
                str(p) for p in json.loads(handle.read().decode("utf-8"))["header"]["version"]
            )
        except Exception:  # noqa: BLE001 - the version is cosmetic in the name
            version = "0.0.0"
        finally:
            handle.close()
    if not os.path.isdir(out_dir):
        os.makedirs(out_dir)
    name = "Diorama-China-upload-v%s.zip" % (version,)
    target = os.path.join(out_dir, name)
    handle = io.open(target, "wb") if sys.version_info[0] < 3 else open(target, "wb")
    try:
        archive = zipfile.ZipFile(handle, "w", zipfile.ZIP_DEFLATED)
        try:
            for pack_dir, prefix in (
                (behavior, BEHAVIOR_PACK_DIR),
                (resource, RESOURCE_PACK_DIR),
            ):
                archive.writestr(prefix.rstrip("/") + "/", b"")
                for rel, full in _iter_files(pack_dir):
                    archive.write(full, prefix + "/" + rel)
        finally:
            archive.close()
    finally:
        handle.close()
    return target


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Build the zip the China developer platform accepts"
    )
    parser.add_argument("--out", default=os.path.join(ROOT, "dist"))
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)
    report = Report()
    target = build(args.out, report)
    if not args.quiet:
        for where, message in report.errors:
            print("error  %s: %s" % (os.path.relpath(where, ROOT), message))
        for where, message in report.warnings:
            print("warn   %s: %s" % (os.path.relpath(where, ROOT), message))
    if target is None:
        print("upload package NOT built: %d error(s)" % (len(report.errors),))
        return 1
    print("upload package: %s" % (target,))
    print(
        "structure: %s/ + %s/ at the zip root, nothing else"
        % (BEHAVIOR_PACK_DIR, RESOURCE_PACK_DIR)
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
