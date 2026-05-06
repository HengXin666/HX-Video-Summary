"""
中文视频转写与截图工具
使用 FunASR (paraformer-zh) 模型进行语音识别
支持标点恢复和语音端点检测(VAD)

用法:
    uv run python py/transcribe.py                    # 处理所有视频
    uv run python py/transcribe.py -n 1               # 只处理最新的1个视频
    uv run python py/transcribe.py -i video.mp4       # 处理指定视频
    uv run python py/transcribe.py screenshot -i video.mp4 -t 00:05:30   # 截图
"""

import argparse
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from datetime import timedelta

from funasr import AutoModel

# 视频目录：上级目录（HX-Video-Summary -> 视频总结 -> 座谈会目录）
VIDEO_DIR = Path(__file__).resolve().parent.parent.parent
# 支持的视频格式
VIDEO_EXTS = {".mp4", ".mkv", ".avi", ".mov", ".flv", ".wmv", ".webm"}
# 输出目录
OUTPUT_DIR = Path(__file__).resolve().parent / "output"


def format_timestamp(ms: float) -> str:
    """将毫秒格式化为 HH:MM:SS.mmm"""
    s, ms_part = divmod(ms, 1000)
    m, s = divmod(int(s), 60)
    h, m = divmod(m, 60)
    return f"{h:02d}:{m:02d}:{s:02d}.{int(ms_part):03d}"


def parse_time_to_seconds(time_str: str) -> float:
    """将时间字符串转为秒数，支持 HH:MM:SS、MM:SS、纯秒数"""
    parts = time_str.split(":")
    try:
        if len(parts) == 3:
            h, m, s = parts
            return int(h) * 3600 + int(m) * 60 + float(s)
        elif len(parts) == 2:
            m, s = parts
            return int(m) * 60 + float(s)
        else:
            return float(time_str)
    except (ValueError, IndexError):
        raise argparse.ArgumentTypeError(
            f"无法解析时间: {time_str}，支持格式: HH:MM:SS、MM:SS 或秒数"
        )


def extract_audio(video_path: str, audio_path: str) -> bool:
    """使用 ffmpeg 从视频中提取音频为 16kHz 单声道 WAV"""
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        video_path,
        "-vn",
        "-acodec",
        "pcm_s16le",
        "-ar",
        "16000",
        "-ac",
        "1",
        audio_path,
    ]
    result = subprocess.run(
        cmd, capture_output=True, text=True, encoding="utf-8", errors="replace"
    )
    return result.returncode == 0


def screenshot_frame(video_path: str, timestamp: float, output_path: str) -> bool:
    """使用 ffmpeg 截取视频指定时间点的帧"""
    cmd = [
        "ffmpeg",
        "-y",
        "-ss",
        str(timestamp),
        "-i",
        video_path,
        "-frames:v",
        "1",
        "-q:v",
        "2",
        output_path,
    ]
    result = subprocess.run(
        cmd, capture_output=True, text=True, encoding="utf-8", errors="replace"
    )
    return result.returncode == 0


def find_videos(directory: Path) -> list[Path]:
    """查找目录下的所有视频文件，按文件大小排序（最小的优先）"""
    videos = []
    for f in directory.iterdir():
        if f.is_file() and f.suffix.lower() in VIDEO_EXTS:
            videos.append(f)
    videos.sort(key=lambda x: x.stat().st_size)
    return videos


