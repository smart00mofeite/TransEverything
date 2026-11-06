#!/usr/bin/env python3
"""
TransEverything - 图形界面入口

直接运行：python app.py [文件...]
打包后：双击 TransEverything.exe（把文件拖到 exe 图标上也能直接带入列表）
"""

import logging
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from PySide6.QtGui import QIcon  # noqa: E402
from PySide6.QtWidgets import QApplication, QMessageBox  # noqa: E402

APP_NAME = "TransEverything"
VERSION = "1.0.0"


def _install_excepthook() -> None:
    def hook(exc_type, exc, tb) -> None:  # noqa: ANN001
        logging.getLogger("trans_everything").error(
            "未捕获异常", exc_info=(exc_type, exc, tb)
        )
        try:
            QMessageBox.critical(
                None,
                "出错了",
                f"程序遇到未处理的错误，已记录日志：\n\n{exc_type.__name__}: {exc}",
            )
        except Exception:
            pass

    sys.excepthook = hook


def _attach_console() -> None:
    """打包成 GUI 程序后没有控制台；从命令行启动时尝试附着父进程控制台以便打印。"""
    if sys.platform != "win32":
        return
    try:
        import ctypes

        ctypes.windll.kernel32.AttachConsole(-1)
        if sys.stdout is None or sys.stdout.fileno() < 0:
            sys.stdout = open("CONOUT$", "w", encoding="utf-8", buffering=1)  # noqa: SIM115
    except Exception:
        pass


