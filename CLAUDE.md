# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

视频转写与总结工具。使用 FunASR (paraformer-zh) 对中文视频进行语音识别(带 VAD 和标点恢复), 配合内置的 science-content-ppt skill 将转写结果生成 PPT 演示网页。

## 常用命令

```bash
# 安装依赖(需要 Python >= 3.12 + 系统安装 ffmpeg)
uv sync

# 语音转写 — 处理视频目录下所有视频(默认从小到大)
uv run transcribe.py

# 只处理最新 N 个视频(配合 -n)
uv run transcribe.py -n 1

# 处理指定视频 / 指定输出目录 / 强制覆盖
uv run transcribe.py -i "D:\视频\座谈会.mp4"
uv run transcribe.py -o ./my-output
uv run transcribe.py -i video.mp4 -f

# 截图 — 截取视频指定时间点的帧(HH:MM:SS 或秒数)
uv run transcribe.py screenshot -i video.mp4 -t 00:05:30
uv run transcribe.py screenshot -i video.mp4 -t 120
```

## 架构

只有一个核心脚本 `transcribe.py`(383 行), 包含两个子命令:

- **transcribe(默认)**: `cmd_transcribe()` — 查找视频 → ffmpeg 提取 16kHz 单声道 WAV → FunASR paraformer-zh 识别 → 格式化为带时间戳的文本 → 输出到 `output/`
- **screenshot**: `cmd_screenshot()` — ffmpeg 截取指定时间点帧 → 输出到 `output/screenshots/`

关键路径约定:
- **视频目录**: `VIDEO_DIR = Path(__file__).resolve().parent.parent.parent`(即 HX-Video-Summary 的上上级目录)
- **输出目录**: `OUTPUT_DIR = output/`, 转写结果写入 `{视频名}_转写.txt`, 汇总合并到 `转写结果.txt`

模型初始化(`funasr.AutoModel`)使用 `paraformer-zh` + `fsmn-vad` + `ct-punc`, 首次运行自动下载到 `~/.cache/modelscope/`。

## 工作流

1. `transcribe.py` 将视频转写为带时间戳的文本
2. 将转写结果交给 AI 进行内容总结
3. 配合 `.codebuddy/skills/science-content-ppt/` skill 生成 PPT 演示网页
4. 对有疑惑的内容用 `screenshot` 截图, 让 AI 结合图像理解

## 依赖注意事项

- **ffmpeg** 必须系统安装并加入 PATH
- FunASR 模型首次运行自动下载, 需要网络连接
- `torch` + `torchaudio` 在 pyproject.toml 中声明, `uv sync` 自动安装
- 构建依赖 `editdistance` 需要 `pdm-backend`(已在 `pyproject.toml` 的 `tool.uv.extra-build-dependencies` 中配置)