def format_output(result: list[dict], video_name: str) -> str:
    """将识别结果格式化为可读文本，带时间戳"""
    lines = []
    lines.append(f"视频: {video_name}")
    lines.append("=" * 60)
    lines.append("")

    for res in result:
        text = res.get("text", "")
        timestamp = res.get("timestamp", None)

        if timestamp and len(timestamp) > 0:
            sentences = []
            current_chars = []
            current_start = timestamp[0][0] if timestamp else 0
            current_end = timestamp[0][1] if timestamp else 0

            for idx, char in enumerate(text):
                current_chars.append(char)
                if idx < len(timestamp):
                    current_end = timestamp[idx][1]

                if char in "。！？；\n":
                    sentences.append(
                        {
                            "text": "".join(current_chars).strip(),
                            "start": current_start,
                            "end": current_end,
                        }
                    )
                    current_chars = []
                    if idx + 1 < len(timestamp):
                        current_start = timestamp[idx + 1][0]

            if current_chars:
                sentences.append(
                    {
                        "text": "".join(current_chars).strip(),
                        "start": current_start,
                        "end": current_end,
                    }
                )

            for sent in sentences:
                if sent["text"]:
                    start_str = format_timestamp(sent["start"])
                    end_str = format_timestamp(sent["end"])
                    lines.append(f"[{start_str} -> {end_str}]")
                    lines.append(f"  {sent['text']}")
                    lines.append("")
        else:
            paragraphs = []
            current = []
            for char in text:
                current.append(char)
                if char in "。！？；":
                    paragraphs.append("".join(current))
                    current = []
            if current:
                paragraphs.append("".join(current))

            for para in paragraphs:
                para = para.strip()
                if para:
                    lines.append(para)
                    lines.append("")

    lines.append("=" * 60)
    lines.append("")
    return "\n".join(lines)


def cmd_transcribe(args):
    """执行语音转写"""
    # 确定视频列表
    if args.input:
        video_paths = [Path(args.input)]
        if not video_paths[0].exists():
            print(f"错误：文件不存在: {args.input}")
            sys.exit(1)
        if video_paths[0].suffix.lower() not in VIDEO_EXTS:
            print(f"错误：不支持的视频格式: {video_paths[0].suffix}")
            sys.exit(1)
    else:
        video_paths = find_videos(args.video_dir)
        if not video_paths:
            print(f"在 {args.video_dir} 下未找到视频文件")
            return

    if args.num:
        video_paths = video_paths[: args.num]

    # 确定输出目录
    output_dir = Path(args.output) if args.output else OUTPUT_DIR
    output_dir.mkdir(exist_ok=True, parents=True)

    # 初始化模型
    print("正在加载模型 paraformer-zh（首次运行需要下载，请耐心等待）...")
    model = AutoModel(
        model="paraformer-zh",
        vad_model="fsmn-vad",
        punc_model="ct-punc",
        disable_update=True,
    )
    print("模型加载完成！")

    print(f"找到 {len(video_paths)} 个视频文件：")
    for v in video_paths:
        size_mb = v.stat().st_size / (1024 * 1024)
        print(f"  - {v.name} ({size_mb:.1f} MB)")
    print()

    # 逐个处理
    for i, video in enumerate(video_paths, 1):
        print(f"[{i}/{len(video_paths)}] 正在处理: {video.name}")

        safe_name = video.stem
        single_file = output_dir / f"{safe_name}_转写.txt"
        if single_file.exists() and not args.force:
            print(f"  已存在转写结果，跳过: {single_file.name}")
            continue

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            audio_path = tmp.name

        try:
            print("  提取音频...")
            if not extract_audio(str(video), audio_path):
                print(f"  错误：无法从 {video.name} 提取音频")
                continue

            audio_size_mb = os.path.getsize(audio_path) / (1024 * 1024)
            print(f"  音频大小: {audio_size_mb:.1f} MB")

            print("  识别语音（可能需要较长时间）...")
            result = model.generate(
                input=audio_path,
                batch_size_s=300,
                hotword="",
            )

            formatted = format_output(result, video.name)

            with open(single_file, "w", encoding="utf-8") as f:
                f.write(formatted)
            print(f"  已保存: {single_file.name}")

        finally:
            if os.path.exists(audio_path):
                os.unlink(audio_path)

    # 汇总所有结果
    all_results = sorted(output_dir.glob("*_转写.txt"))
    if all_results:
        combined_file = output_dir / "转写结果.txt"
        with open(combined_file, "w", encoding="utf-8") as f:
            for result_file in all_results:
                content = result_file.read_text(encoding="utf-8")
                f.write(content)
                f.write("\n")
        print(f"\n汇总结果已保存到: {combined_file}")


