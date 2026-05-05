# HX-Video-Summary

视频转写与总结工具, 使用 FunASR (paraformer-zh) 进行中文语音识别, 支持标点恢复和语音端点检测(VAD)。

## 功能

- 视频音频提取 + 语音转文字(带时间戳)
- 视频任意时间点截图(供 AI 识图)
- 转写结果配合 AI skill 生成 PPT 演示网页
- **GitHub 工作流**: 输入 B 站视频链接, 自动下载 → 转写 → AI 总结 → 生成 PPT → 邮件发送

## 依赖

- Python >= 3.12
- ffmpeg(需系统安装并加入 PATH)
- uv(包管理器)
- [yt-dlp](https://github.com/yt-dlp/yt-dlp)(GitHub 工作流自动安装)

## 安装

```bash
uv sync
```

## 使用

### 语音转写

```bash
# 处理所有视频
uv run transcribe.py

# 只处理最新的1个视频
uv run transcribe.py -n 1

# 指定视频路径
uv run transcribe.py -i "D:\视频\座谈会.mp4"

# 指定输出目录
uv run transcribe.py -o ./result
```

### 视频截图

```bash
# 截取视频第 5 分 30 秒的帧
uv run transcribe.py screenshot -i "D:\视频\座谈会.mp4" -t 00:05:30

# 截取视频第 120 秒的帧
uv run transcribe.py screenshot -i "D:\视频\座谈会.mp4" -t 120

# 指定截图保存路径
uv run transcribe.py screenshot -i "D:\视频\座谈会.mp4" -t 00:05:30 -o ./screenshots
```

## GitHub 工作流(B站视频总结 & PPT生成)

在 GitHub Actions 中一键完成: 下载 B 站视频 → 语音转写 → AI 总结 → 生成 PPT 网页 → 邮件发送。

### 配置 Secrets

在仓库 `Settings > Secrets and variables > Actions` 中添加以下 secrets:

| Secret | 说明 |
|--------|------|
| `DEEPSEEK_API_KEY` | DeepSeek API Key, 用于调用大模型 |
| `QQ_EMAIL` | 发件人 QQ 邮箱地址, 如 `123456@qq.com` |
| `QQ_SMTP_AUTH_CODE` | QQ 邮箱 SMTP 授权码(非 QQ 密码), 在 QQ 邮箱 `设置 > 账户 > POP3/SMTP服务` 中获取 |

### 触发工作流

1. 进入仓库 `Actions` 标签页
2. 选择 **B站视频总结 & PPT生成**
3. 点击 `Run workflow`
4. 填入 B 站视频链接和接收邮箱
5. 点击 `Run workflow` 启动

### 产物

- **PPT HTML**: 工作流完成后可在 Actions 页面下载 `bilibili-ppt` artifact
- **邮件**: PPT HTML 作为附件发送到指定邮箱(同时抄送发件人)

### 工作流架构

```
用户输入B站URL → yt-dlp下载视频 → ffmpeg提取音频
→ FunASR语音转写 → Claude Code(AI)总结 + 截图辅助理解
→ science-content-ppt skill 生成PPT网页 → 上传Artifact + QQ邮件发送
```

### AI 自动驾驶配置

工作流中的 Claude Code 使用 DeepSeek 作为后端(通过 Anthropic 兼容 API), 配置如下:

```bash
ANTHROPIC_BASE_URL=https://api.deepseek.com/anthropic
ANTHROPIC_MODEL=deepseek-v4-pro[1m]
ANTHROPIC_DEFAULT_OPUS_MODEL=deepseek-v4-pro[1m]
ANTHROPIC_DEFAULT_SONNET_MODEL=deepseek-v4-pro[1m]
ANTHROPIC_DEFAULT_HAIKU_MODEL=deepseek-v4-flash
CLAUDE_CODE_SUBAGENT_MODEL=deepseek-v4-flash
CLAUDE_CODE_EFFORT_LEVEL=max
```

非交互模式通过 `--permission-mode bypassPermissions` 实现全自动运行。

## 工作流

1. 使用 `transcribe.py` 将视频转写为带时间戳的文本
2. 将转写结果交给 AI 进行总结
3. 使用 science-content-ppt skill 生成 PPT 演示网页
4. 对有疑惑的内容使用 `screenshot` 截图, 让 AI 结合图像理解

## 项目结构

```
HX-Video-Summary/
├── transcribe.py                # 主脚本(转写 + 截图)
├── send_email.py                # QQ邮箱发送工具
├── pyproject.toml               # 项目配置
├── output/                      # 转写结果输出目录
├── .codebuddy/skills/           # AI skill 定义
└── .github/workflows/           # GitHub Actions 工作流
    └── bilibili-summary.yml
```
