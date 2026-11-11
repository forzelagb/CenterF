import json
import socket
import struct
import threading
import hashlib
from pathlib import Path
from core.reconstruction.container import (
    read_container_manifest, read_single_compressed_block
)
from core.compression.algorithms import decompress_with_algo

DEFAULT_P2P_PORT = 9876


class LocalRepository:
    def __init__(self, repo_dir: str | Path = "storage_repo", quota_mb: int = 250):
        self.repo_dir = Path(repo_dir)
        self.blocks_cache_dir = self.repo_dir / "blocks_cache"
        self.containers_dir = self.repo_dir / "containers"
        self.downloads_dir = self.repo_dir / "downloads"
        self.quota_bytes = quota_mb * 1024 * 1024

        self.blocks_cache_dir.mkdir(parents=True, exist_ok=True)
        self.containers_dir.mkdir(parents=True, exist_ok=True)
        self.downloads_dir.mkdir(parents=True, exist_ok=True)

    def get_used_bytes(self) -> int:
        total = 0
        for p in self.repo_dir.rglob("*"):
            if p.is_file():
                total += p.stat().st_size
        return total

    def get_free_bytes(self) -> int:
        return max(0, self.quota_bytes - self.get_used_bytes())

    def has_Room_for(self, size_bytes: int) -> bool:
        return (self.get_used_bytes() + size_bytes) <= self.quota_bytes

    def has_cached_block(self, sha256_hex: str) -> bool:
        return (self.blocks_cache_dir / f"{sha256_hex}.blk").exists()

    def get_cached_block_raw(self, sha256_hex: str) -> bytes:
        p = self.blocks_cache_dir / f"{sha256_hex}.blk"
        return p.read_bytes()

    def save_cached_block_raw(self, sha256_hex: str, raw_data: bytes):
        if self.has_Room_for(len(raw_data)):
            p = self.blocks_cache_dir / f"{sha256_hex}.blk"
            if not p.exists():
                p.write_bytes(raw_data)

    def list_shared_containers(self) -> list[Path]:
        return sorted(self.containers_dir.glob("*.cenf"))




def _send_msg(sock: socket.socket, data: bytes):
    sock.sendall(struct.pack(">I", len(data)) + data)




def _recv_exact(sock: socket.socket, n: int) -> bytes:
    buf = bytearray()
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise ConnectionError("Соединение закрыто удаленным узлом")
        buf.extend(chunk)
    return bytes(buf)




def _recv_msg(sock: socket.socket) -> bytes:
    raw_len = _recv_exact(sock, 4)
    msg_len = struct.unpack(">I", raw_len)[0]
    return _recv_exact(sock, msg_len)




class P2PNodeServer:
    def __init__(self, repo: LocalRepository, host: str = "0.0.0.0", port: int = DEFAULT_P2P_PORT, log_callback=None):
        self.repo = repo
        self.host = host
        self.port = port
        self.log_callback = log_callback
        self._running = False
        self._server_sock: socket.socket | None = None
        self._thread: threading.Thread | None = None

    def _log(self, text: str):
        if self.log_callback:
            self.log_callback(text)

    def start(self):
        if self._running:
            return
        self._running = True
        self._server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._server_sock.bind((self.host, self.port))
        self._server_sock.listen(5)
        self._thread = threading.Thread(target=self._accept_loop, daemon=True)
        self._thread.start()
        self._log(f"[P2P Узел] Сервер раздачи запущен на порту {self.port}")

    def stop(self):
        self._running = False
        if self._server_sock:
            try:
                self._server_sock.close()
            except Exception:
                pass
        self._log("[P2P Узел] Сервер раздачи остановлен")

    def _accept_loop(self):
        while self._running:
            try:
                client_sock, addr = self._server_sock.accept()
                t = threading.Thread(target=self._handle_client, args=(client_sock, addr), daemon=True)
                t.start()
            except Exception:
                if self._running:
                    continue
                break

    def _handle_client(self, sock: socket.socket, addr):
        try:
            with sock:
                while self._running:
                    req_bytes = _recv_msg(sock)
                    req_str = req_bytes.decode("utf-8")

                    if req_str == "LIST":
                        files = [p.name for p in self.repo.list_shared_containers()]
                        _send_msg(sock, json.dumps({"status": "ok", "files": files}).encode("utf-8"))

                    elif req_str.startswith("MANIFEST:"):
                        fname = req_str.split(":", 1)[1]
                        target = self.repo.containers_dir / fname
                        if not target.exists():
                            _send_msg(sock, json.dumps({"status": "error", "msg": "Контейнер не найден"}).encode("utf-8"))
                        else:
                            manifest, _ = read_container_manifest(target)
                            self._log(f"[P2P Раздача] Клиент {addr[0]} запросил манифест {fname}")
                            _send_msg(sock, json.dumps({"status": "ok", "manifest": manifest}).encode("utf-8"))

                    elif req_str.startswith("BLOCK:"):
                        _, fname, idx_str = req_str.split(":", 2)
                        b_idx = int(idx_str)
                        target = self.repo.containers_dir / fname
                        _, payload = read_single_compressed_block(target, b_idx)
                        _send_msg(sock, payload)

                    elif req_str == "QUIT":
                        break
        except Exception:
            pass




