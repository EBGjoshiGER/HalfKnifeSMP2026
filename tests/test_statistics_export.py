import importlib.util
import json
import ftplib
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location("sync_statistics", Path(__file__).parents[1] / "scripts/sync_statistics.py")
exporter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(exporter)
ALICE = "00000000-0000-0000-0000-000000000001"
BOB = "00000000-0000-0000-0000-000000000002"
OTHER = "00000000-0000-0000-0000-000000000003"


class FakeFTP:
    def __init__(self):
        self.directory = "/"
        self.requested = []
        self.active = {"schema": 1, "mode": "active", "updatedAt": "2026-10-21T10:00:00Z", "players": [
            {"uuid": ALICE, "activeMillis": 3600000, "afkMillis": 99999999},
            {"uuid": OTHER, "activeMillis": 999999999}
        ]}
        self.stats = {"stats": {
            "minecraft:custom": {"minecraft:play_time": 144000, "minecraft:deaths": 3, "minecraft:mob_kills": 5,
                                 "minecraft:walk_one_cm": 100000, "minecraft:sprint_one_cm": 200000,
                                 "minecraft:damage_dealt": 50, "ras:levels_gained": 12},
            "minecraft:mined": {"minecraft:stone": 100, "minecraft:diamond_ore": 3, "minecraft:deepslate_diamond_ore": 2},
            "minecraft:used": {"minecraft:totem_of_undying": 2}, "minecraft:crafted": {"minecraft:oak_planks": 8}
        }}

    def pwd(self): return self.directory
    def cwd(self, value): self.directory = value
    def nlst(self): return [ALICE + ".json", OTHER + ".json"]
    def retrbinary(self, command, callback):
        path = command[5:]
        self.requested.append(path)
        if path == "server.properties": text = "level-name=HalfKnifeSMP2026\n"
        elif path == "whitelist.json": text = json.dumps([{"uuid": ALICE, "name": "Alice"}, {"uuid": BOB, "name": "Bob"}])
        elif path.endswith("config/halfknife-active-playtime/playtime.json"):
            if self.active is None: raise ftplib.error_perm("550 missing")
            text = json.dumps(self.active)
        elif path == ALICE + ".json": text = json.dumps(self.stats)
        else: raise AssertionError("Unapproved file requested: " + path)
        callback(text.encode())


class ExportTests(unittest.TestCase):
    def test_real_units_filtering_and_full_details(self):
        ftp = FakeFTP()
        result = exporter.collect(ftp)
        alice, bob = result["players"]
        self.assertEqual([p["name"] for p in result["players"]], ["Alice", "Bob"])
        self.assertEqual(alice["summary"]["activeSeconds"], 3600)
        self.assertEqual(alice["summary"]["totalSeconds"], 7200)
        self.assertEqual(alice["summary"]["blocksMined"], 105)
        self.assertEqual(alice["summary"]["diamondsMined"], 5)
        self.assertEqual(alice["summary"]["distanceCm"], 300000)
        self.assertEqual(alice["summary"]["damageDealt"], 5)
        self.assertEqual(alice["stats"]["minecraft:custom"]["ras:levels_gained"], 12)
        self.assertFalse(bob["hasStats"])
        self.assertEqual(bob["summary"]["activeSeconds"], 0)
        self.assertNotIn(OTHER, json.dumps(result))
        self.assertEqual(ftp.directory, "/")

    def test_pending_never_substitutes_vanilla_time(self):
        ftp = FakeFTP(); ftp.active = None
        result = exporter.collect(ftp)
        self.assertEqual(result["activeMode"], "pending")
        self.assertIsNone(result["players"][0]["summary"]["activeSeconds"])
        self.assertEqual(result["players"][0]["summary"]["totalSeconds"], 7200)

    def test_corrupt_stats_abort_update(self):
        ftp = FakeFTP(); ftp.stats = {"stats": {"minecraft:custom": {"minecraft:deaths": -1}}}
        with self.assertRaises(ValueError): exporter.collect(ftp)
        self.assertEqual(ftp.directory, "/")

    def test_corrupt_active_export_aborts(self):
        ftp = FakeFTP(); ftp.active["players"][0]["activeMillis"] = True
        with self.assertRaises(ValueError): exporter.collect(ftp)


if __name__ == "__main__": unittest.main()
