r"""用抓取到的 Pinterest 图片送入 ComfyUI 工作流，生成图片（命令行入口）。

运行方式（需已激活 .venv）：
    # 完整流程：先抓取 Pinterest 图片入库，再批量送入 ComfyUI 生成
    .venv\Scripts\python.exe examples/pinterest_generate.py

    # 仅对图片库中已有图片批量生成（不重新抓取）
    .venv\Scripts\python.exe examples/pinterest_generate.py --generate-only

说明：
- 抓取使用浏览器后端（nodriver），登录态持久化到 libraries/browser_profile。
- 生成使用 config/krea2i2i_api.json 工作流（API 模式），输出到 libraries/outputs/。
- ComfyUI 地址默认 http://10.0.0.190:8188（见 config/core_config.json）。
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config.manager import CoreConfigManager  # noqa: E402
from app.core.image_library import ImageLibrary  # noqa: E402
from app.core.pinterest_flow import crawl_pinterest, generate_from_library  # noqa: E402


def _print_progress(stage: str, message: str) -> None:
    print(f"[{stage}] {message}", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Pinterest 图片抓取 + ComfyUI 图生图（命令行）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="示例：\n"
               "  python examples/pinterest_generate.py\n"
               "  python examples/pinterest_generate.py --generate-only\n"
               "  python examples/pinterest_generate.py --generate-only --max-images 5")
    parser.add_argument("--generate-only", action="store_true",
                        help="仅对图片库已有图片生成，不重新抓取")
    parser.add_argument("--max-images", type=int, default=0,
                        help="最多生成的图片数（0 表示全部）")
    args = parser.parse_args()

    mgr = CoreConfigManager()
    cfg = mgr.config

    if args.generate_only:
        library = ImageLibrary.resolve(
            root_dir=cfg.library.root_dir,
            library_name=cfg.crawler.output_library)
        print(f"从图片库读取 {library.count()} 张图片，开始生成…", flush=True)
    else:
        library = crawl_pinterest(cfg, progress=_print_progress)

    try:
        generate_from_library(cfg, library, max_images=args.max_images,
                              progress=_print_progress)
    except KeyboardInterrupt:
        print("\n已被用户中断（Ctrl+C）。已生成的图片均已保存到输出目录，可随时重新运行继续。",
              flush=True)
        sys.exit(130)


if __name__ == "__main__":
    main()
