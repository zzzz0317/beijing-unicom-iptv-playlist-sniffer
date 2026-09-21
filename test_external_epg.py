# SPDX-License-Identifier: AGPL-3.0-only

import contextlib
import gzip
import io
import json
from pathlib import Path
import runpy
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

import util


class ExternalEPGTests(unittest.TestCase):
    def generate(self, url, payload):
        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory)
            script = work / "epg.py"
            shutil.copyfile(Path(__file__).resolve().parent / "epg.py", script)
            raw = [{"channelID": "test", "userChannelID": 18,
                    "channelName": "CCTV-5+"}]
            (work / "raw.json").write_text(json.dumps(raw), encoding="utf-8")
            config = {
                "playlist_raw_path": str(work / "raw.json"),
                "epg_save_path": str(work / "epg.xml"),
                "epg_offset_start": 0,
                "epg_offset_end": 0,
                "epg_cache_external": True,
                "epg_cache_external_path": str(work / "cache"),
                "epg_external": [{
                    "name": "test", "url": url,
                    "channel": [{"tvg_name": "CCTV-5+",
                                 "tvg_id_iptv": 18, "tvg_id_ext": 6}],
                }],
            }
            (work / "config.json").write_text(json.dumps(config), encoding="utf-8")
            with patch.object(sys, "argv", [str(script)]), \
                    patch.object(util, "get_remote_content", return_value=(200, payload)) as fetch, \
                    contextlib.redirect_stdout(io.StringIO()) as output:
                runpy.run_path(str(script), run_name="__main__")
            fetch.assert_called_once_with(url, encoding=None)
            root = ET.parse(work / "epg.xml").getroot()
            cached = [json.loads(p.read_text(encoding="utf-8"))
                      for p in (work / "cache").glob("*.json")]
            return root, cached, output.getvalue()

    def test_maps_and_caches_xml_independent_of_url_suffix(self):
        xml = (b'<?xml version="1.0" encoding="UTF-8"?><tv>'
               b'<programme channel="6" start="20260921080000 +0800" '
               b'stop="20260921090000 +0800"><title lang="zh">Sports</title>'
               b'</programme></tv>')
        cases = [
            ("https://example.test/epg.xml.gz", xml),
            ("https://example.test/epg.xml", xml),
            ("https://example.test/epg.xml.gz", gzip.compress(xml)),
            ("https://example.test/epg.xml", gzip.compress(xml)),
            ("https://example.test/epg.xml.gz?token=test", gzip.compress(xml)),
        ]
        for url, payload in cases:
            with self.subTest(url=url, compressed=payload.startswith(b"\x1f\x8b")):
                root, cached, _ = self.generate(url, payload)
                self.assertEqual(root.find("channel").get("id"), "18")
                programme, = root.findall("programme")
                self.assertEqual(programme.get("channel"), "18")
                self.assertEqual(programme.findtext("title"), "Sports")
                self.assertEqual(programme.get("start"), "20260921080000 +0800")
                self.assertEqual(programme.get("stop"), "20260921090000 +0800")
                self.assertEqual(len(cached), 1)
                self.assertEqual(cached[0][0]["channel"], "18")
                self.assertEqual(cached[0][0]["title"], "Sports")

    def test_corrupt_gzip_is_still_skipped(self):
        root, cached, output = self.generate(
            "https://example.test/epg.xml.gz", b"\x1f\x8btruncated")
        self.assertEqual(root.findall("programme"), [])
        self.assertEqual(cached, [])
        self.assertIn("Failed to decompress EPG data", output)


if __name__ == "__main__":
    unittest.main()