def _diagnose(preferred_dir: str = "") -> int:
    """输出运行环境与依赖自检结果，打包后在客户机上排查问题用。"""
    import importlib
    import platform

    _attach_console()

    from core.utils import (
        BASE_DIR,
        find_pdf_font,
        is_dir_writable,
        resource_path,
        user_data_dir,
        user_log_dir,
    )

    lines: list[str] = []
    lines.append(f"{APP_NAME} {VERSION}")
    lines.append(f"python {sys.version.split()[0]} / {platform.architecture()[0]}")
    lines.append(f"frozen = {bool(getattr(sys, 'frozen', False))}")
    lines.append(f"base dir = {BASE_DIR}")
    lines.append(f"fonts dir = {resource_path('fonts')} (exists={resource_path('fonts').is_dir()})")
    lines.append(f"icon = {resource_path('assets', 'app.ico')} "
                 f"(exists={resource_path('assets', 'app.ico').is_file()})")

    regular, cjk = find_pdf_font(False)
    bold, _ = find_pdf_font(True)
    lines.append(f"pdf font = {regular} (cjk={cjk})")
    lines.append(f"pdf bold = {bold}")

    for module in (
        "pdfplumber",
        "fpdf",
        "docx",
        "openpyxl",
        "python_calamine",
        "PIL",
        "resvg_py",
        "pypdfium2",
        "PySide6",
    ):
        try:
            importlib.import_module(module)
            lines.append(f"ok      {module}")
        except Exception as exc:  # noqa: BLE001
            lines.append(f"MISSING {module}: {type(exc).__name__}: {exc}")

    # 20 条转换链路都是动态导入，这里逐个验证模块真实存在
    try:
        import convert

        failed = []
        for key, module_name in sorted(convert.CONVERSION_MAP.items()):
            try:
                importlib.import_module(module_name)
            except Exception as exc:  # noqa: BLE001
                failed.append(f"{key} ({module_name}): {type(exc).__name__}: {exc}")
        if failed:
            lines.append(f"转换模块缺失 {len(failed)} 个：")
            lines.extend(f"  FAIL {item}" for item in failed)
        else:
            lines.append(f"ok      全部 {len(convert.CONVERSION_MAP)} 个转换模块可导入")
    except Exception as exc:  # noqa: BLE001
        lines.append(f"FAIL    无法加载 convert 模块表：{exc}")

    # 端到端冒烟：真实跑一遍转换，确认打包后功能可用
    import shutil
    import tempfile

    work = None
    if preferred_dir:
        try:
            candidate = Path(preferred_dir)
            probe = candidate / ".te_probe"
            probe.write_text("x", encoding="utf-8")
            probe.unlink()
            work = candidate
        except OSError:
            work = None

    candidates = [Path(tempfile.gettempdir()), user_data_dir()]
    try:
        candidates.append(Path.cwd())
    except OSError:
        pass
    if work is None:
        for base in candidates:
            created = None
            try:
                created = Path(tempfile.mkdtemp(prefix="te_diag_", dir=str(base)))
                probe = created / ".probe"
                probe.write_text("x", encoding="utf-8")
                probe.unlink()
                work = created
                break
            except OSError:
                if created is not None:
                    shutil.rmtree(created, ignore_errors=True)
                continue

    created_files: list[Path] = []
    if work is None:
        lines.append("e2e 跳过：找不到可写目录")
    else:
        try:
            txt = work / "diag_input.txt"
            csv_file = work / "diag_input.csv"
            svg = work / "diag_input.svg"
            txt.write_text("中文测试 TransEverything\n", encoding="utf-8")
            csv_file.write_text("a,b\n1,2\n", encoding="utf-8-sig")
            svg.write_text(
                '<svg xmlns="http://www.w3.org/2000/svg" width="20" height="10">'
                '<rect width="20" height="10" fill="blue"/></svg>',
                encoding="utf-8",
            )
            created_files += [txt, csv_file, svg]

            steps = [
                ("txt→pdf", "pdf_word_txt.txt_to_pdf", txt),
                ("csv→xlsx", "excel_csv_tsv.csv_to_excel", csv_file),
                ("svg→png", "image.svg_to_png", svg),
            ]
            for label, module_name, source in steps:
                try:
                    module = importlib.import_module(module_name)
                    result = Path(module.convert(str(source), output_dir=str(work)))
                    created_files.append(result)
                    size = result.stat().st_size if result.exists() else 0
                    lines.append(f"e2e {label}: ok ({size} bytes)")
                except Exception as exc:  # noqa: BLE001
                    lines.append(f"e2e {label}: FAIL {type(exc).__name__}: {exc}")

            # PDF 渲染在内存里验证（同时检验 pdfium 原生库能否加载）
            try:
                import pypdfium2 as pdfium

                pdf_file = work / "diag_input.pdf"
                if pdf_file.exists():
                    document = pdfium.PdfDocument(str(pdf_file))
                    try:
                        image = document[0].render(scale=1.5).to_pil()
                        lines.append(f"e2e pdf 渲染: ok ({image.width}x{image.height})")
                        created_files.append(pdf_file)
                    finally:
                        document.close()
                else:
                    lines.append("e2e pdf 渲染: 跳过（没有生成 PDF）")
            except Exception as exc:  # noqa: BLE001
                lines.append(f"e2e pdf 渲染: FAIL {type(exc).__name__}: {exc}")
        except Exception as exc:  # noqa: BLE001
            lines.append(f"e2e 跳过：{type(exc).__name__}: {exc}")
        finally:
            for path in created_files:
                try:
                    path.unlink()
                except OSError:
                    pass
            if not preferred_dir:
                shutil.rmtree(work, ignore_errors=True)
            else:
                for stale in work.glob("diag_input*"):
                    try:
                        stale.unlink()
                    except OSError:
                        pass

    lines.append(f"user data = {user_data_dir()}")
    lines.append(f"user data writable = {is_dir_writable(user_data_dir())}")
    lines.append(f"logs      = {user_log_dir()}")
    lines.append(f"logs writable = {is_dir_writable(user_log_dir())}")

    report = "\n".join(lines)
    try:
        target = user_log_dir() / "diagnose.txt"
        target.write_text(report + "\n", encoding="utf-8")
    except OSError:
        pass

    try:
        print(report)
    except Exception:
        pass
    return 0


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv if argv is None else argv)

    if "--version" in args:
        _attach_console()
        try:
            print(f"{APP_NAME} {VERSION}")
        except Exception:
            pass
        return 0

    if "--diagnose" in args:
        index = args.index("--diagnose")
        preferred = ""
        if index + 1 < len(args) and not args[index + 1].startswith("-"):
            preferred = args[index + 1]
        return _diagnose(preferred)

    if sys.platform == "win32":
        try:
            import ctypes

            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                "TransEverything.App.1"
            )
        except Exception:
            pass

    app = QApplication(args)
    app.setApplicationName(APP_NAME)
    app.setApplicationDisplayName(APP_NAME)
    app.setOrganizationName(APP_NAME)
    app.setApplicationVersion(VERSION)

    from core.utils import resource_path
    from gui.logsetup import setup_logging

    setup_logging()
    logging.getLogger("trans_everything").info("启动 %s %s", APP_NAME, VERSION)

    from gui.theme import apply_theme

    apply_theme(app)

    icon_path = resource_path("assets", "app.ico")
    if icon_path.is_file():
        app.setWindowIcon(QIcon(str(icon_path)))

    _install_excepthook()

    from gui.mainwindow import MainWindow
    from gui.settings import Settings

    initial = [value for value in args[1:] if not value.startswith("-")]
    window = MainWindow(Settings(), initial_files=initial)
    window.show()

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