def cmd_screenshot(args):
    """执行视频截图"""
    if not args.input:
        print("错误：截图模式必须指定视频路径 (-i / --input)")
        sys.exit(1)

    video_path = Path(args.input)
    if not video_path.exists():
        print(f"错误：文件不存在: {args.input}")
        sys.exit(1)

    # 解析时间
    try:
        ts_seconds = parse_time_to_seconds(args.time)
    except argparse.ArgumentTypeError as e:
        print(f"错误：{e}")
        sys.exit(1)

    # 确定输出目录
    output_dir = Path(args.output) if args.output else OUTPUT_DIR / "screenshots"
    output_dir.mkdir(exist_ok=True, parents=True)

    # 生成输出文件名
    safe_name = video_path.stem
    ts_label = args.time.replace(":", "-")
    output_file = output_dir / f"{safe_name}_{ts_label}.jpg"

    print(f"正在截取: {video_path.name} @ {args.time} ({ts_seconds}s)")

    if screenshot_frame(str(video_path), ts_seconds, str(output_file)):
        size_kb = output_file.stat().st_size / 1024
        print(f"截图已保存: {output_file} ({size_kb:.1f} KB)")
    else:
        print("截图失败，请检查视频文件和时间点是否正确")
        sys.exit(1)


def build_parser() -> argparse.ArgumentParser:
    """构建命令行参数解析器"""
    parser = argparse.ArgumentParser(
        description="视频转写与截图工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""示例:
  uv run python py/transcribe.py                        处理所有视频
  uv run python py/transcribe.py -n 1                   只处理1个视频
  uv run python py/transcribe.py -i video.mp4           处理指定视频
  uv run python py/transcribe.py -o ./result            指定输出目录
  uv run python py/transcribe.py screenshot -i v.mp4 -t 00:05:30   截图
  uv run python py/transcribe.py screenshot -i v.mp4 -t 120         截图(秒)""",
    )

    subparsers = parser.add_subparsers(dest="command", help="子命令")

    # 转写子命令（默认）
    transcribe_parser = subparsers.add_parser("transcribe", help="语音转写（默认）")
    transcribe_parser.add_argument(
        "-i", "--input", help="指定视频文件路径（不指定则扫描视频目录）"
    )
    transcribe_parser.add_argument(
        "-n", "--num", type=int, help="处理视频数量（从最小的开始）"
    )
    transcribe_parser.add_argument("-o", "--output", help="输出目录（默认: ./output）")
    transcribe_parser.add_argument(
        "-d",
        "--video-dir",
        default=str(VIDEO_DIR),
        help=f"视频搜索目录（默认: {VIDEO_DIR}）",
    )
    transcribe_parser.add_argument(
        "-f", "--force", action="store_true", help="强制重新转写（覆盖已有结果）"
    )

    # 截图子命令
    screenshot_parser = subparsers.add_parser("screenshot", help="截取视频帧")
    screenshot_parser.add_argument("-i", "--input", required=True, help="视频文件路径")
    screenshot_parser.add_argument(
        "-t", "--time", required=True, help="截图时间点（HH:MM:SS / MM:SS / 秒数）"
    )
    screenshot_parser.add_argument(
        "-o", "--output", help="截图保存目录（默认: ./output/screenshots）"
    )

    return parser


def main():
    parser = build_parser()

    # 兼容无子命令的直接调用: transcribe.py [数字]
    if (
        len(sys.argv) > 1
        and not sys.argv[1].startswith("-")
        and sys.argv[1] not in ("transcribe", "screenshot")
    ):
        try:
            num = int(sys.argv[1])
            sys.argv = [sys.argv[0], "transcribe", "-n", str(num)]
        except ValueError:
            pass

    args = parser.parse_args()

    if args.command == "screenshot":
        cmd_screenshot(args)
    else:
        # 默认执行转写
        cmd_transcribe(args)


if __name__ == "__main__":
    main()
