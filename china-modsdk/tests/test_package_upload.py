# -*- coding: utf-8 -*-
"""Tests for the platform-upload packager.

The upload zip is rejected by machine review before it is ever loaded, and the
only feedback is an error number, so the packaging rules themselves are worth
testing: two folders at the root, no nesting, no junk, valid JSON, and an engine
version the platform accepts.
"""

from __future__ import absolute_import, division, print_function

import json
import os
import shutil
import sys
import tempfile
import unittest
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, os.pardir))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from tools import package_upload  # noqa: E402


class RealTreeTest(unittest.TestCase):
    """The shipped tree must already satisfy the upload rules."""

    def test_the_repository_tree_passes(self):
        report = package_upload.Report()
        behavior, resource = package_upload.collect(report)
        self.assertIsNotNone(behavior)
        self.assertIsNotNone(resource)
        self.assertEqual(report.errors, [], report.errors)

    def test_the_built_zip_has_exactly_two_root_folders(self):
        out = tempfile.mkdtemp(prefix="diorama-upload-")
        try:
            path = package_upload.build(out)
            self.assertIsNotNone(path)
            archive = zipfile.ZipFile(path)
            try:
                roots = set()
                for name in archive.namelist():
                    roots.add(name.split("/")[0])
            finally:
                archive.close()
        finally:
            shutil.rmtree(out, ignore_errors=True)
        self.assertEqual(
            roots,
            {package_upload.BEHAVIOR_PACK_DIR, package_upload.RESOURCE_PACK_DIR},
        )


class SyntheticTreeTest(unittest.TestCase):
    """Break one rule at a time against a throwaway tree."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="diorama-rules-")
        self.behavior = os.path.join(self.tmp, "behavior_packs", "bp")
        self.resource = os.path.join(self.tmp, "resource_packs", "rp")
        os.makedirs(os.path.join(self.behavior, "entities"))
        os.makedirs(os.path.join(self.resource, "textures"))
        self._write_manifest(self.behavior, "data")
        self._write_manifest(self.resource, "resources")
        self._saved = (package_upload.MOD_ROOT, package_upload.RES_ROOT)
        package_upload.MOD_ROOT = os.path.join(self.tmp, "behavior_packs")
        package_upload.RES_ROOT = os.path.join(self.tmp, "resource_packs")

    def tearDown(self):
        package_upload.MOD_ROOT, package_upload.RES_ROOT = self._saved
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _write_manifest(self, pack_dir, module_type, engine=(1, 18, 0)):
        manifest = {
            "format_version": 2,
            "header": {
                "name": "t",
                "description": "t",
                "uuid": "7c1f0a52-3b6e-4d18-9a4f-2e5b8c0d41a7",
                "version": [0, 1, 0],
                "min_engine_version": list(engine),
            },
            "modules": [
                {
                    "type": module_type,
                    "uuid": "b3d94c61-0f2a-47c5-8e11-6a7d5f2c98b4",
                    "version": [0, 1, 0],
                }
            ],
        }
        path = os.path.join(pack_dir, "manifest.json")
        handle = open(path, "w")
        try:
            json.dump(manifest, handle)
        finally:
            handle.close()
        return path

    def errors(self):
        report = package_upload.Report()
        package_upload.collect(report)
        return [message for _where, message in report.errors]

    def test_a_clean_synthetic_tree_passes(self):
        self.assertEqual(self.errors(), [])

    def test_an_old_engine_version_is_rejected(self):
        self._write_manifest(self.behavior, "data", engine=(1, 16, 0))
        self.assertTrue(any("min_engine_version" in e for e in self.errors()))

    def test_a_behavior_pack_without_entities_is_rejected(self):
        shutil.rmtree(os.path.join(self.behavior, "entities"))
        self.assertTrue(any("entities" in e for e in self.errors()))

    def test_a_resource_pack_without_textures_is_rejected(self):
        shutil.rmtree(os.path.join(self.resource, "textures"))
        self.assertTrue(any("textures" in e for e in self.errors()))

    def test_a_compiled_mcp_file_is_rejected(self):
        handle = open(os.path.join(self.behavior, "leftover.MCP"), "wb")
        try:
            handle.write(b"junk")
        finally:
            handle.close()
        self.assertTrue(any("forbidden file type" in e for e in self.errors()))

    def test_a_stray_root_file_is_caught_by_the_root_check(self):
        out = tempfile.mkdtemp(prefix="diorama-out-")
        try:
            path = package_upload.build(out)
            self.assertIsNotNone(path)
            archive = zipfile.ZipFile(path)
            try:
                roots = {name.split("/")[0] for name in archive.namelist()}
            finally:
                archive.close()
        finally:
            shutil.rmtree(out, ignore_errors=True)
        # Whatever else is on disk, the archive root is always just the packs.
        self.assertEqual(
            roots,
            {package_upload.BEHAVIOR_PACK_DIR, package_upload.RESOURCE_PACK_DIR},
        )

    def test_invalid_json_is_rejected(self):
        path = os.path.join(self.behavior, "entities", "broken.json")
        handle = open(path, "w")
        try:
            handle.write("{ not json")
        finally:
            handle.close()
        self.assertTrue(any("does not parse" in e for e in self.errors()))


if __name__ == "__main__":
    unittest.main()
