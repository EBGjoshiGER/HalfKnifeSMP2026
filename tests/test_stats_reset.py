import ftplib
import importlib.util
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
spec = importlib.util.spec_from_file_location("request_stats_reset", Path(__file__).parents[1] / "scripts/request_stats_reset.py")
reset = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reset)
ALICE = "00000000-0000-0000-0000-000000000001"


class FTP:
    def __init__(self):
        self.files = {
            "server.properties": b"level-name=world\n",
            "whitelist.json": json.dumps([{"uuid": ALICE, "name": "Alice"}]).encode(),
            "world/config/halfknife-active-playtime/playtime.json": b'{"resetProtocol":1}',
        }
        self.acknowledge = True
        self.success = True

    def retrbinary(self, command, callback):
        name = command[5:]
        if name not in self.files:
            raise ftplib.error_perm("550 not found")
        callback(self.files[name])

    def storbinary(self, command, stream):
        self.files[command[5:]] = stream.read()

    def rename(self, source, target):
        self.files[target] = self.files.pop(source)
        if self.acknowledge:
            request = json.loads(self.files.pop(target))
            self.files[target.replace("request", "result")] = json.dumps({
                "id": request["id"], "success": self.success, "message": "test receipt"
            }).encode()

    def delete(self, name):
        self.files.pop(name)


class ResetTests(unittest.TestCase):
    def test_resolves_name_to_uuid_before_upload_and_requires_receipt(self):
        ftp = FTP()
        folder, request = reset.prepare_request(ftp, "ALICE", "all")
        self.assertEqual(request["target"], ALICE)
        self.assertEqual(reset.send_request(ftp, folder, request)["success"], True)
        self.assertNotIn(folder + "/reset-request.json", ftp.files)

    def test_old_mod_cannot_receive_request(self):
        ftp = FTP()
        ftp.files["world/config/halfknife-active-playtime/playtime.json"] = b'{}'
        with self.assertRaisesRegex(RuntimeError, "restart"):
            reset.prepare_request(ftp, "Alice", "active")

    def test_invalid_or_unknown_target_cannot_be_uploaded(self):
        for target in ["Unknown", "Alice\nALL", "../Alice"]:
            with self.subTest(target=target), self.assertRaises(ValueError):
                reset.prepare_request(FTP(), target, "all")

    def test_existing_request_is_preserved(self):
        ftp = FTP()
        folder, request = reset.prepare_request(ftp, "Alice", "active")
        pending = folder + "/reset-request.json"
        ftp.files[pending] = b'{"id":"original"}'
        with self.assertRaisesRegex(RuntimeError, "already pending"):
            reset.send_request(ftp, folder, request)
        self.assertEqual(ftp.files[pending], b'{"id":"original"}')

    def test_timeout_cancels_only_own_request(self):
        ftp = FTP(); ftp.acknowledge = False
        folder, request = reset.prepare_request(ftp, "Alice", "active")
        with self.assertRaises(TimeoutError):
            reset.send_request(ftp, folder, request, timeout=0)
        self.assertNotIn(folder + "/reset-request.json", ftp.files)

    def test_server_failure_is_not_reported_as_success(self):
        ftp = FTP(); ftp.success = False
        folder, request = reset.prepare_request(ftp, "Alice", "all")
        with self.assertRaisesRegex(RuntimeError, "rejected"):
            reset.send_request(ftp, folder, request)

    def test_world_traversal_is_rejected(self):
        ftp = FTP(); ftp.files["server.properties"] = b"level-name=../outside\n"
        with self.assertRaisesRegex(ValueError, "world path"):
            reset.prepare_request(ftp, "Alice", "active")


if __name__ == "__main__":
    unittest.main()
