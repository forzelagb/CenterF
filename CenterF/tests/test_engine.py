import os
import tempfile
import unittest
from pathlib import Path

from core.compression.algorithms.rle_custom import rle_compress, rle_decompress
from core.compression.algorithms.huffman_custom import huffman_compress, huffman_decompress
from core.analyzer.statistics import analyze_block
from core.reconstruction.container import pack_file_to_container, unpack_container
from core.network.p2p_node import LocalRepository, P2PNodeServer, download_container_p2p


class TestCenterFEngine(unittest.TestCase):
    def test_custom_rle_roundtrip(self):
        samples = [
            b"",
            b"A" * 500,
            b"\x00" * 300 + b"XYZ12345" + b"\xff" * 200,
            b"Non-repeating normal text string without long runs 1234567890"
        ]
        for s in samples:
            comp = rle_compress(s)
            decomp = rle_decompress(comp)
            self.assertEqual(s, decomp)

    def test_custom_huffman_roundtrip(self):
        samples = [
            b"",
            b"X" * 100,
            b"AAAABBBCCD" * 50,
            "Привет, это проверка алгоритма Хаффмана на русском тексте!".encode("utf-8")
        ]
        for s in samples:
            comp = huffman_compress(s)
            decomp = huffman_decompress(comp)
            self.assertEqual(s, decomp)

    def test_analyzer_metrics(self):
        zeros = b"\x00" * 4096
        st_zero = analyze_block(zeros)
        self.assertEqual(st_zero.entropy, 0.0)
        self.assertEqual(st_zero.block_type, "sparse_zeros")

        txt = (b"Hello world! This is a readable text block.\n" * 100)
        st_txt = analyze_block(txt)
        self.assertEqual(st_txt.block_type, "text")
        self.assertLess(st_txt.entropy, 5.5)

    def test_container_pack_and_unpack(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            src = tmp_path / "sample.bin"
            raw_content = (b"\x00" * 20000) + (b"CenterF adaptive test line\n" * 1500) + os.urandom(15000)
            src.write_bytes(raw_content)

            cenf_file = tmp_path / "sample.bin.cenf"
            summary, blocks = pack_file_to_container(src, cenf_file, chunk_size=16384)

            self.assertTrue(cenf_file.exists())
            self.assertGreaterEqual(len(blocks), 4)

            restored = unpack_container(cenf_file, output_dir=tmp_path / "out")
            self.assertEqual(restored.read_bytes(), raw_content)

    def test_p2p_block_transfer_and_deduplication(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            sender_repo = LocalRepository(tmp_path / "sender_repo", quota_mb=50)
            receiver_repo = LocalRepository(tmp_path / "receiver_repo", quota_mb=50)

            src = tmp_path / "shared_doc.bin"
            payload = (b"REPEAT_BLOCK_DATA_" * 4000) + (b"\x00" * 32768)
            src.write_bytes(payload)

            container_path = sender_repo.containers_dir / "shared_doc.bin.cenf"
            pack_file_to_container(src, container_path, chunk_size=16384)

            server = P2PNodeServer(sender_repo, host="127.0.0.1", port=19876)
            server.start()
            try:
                out1, stats1 = download_container_p2p("127.0.0.1", 19876, "shared_doc.bin.cenf", receiver_repo)
                self.assertEqual(out1.read_bytes(), payload)
                self.assertEqual(stats1["reused_blocks"], 0)
                self.assertGreater(stats1["downloaded_blocks"], 0)

                out2, stats2 = download_container_p2p("127.0.0.1", 19876, "shared_doc.bin.cenf", receiver_repo)
                self.assertEqual(out2.read_bytes(), payload)
                self.assertEqual(stats2["downloaded_blocks"], 0)
                self.assertEqual(stats2["reused_blocks"], stats2["total_blocks"])
                self.assertEqual(stats2["network_bytes"], 0)
            finally:
                server.stop()


if __name__ == "__main__":
    unittest.main()