def fetch_remote_file_list(host: str, port: int = DEFAULT_P2P_PORT) -> list[str]:
    with socket.create_connection((host, port), timeout=5.0) as sock:
        _send_msg(sock, b"LIST")
        resp = json.loads(_recv_msg(sock).decode("utf-8"))
        _send_msg(sock, b"QUIT")
        if resp.get("status") == "ok":
            return resp.get("files", [])
        raise RuntimeError(resp.get("msg", "Ошибка получения списка файлов"))




def download_container_p2p(
    host: str,
    port: int,
    container_filename: str,
    local_repo: LocalRepository,
    progress_callback=None,
    log_callback=None
) -> tuple[Path, dict]:
    def _log(msg: str):
        if log_callback:
            log_callback(msg)

    with socket.create_connection((host, port), timeout=10.0) as sock:
        _send_msg(sock, f"MANIFEST:{container_filename}".encode("utf-8"))
        resp = json.loads(_recv_msg(sock).decode("utf-8"))
        if resp.get("status") != "ok":
            raise RuntimeError(resp.get("msg", "Не удалось получить манифест"))

        manifest = resp["manifest"]
        orig_name = manifest["original_name"]
        orig_size = manifest["original_size"]
        blocks = manifest["blocks"]
        total_blocks = len(blocks)

        if not local_repo.has_Room_for(orig_size):
            raise RuntimeError(
                f"Превышена квота локального репозитория! "
                f"Нужно {orig_size // 1024} КБ, свободно {local_repo.get_free_bytes() // 1024} КБ."
            )

        out_path = local_repo.downloads_dir / orig_name
        reused_blocks = 0
        downloaded_blocks = 0
        network_bytes_transferred = 0
        full_hasher = hashlib.sha256()

        _log(f"[P2P Прием] Начат прием '{orig_name}' ({total_blocks} независимых блоков)")

        with open(out_path, "wb") as out_f:
            for idx, b_meta in enumerate(blocks):
                b_sha = b_meta["sha256"]
                algo_id = b_meta["algo_id"]
                algo_name = b_meta["algo_name"]

                if local_repo.has_cached_block(b_sha):
                    raw_data = local_repo.get_cached_block_raw(b_sha)
                    reused_blocks += 1
                    _log(f"  Блок #{idx}: взят из локального кэша (SHA256 {b_sha[:8]}..., 0 байт по сети)")
                else:
                    _send_msg(sock, f"BLOCK:{container_filename}:{idx}".encode("utf-8"))
                    comp_payload = _recv_msg(sock)
                    network_bytes_transferred += len(comp_payload)
                    downloaded_blocks += 1

                    raw_data = decompress_with_algo(comp_payload, algo_id)

                    actual_sha = hashlib.sha256(raw_data).hexdigest()
                    if actual_sha != b_sha:
                        raise ValueError(f"Сбой контрольной суммы P2P блока #{idx}!")

                    local_repo.save_cached_block_raw(b_sha, raw_data)
                    _log(
                        f"  Блок #{idx}: скачан по сети ({len(comp_payload)} Б -> {len(raw_data)} Б, {algo_name})"
                    )

                out_f.write(raw_data)
                full_hasher.update(raw_data)

                if progress_callback:
                    progress_callback(idx + 1, total_blocks)

        _send_msg(sock, b"QUIT")

        if full_hasher.hexdigest() != manifest["file_sha256"]:
            raise ValueError("Ошибка общей контрольной суммы файла после P2P сборки!")

        stats = {
            "total_blocks": total_blocks,
            "downloaded_blocks": downloaded_blocks,
            "reused_blocks": reused_blocks,
            "network_bytes": network_bytes_transferred,
            "original_size": orig_size
        }
        _log(
            f"[P2P Готово] Файл собран: {out_path.name}. "
            f"Скачано блоков: {downloaded_blocks}, взято из кэша: {reused_blocks}, "
            f"передано по сети: {network_bytes_transferred} байт (вместо {orig_size} байт)."
        )
        return out_path, stats
