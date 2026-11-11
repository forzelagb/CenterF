import sys
from core.gui_app import CenterFApp
from core.reconstruction.container import pack_file_to_container




def main():
    if len(sys.argv) > 1:
        target = sys.argv[1]
        print(f"[CenterF CLI] Анализ и упаковка файла: {target}")
        summary, blocks = pack_file_to_container(target)
        print(f"Готово! Создан контейнер: {summary.container_path}")
        print(f"Исходный размер: {summary.original_size} Б -> Сжатый: {summary.compressed_total_size} Б ({summary.compression_ratio_percent}%)")
        for b in blocks:
            print(f"  Блок #{b.index}: тип={b.block_type}, энтропия={b.entropy}, алгоритм={b.algo_name}, {b.raw_size} -> {b.compressed_size} Б")
    else:
        app = CenterFApp()
        app.mainloop()




if __name__ == "__main__":
    main()
