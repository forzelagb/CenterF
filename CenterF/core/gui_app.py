import os
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from core.chunking.chunker import DEFAULT_CHUNK_SIZE
from core.compression.algorithms import (
    ALGO_STORE, ALGO_RLE, ALGO_HUFFMAN, ALGO_ZLIB, ALGO_BZ2, ALGO_LZMA
)
from core.reconstruction.container import (
    pack_file_to_container, unpack_container, read_container_manifest
)
from core.network.p2p_node import (
    LocalRepository, P2PNodeServer, fetch_remote_file_list, download_container_p2p, DEFAULT_P2P_PORT
)




def fmt_size(num_bytes: int) -> str:
    if num_bytes < 1024:
        return f"{num_bytes} Б"
    elif num_bytes < 1024 * 1024:
        return f"{num_bytes / 1024:.1f} КБ"
    else:
        return f"{num_bytes / (1024 * 1024):.2f} МБ"




class CenterFApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("CenterF — Интеллектуальная система адаптивного блочного сжатия и P2P-передачи данных")
        self.geometry("1020x680")
        self.minsize(920, 620)

        self.repo = LocalRepository(repo_dir="storage_repo", quota_mb=250)
        self.p2p_server = P2PNodeServer(self.repo, port=DEFAULT_P2P_PORT, log_callback=self.log_p2p_safe)

        self._setup_styles()
        self._build_ui()

        try:
            self.p2p_server.start()
            self.lbl_server_status.config(text=f"Статус P2P-узла: Активен (порт {DEFAULT_P2P_PORT})", foreground="green")
        except Exception as e:
            self.lbl_server_status.config(text=f"Статус P2P-узла: Порт занят ({e})", foreground="red")

        self.refresh_repo_status()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _setup_styles(self):
        style = ttk.Style(self)
        try:
            style.theme_use("vista")
        except Exception:
            pass
        style.configure("Title.TLabel", font=("Segoe UI", 13, "bold"))
        style.configure("Sub.TLabel", font=("Segoe UI", 9))
        style.configure("Stat.TLabel", font=("Segoe UI", 10, "bold"))
        style.configure("Treeview.Heading", font=("Segoe UI", 9, "bold"))

    def _build_ui(self):
        header = ttk.Frame(self, padding=(12, 8))
        header.pack(fill="x")

        ttk.Label(
            header,
            text="CenterF Engine — Адаптивное блочное сжатие и P2P-хранилище",
            style="Title.TLabel"
        ).pack(side="left")

        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        self.tab_compress = ttk.Frame(self.notebook, padding=10)
        self.tab_inspect = ttk.Frame(self.notebook, padding=10)
        self.tab_p2p = ttk.Frame(self.notebook, padding=10)

        self.notebook.add(self.tab_compress, text=" 1. Адаптивное сжатие (Data Analyzer & Engine) ")
        self.notebook.add(self.tab_inspect, text=" 2. Контейнер файла (Инспектор и Распаковка) ")
        self.notebook.add(self.tab_p2p, text=" 3. P2P-Репозиторий и Прямая передача блоков ")

        self._build_tab_compress()
        self._build_tab_inspect()
        self._build_tab_p2p()


    def _build_tab_compress(self):
        top_box = ttk.LabelFrame(self.tab_compress, text="Выбор файла и параметров разбиения", padding=10)
        top_box.pack(fill="x", pady=(0, 8))

        row1 = ttk.Frame(top_box)
        row1.pack(fill="x", pady=2)
        ttk.Label(row1, text="Исходный файл:").pack(side="left")
        self.ent_input_file = ttk.Entry(row1)
        self.ent_input_file.pack(side="left", fill="x", expand=True, padx=8)
        ttk.Button(row1, text="Обзор...", command=self.browse_input_file).pack(side="left")

        row2 = ttk.Frame(top_box)
        row2.pack(fill="x", pady=(8, 2))

        ttk.Label(row2, text="Размер независимого блока:").pack(side="left")
        self.cmb_chunk_size = ttk.Combobox(
            row2,
            values=["16 КБ (16384 Б)", "32 КБ (32768 Б)", "64 КБ (65536 Б) - Рекомендуется", "128 КБ (131072 Б)"],
            state="readonly",
            width=30
        )
        self.cmb_chunk_size.current(2)
        self.cmb_chunk_size.pack(side="left", padx=(6, 20))

        ttk.Label(row2, text="Режим селектора:").pack(side="left")
        self.cmb_mode = ttk.Combobox(
            row2,
            values=[
                "АВТО (Интеллектуальный выбор под каждый блок)",
                "Принудительно: RLE (Свой алгоритм)",
                "Принудительно: Huffman (Свой алгоритм)",
                "Принудительно: ZLIB (Deflate)",
                "Принудительно: BZIP2 (BWT)",
                "Принудительно: LZMA (7z)",
                "Принудительно: STORE (Без сжатия)"
            ],
            state="readonly",
            width=42
        )
        self.cmb_mode.current(0)
        self.cmb_mode.pack(side="left", padx=6)

        self.var_save_to_repo = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            top_box,
            text="Сразу поместить готовый .cenf контейнер в мой P2P-репозиторий для раздачи",
            variable=self.var_save_to_repo
        ).pack(anchor="w", pady=(6, 0))

        act_frame = ttk.Frame(self.tab_compress)
        act_frame.pack(fill="x", pady=4)

        self.btn_run_compress = ttk.Button(
            act_frame,
            text="🚀 Запустить анализ блоков и упаковать в CenterF (.cenf)",
            command=self.start_compression
        )
        self.btn_run_compress.pack(side="left")

        self.prog_compress = ttk.Progressbar(act_frame, mode="determinate")
        self.prog_compress.pack(side="left", fill="x", expand=True, padx=12)

        self.lbl_compress_summary = ttk.Label(
            self.tab_compress,
            text="Выберите файл на диске через кнопку «Обзор...» и запустите сжатие.",
            style="Stat.TLabel"
        )
        self.lbl_compress_summary.pack(anchor="w", pady=6)

        tbl_frame = ttk.LabelFrame(
            self.tab_compress,
            text="Карта независимых блоков файла (результат работы Data Analyzer и Adaptive Selector)",
            padding=6
        )
        tbl_frame.pack(fill="both", expand=True)

        cols = ("idx", "btype", "entropy", "algo", "raw", "comp", "ratio", "sha", "reason")
        self.tree_blocks = ttk.Treeview(tbl_frame, columns=cols, show="headings", height=12)
        self.tree_blocks.heading("idx", text="Блок #")
        self.tree_blocks.heading("btype", text="Тип данных")
        self.tree_blocks.heading("entropy", text="Энтропия")
        self.tree_blocks.heading("algo", text="Выбранный алгоритм")
        self.tree_blocks.heading("raw", text="До сжатия")
        self.tree_blocks.heading("comp", text="После сжатия")
        self.tree_blocks.heading("ratio", text="Экономия")
        self.tree_blocks.heading("sha", text="SHA-256 блока")
        self.tree_blocks.heading("reason", text="Обоснование селектора")

        self.tree_blocks.column("idx", width=55, anchor="center")
        self.tree_blocks.column("btype", width=95, anchor="center")
        self.tree_blocks.column("entropy", width=75, anchor="center")
        self.tree_blocks.column("algo", width=155, anchor="w")
        self.tree_blocks.column("raw", width=85, anchor="e")
        self.tree_blocks.column("comp", width=95, anchor="e")
        self.tree_blocks.column("ratio", width=75, anchor="center")
        self.tree_blocks.column("sha", width=95, anchor="center")
        self.tree_blocks.column("reason", width=240, anchor="w")

        vsb = ttk.Scrollbar(tbl_frame, orient="vertical", command=self.tree_blocks.yview)
        self.tree_blocks.configure(yscrollcommand=vsb.set)
        self.tree_blocks.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")


    def _build_tab_inspect(self):
        top = ttk.LabelFrame(self.tab_inspect, text="Работа с контейнером CenterF (.cenf)", padding=10)
        top.pack(fill="x", pady=(0, 8))

        r = ttk.Frame(top)
        r.pack(fill="x")
        ttk.Label(r, text="Файл контейнера (.cenf):").pack(side="left")
        self.ent_container_file = ttk.Entry(r)
        self.ent_container_file.pack(side="left", fill="x", expand=True, padx=8)
        ttk.Button(r, text="Выбрать .cenf...", command=self.browse_container_file).pack(side="left", padx=(0, 6))
        ttk.Button(r, text="🔍 Прочитать паспорт", command=self.inspect_selected_container).pack(side="left", padx=(0, 6))
        ttk.Button(r, text="📦 Распаковать и проверить SHA-256", command=self.unpack_selected_container).pack(side="left")

        self.lbl_manifest_info = ttk.Label(
            self.tab_inspect,
            text="Откройте любой .cenf файл, чтобы увидеть его внутреннюю структуру и проверить целостность блоков.",
            style="Stat.TLabel"
        )
        self.lbl_manifest_info.pack(anchor="w", pady=6)

        mid = ttk.LabelFrame(self.tab_inspect, text="Содержимое паспорта контейнера и таблица блоков", padding=6)
        mid.pack(fill="both", expand=True)

        self.txt_manifest = tk.Text(mid, font=("Consolas", 10), wrap="none", height=18)
        vsb2 = ttk.Scrollbar(mid, orient="vertical", command=self.txt_manifest.yview)
        self.txt_manifest.configure(yscrollcommand=vsb2.set)
        self.txt_manifest.pack(side="left", fill="both", expand=True)
        vsb2.pack(side="right", fill="y")


    def _build_tab_p2p(self):
        repo_frame = ttk.LabelFrame(
            self.tab_p2p,
            text="Локальный выделенный репозиторий пользователя (хранение блоков без промежуточного облака)",
            padding=10
        )
        repo_frame.pack(fill="x", pady=(0, 8))

        r_info = ttk.Frame(repo_frame)
        r_info.pack(fill="x")

        self.lbl_repo_quota = ttk.Label(r_info, text="Занято места: ...", style="Stat.TLabel")
        self.lbl_repo_quota.pack(side="left")

        self.lbl_server_status = ttk.Label(r_info, text="Статус P2P-узла: ...", style="Stat.TLabel")
        self.lbl_server_status.pack(side="right")

        self.prog_quota = ttk.Progressbar(repo_frame, mode="determinate", maximum=100)
        self.prog_quota.pack(fill="x", pady=6)

        r_btns = ttk.Frame(repo_frame)
        r_btns.pack(fill="x")
        ttk.Button(r_btns, text="🔄 Обновить статус репозитория", command=self.refresh_repo_status).pack(side="left", padx=(0, 8))
        ttk.Button(r_btns, text="🗑 Очистить локальный кэш блоков", command=self.clear_block_cache).pack(side="left", padx=(0, 8))
        ttk.Button(r_btns, text="📂 Открыть папку репозитория в Проводнике", command=self.open_repo_folder).pack(side="left")

        p2p_box = ttk.LabelFrame(
            self.tab_p2p,
            text="Прямое P2P-скачивание с узла отправителя (по независимым блокам с проверкой дедупликации)",
            padding=10
        )
        p2p_box.pack(fill="x", pady=(0, 8))

        conn_row = ttk.Frame(p2p_box)
        conn_row.pack(fill="x", pady=2)

        ttk.Label(conn_row, text="IP отправителя:").pack(side="left")
        self.ent_peer_ip = ttk.Entry(conn_row, width=16)
        self.ent_peer_ip.insert(0, "127.0.0.1")
        self.ent_peer_ip.pack(side="left", padx=(6, 14))

        ttk.Label(conn_row, text="Порт:").pack(side="left")
        self.ent_peer_port = ttk.Entry(conn_row, width=8)
        self.ent_peer_port.insert(0, str(DEFAULT_P2P_PORT))
        self.ent_peer_port.pack(side="left", padx=(6, 14))

        ttk.Button(conn_row, text="📡 Запросить список файлов у пира", command=self.query_peer_files).pack(side="left", padx=(0, 14))

        ttk.Label(conn_row, text="Доступные контейнеры:").pack(side="left")
        self.cmb_remote_files = ttk.Combobox(conn_row, state="readonly", width=28)
        self.cmb_remote_files.pack(side="left", padx=6)

        dl_row = ttk.Frame(p2p_box)
        dl_row.pack(fill="x", pady=(8, 2))
        self.btn_p2p_download = ttk.Button(
            dl_row,
            text="⬇ Скачать выбранный контейнер по блокам и собрать файл",
            command=self.start_p2p_download
        )
        self.btn_p2p_download.pack(side="left")

        self.prog_p2p = ttk.Progressbar(dl_row, mode="determinate")
        self.prog_p2p.pack(side="left", fill="x", expand=True, padx=12)

        log_frame = ttk.LabelFrame(self.tab_p2p, text="Журнал работы P2P-узла и поблочной передачи данных", padding=6)
        log_frame.pack(fill="both", expand=True)

        self.txt_p2p_log = tk.Text(log_frame, font=("Consolas", 9), height=12)
        vsb3 = ttk.Scrollbar(log_frame, orient="vertical", command=self.txt_p2p_log.yview)
        self.txt_p2p_log.configure(yscrollcommand=vsb3.set)
        self.txt_p2p_log.pack(side="left", fill="both", expand=True)
        vsb3.pack(side="right", fill="y")


    def browse_input_file(self):
        path = filedialog.askopenfilename(title="Выберите файл для адаптивного сжатия")
        if path:
            self.ent_input_file.delete(0, tk.END)
            self.ent_input_file.insert(0, path)

    def _get_selected_chunk_size(self) -> int:
        idx = self.cmb_chunk_size.current()
        sizes = [16384, 32768, 65536, 131072]
        return sizes[idx] if 0 <= idx < len(sizes) else DEFAULT_CHUNK_SIZE

    def _get_selected_force_algo(self) -> int | None:
        idx = self.cmb_mode.current()
        mapping = {
            0: None,
            1: ALGO_RLE,
            2: ALGO_HUFFMAN,
            3: ALGO_ZLIB,
            4: ALGO_BZ2,
            5: ALGO_LZMA,
            6: ALGO_STORE
        }
        return mapping.get(idx, None)

    def start_compression(self):
        in_path = self.ent_input_file.get().strip()
        if not in_path or not os.path.isfile(in_path):
            messagebox.showwarning("Внимание", "Сначала выберите существующий файл через кнопку «Обзор...»!")
            return

        chunk_size = self._get_selected_chunk_size()
        force_algo = self._get_selected_force_algo()
        save_to_repo = self.var_save_to_repo.get()

        if save_to_repo:
            out_path = str(self.repo.containers_dir / (os.path.basename(in_path) + ".cenf"))
        else:
            out_path = in_path + ".cenf"

        for item in self.tree_blocks.get_children():
            self.tree_blocks.delete(item)

        self.btn_run_compress.config(state="disabled")
        self.prog_compress["value"] = 0
        self.lbl_compress_summary.config(text="Выполняется поблочный анализ энтропии и подбор алгоритмов...")

        def worker():
            try:
                def on_prog(curr, total, pb):
                    pct = (curr / total) * 100
                    self.after(0, lambda c=curr, t=total, p=pct, block=pb: self._on_block_packed(c, t, p, block))

                summary, blocks = pack_file_to_container(
                    input_path=in_path,
                    output_path=out_path,
                    chunk_size=chunk_size,
                    force_algo=force_algo,
                    progress_callback=on_prog
                )
                self.after(0, lambda: self._on_compression_done(summary))
            except Exception as e:
                self.after(0, lambda err=str(e): messagebox.showerror("Ошибка сжатия", err))
                self.after(0, lambda: self.btn_run_compress.config(state="normal"))

        threading.Thread(target=worker, daemon=True).start()

    def _on_block_packed(self, curr, total, pct, pb):
        self.prog_compress["value"] = pct
        ratio = 0.0
        if pb.raw_size > 0:
            ratio = round((1.0 - pb.compressed_size / pb.raw_size) * 100, 1)
        ratio_str = f"-{ratio}%" if ratio >= 0 else f"+{abs(ratio)}%"

        self.tree_blocks.insert(
            "",
            "end",
            values=(
                f"#{pb.index}",
                pb.block_type,
                f"{pb.entropy:.2f}",
                pb.algo_name,
                fmt_size(pb.raw_size),
                fmt_size(pb.compressed_size),
                ratio_str,
                pb.sha256[:10] + "...",
                pb.reason
            )
        )

    def _on_compression_done(self, summary):
        self.btn_run_compress.config(state="normal")
        self.lbl_compress_summary.config(
            text=(
                f"✅ Готово! Исходный размер: {fmt_size(summary.original_size)}  ➔  "
                f"Контейнер CenterF: {fmt_size(summary.compressed_total_size)} "
                f"(Сжатие: {summary.compression_ratio_percent}%, блоков: {summary.total_blocks}). "
                f"Файл: {summary.container_path.name}"
            )
        )

        self.ent_container_file.delete(0, tk.END)
        self.ent_container_file.insert(0, str(summary.container_path))
        self.inspect_selected_container()
        self.refresh_repo_status()
        self.query_peer_files(silent=True)


    def browse_container_file(self):
        path = filedialog.askopenfilename(
            title="Выберите контейнер CenterF (.cenf)",
            filetypes=[("CenterF Container", "*.cenf"), ("Все файлы", "*.*")]
        )
        if path:
            self.ent_container_file.delete(0, tk.END)
            self.ent_container_file.insert(0, path)
            self.inspect_selected_container()

    def inspect_selected_container(self):
        c_path = self.ent_container_file.get().strip()
        if not c_path or not os.path.isfile(c_path):
            return
        try:
            manifest, data_offset = read_container_manifest(c_path)
            total_file_sz = os.path.getsize(c_path)
            orig_sz = manifest["original_size"]
            saved_pct = round((1 - total_file_sz / orig_sz) * 100, 2) if orig_sz else 0.0

            self.lbl_manifest_info.config(
                text=(
                    f"Контейнер: {os.path.basename(c_path)} | Исходный файл: {manifest['original_name']} ({fmt_size(orig_sz)}) | "
                    f"Блоков: {manifest['total_blocks']} | Экономия: {saved_pct}%"
                )
            )

            lines = [
                "=== ПАСПОРТ КОНТЕЙНЕРА CENTERF (ФОРМАТ CENF v1) ===",
                f"Исходное имя файла : {manifest['original_name']}",
                f"Исходный размер    : {manifest['original_size']} байт ({fmt_size(manifest['original_size'])})",
                f"Размер контейнера  : {total_file_sz} байт ({fmt_size(total_file_sz)})",
                f"Размер заголовка   : {data_offset} байт",
                f"Базовый размер бл. : {manifest['chunk_size']} байт",
                f"Количество блоков  : {manifest['total_blocks']}",
                f"SHA-256 всего файла: {manifest['file_sha256']}",
                "",
                "=== ТАБЛИЦА НЕЗАВИСИМЫХ БЛОКОВ ===",
                f"{'№':<4} | {'Алгоритм':<24} | {'Тип':<12} | {'Энтр.':<6} | {'До (Б)':<8} | {'После (Б)':<9} | {'Смещение':<9} | {'SHA-256 блока'}",
                "-" * 105
            ]
            for b in manifest["blocks"]:
                lines.append(
                    f"{b['index']:<4} | {b['algo_name']:<24} | {b['block_type']:<12} | "
                    f"{b['entropy']:<6.2f} | {b['raw_size']:<8} | {b['compressed_size']:<9} | "
                    f"{b['offset']:<9} | {b['sha256'][:16]}..."
                )

            self.txt_manifest.delete("1.0", tk.END)
            self.txt_manifest.insert(tk.END, "\n".join(lines))
        except Exception as e:
            messagebox.showerror("Ошибка чтения контейнера", str(e))

    def unpack_selected_container(self):
        c_path = self.ent_container_file.get().strip()
        if not c_path or not os.path.isfile(c_path):
            messagebox.showwarning("Внимание", "Сначала выберите файл контейнера .cenf!")
            return

        out_dir = filedialog.askdirectory(title="Выберите папку для сохранения распакованного файла")
        if not out_dir:
            return

        try:
            restored_path = unpack_container(c_path, output_dir=out_dir)
            messagebox.showinfo(
                "Успешная распаковка и проверка",
                f"Все блоки успешно распакованы!\n"
                f"Контрольные суммы SHA-256 каждого блока и итогового файла полностью совпали.\n\n"
                f"Восстановленный файл:\n{restored_path}"
            )
        except Exception as e:
            messagebox.showerror("Ошибка при распаковке", str(e))


    def log_p2p_safe(self, msg: str):
        self.after(0, lambda m=msg: self._append_p2p_log(m))

    def _append_p2p_log(self, msg: str):
        self.txt_p2p_log.insert(tk.END, msg + "\n")
        self.txt_p2p_log.see(tk.END)

    def refresh_repo_status(self):
        used = self.repo.get_used_bytes()
        quota = self.repo.quota_bytes
        pct = min(100.0, (used / quota) * 100) if quota else 0.0
        cached_count = len(list(self.repo.blocks_cache_dir.glob("*.blk")))
        shared_count = len(self.repo.list_shared_containers())

        self.lbl_repo_quota.config(
            text=(
                f"Репозиторий: занято {fmt_size(used)} из {fmt_size(quota)} ({pct:.1f}%)  |  "
                f"Контейнеров на раздаче: {shared_count}  |  Блоков в кэше дедупликации: {cached_count}"
            )
        )
        self.prog_quota["value"] = pct

    def clear_block_cache(self):
        removed = 0
        for p in self.repo.blocks_cache_dir.glob("*.blk"):
            try:
                p.unlink()
                removed += 1
            except Exception:
                pass
        self.refresh_repo_status()
        self._append_p2p_log(f"[Репозиторий] Очищен кэш дедупликации: удалено {removed} блоков.")

    def open_repo_folder(self):
        path = os.path.abspath(self.repo.repo_dir)
        try:
            os.startfile(path)
        except Exception as e:
            messagebox.showinfo("Папка репозитория", f"Путь к репозиторию:\n{path}\n({e})")

    def query_peer_files(self, silent: bool = False):
        host = self.ent_peer_ip.get().strip()
        try:
            port = int(self.ent_peer_port.get().strip())
            files = fetch_remote_file_list(host, port)
            self.cmb_remote_files["values"] = files
            if files:
                self.cmb_remote_files.current(0)
            if not silent:
                self._append_p2p_log(f"[P2P Поиск] У пира {host}:{port} найдено контейнеров: {len(files)}")
        except Exception as e:
            if not silent:
                messagebox.showerror("Ошибка подключения к пиру", f"Не удалось подключиться к {host}:{port}\n{e}")

    def start_p2p_download(self):
        host = self.ent_peer_ip.get().strip()
        try:
            port = int(self.ent_peer_port.get().strip())
        except ValueError:
            messagebox.showwarning("Ошибка", "Некорректный порт")
            return

        fname = self.cmb_remote_files.get().strip()
        if not fname:
            messagebox.showwarning(
                "Нет выбранного контейнера",
                "Сначала нажмите «Запросить список файлов у пира» и выберите контейнер .cenf!"
            )
            return

        self.btn_p2p_download.config(state="disabled")
        self.prog_p2p["value"] = 0

        def worker():
            try:
                def on_prog(c, t):
                    self.after(0, lambda curr=c, tot=t: self.prog_p2p.configure(value=(curr / tot) * 100))

                out_path, stats = download_container_p2p(
                    host=host,
                    port=port,
                    container_filename=fname,
                    local_repo=self.repo,
                    progress_callback=on_prog,
                    log_callback=self.log_p2p_safe
                )
                self.after(0, lambda: self._on_p2p_done(out_path, stats))
            except Exception as e:
                self.after(0, lambda err=str(e): messagebox.showerror("Ошибка P2P передачи", err))
                self.after(0, lambda: self.btn_p2p_download.config(state="normal"))

        threading.Thread(target=worker, daemon=True).start()

    def _on_p2p_done(self, out_path, stats):
        self.btn_p2p_download.config(state="normal")
        self.refresh_repo_status()
        messagebox.showinfo(
            "P2P-передача завершена",
            f"Файл успешно получен напрямую с узла отправителя и проверен по SHA-256!\n\n"
            f"Сохранен в: {out_path}\n"
            f"Всего блоков: {stats['total_blocks']}\n"
            f"Скачано по сети: {stats['downloaded_blocks']} бл. ({fmt_size(stats['network_bytes'])})\n"
            f"Взято из локального кэша (без сети): {stats['reused_blocks']} бл."
        )

    def _on_close(self):
        self.p2p_server.stop()
        self.destroy()
