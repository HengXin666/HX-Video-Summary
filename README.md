<div align="center">

# 🎬 HX Video Summary

**B站视频 → 语音转写 → AI 总结 → PPT 网页 → 邮件送达 · 全自动**

[![GitHub Pages](https://img.shields.io/badge/Preview-bvs.woa.qzz.io-blue?style=flat-square)](https://bvs.woa.qzz.io/)
[![Python](https://img.shields.io/badge/Python-3.12+-3776AB?style=flat-square&logo=python)](https://www.python.org/)
[![FunASR](https://img.shields.io/badge/ASR-FunASR--paraformer-orange?style=flat-square)](https://github.com/modelscope/FunASR)
[![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)](LICENSE)

</div>

## 📖 简介

输入一个 B站视频链接, 剩下的全部自动完成:

> 下载视频 → 语音转文字 → AI 阅读理解 → 生成 PPT 演示网页 → 部署静态站点 → 邮件通知

在线预览: **[bvs.woa.qzz.io](https://bvs.woa.qzz.io/)**

## ✨ 核心特性

- 🎙️ **FunASR 语音转写** — paraformer-zh 模型, 带 VAD 语音端点检测 + 标点恢复, 输出精确时间戳
- 🤖 **AI 深度总结** — Claude Code + DeepSeek 驱动, 自动阅读转写文本、截图辅助理解, 生成结构化科普文章
- 📊 **PPT 风格网页** — 内置 43+ 模板, 暖色系卡片布局, Font Awesome 图标, 键盘/触控翻页
- 📦 **全自动 CI/CD** — GitHub Actions 一键触发, 产物打包 zip, 部署到 GitHub Pages + Cloudflare Workers
- 📧 **邮件即达** — 纯文本总结正文 + PPT 链接发送到指定邮箱
- 🗂️ **智能索引** — 同一视频多次总结去重, 仅展示最新, 历史可展开
- ⚡ **纯静态部署** — CF Workers 零函数调用, 不消耗请求配额

## 🚀 快速开始

### 环境要求

- Python >= 3.12
- ffmpeg(系统安装并加入 PATH)
- [uv](https://github.com/astral-sh/uv)(Python 包管理器)

### 安装

```bash
git clone https://github.com/HengXin666/HX-Video-Summary.git
cd HX-Video-Summary
uv sync
```

### 本地使用

```bash
# 语音转写 — 处理视频目录下所有视频(默认从小到大)
uv run python py/transcribe.py

# 只处理最新 1 个视频
uv run python py/transcribe.py -n 1

# 处理指定视频 / 强制覆盖
uv run python py/transcribe.py -i "D:\视频\座谈会.mp4" -f

# 视频截图 — 截取指定时间点(HH:MM:SS 或秒数)
uv run python py/transcribe.py screenshot -i video.mp4 -t 00:05:30
uv run python py/transcribe.py screenshot -i video.mp4 -t 120
```

## ☁️ GitHub Actions 工作流

在 GitHub 上一键运行, 无需本地 GPU。

### 配置 Secrets

在仓库 `Settings → Secrets and variables → Actions` 中添加:

| Secret | 必填 | 说明 |
|--------|------|------|
| `DEEPSEEK_API_KEY` | ✅ | DeepSeek API Key |
| `QQ_EMAIL` | ✅ | 发件 QQ 邮箱 |
| `QQ_SMTP_AUTH_CODE` | ✅ | QQ 邮箱 SMTP 授权码(在 `设置 → 账户 → POP3/SMTP服务` 获取) |
| `CF_API_TOKEN` | ❌ | Cloudflare API Token(可选, 用于 Workers 部署) |
| `CF_ACCOUNT_ID` | ❌ | Cloudflare 账户 ID(可选) |

### 触发

1. 进入仓库 `Actions` → **B站视频总结 & PPT生成**
2. 点击 `Run workflow`, 填入 B站链接和接收邮箱
3. 等待完成, 查收邮件

### 产物

| 产物 | 说明 |
|------|------|
| 转写结果-字幕 | 纯转写文本, artifact 保留 30 天 |
| 完整产物包 | 转写 + 总结 + PPT HTML 打包为 zip |
| GitHub Pages | PPT 部署到 `{run_number}/` 子目录, 索引页自动更新 |
| CF Workers | 可选, 同步部署完整站点(纯静态, 零函数调用) |
| 邮件 | 纯文本总结 + PPT 链接 |

## 📁 项目结构

```
HX-Video-Summary/
├── py/                           # Python 源码
│   ├── transcribe.py             # 主脚本: 语音转写 + 截图
│   ├── generate_index.py         # Pages 索引页面生成器
│   ├── send_email.py             # QQ SMTP 邮件发送
│   └── get_bilibili_cookies.py   # Playwright 获取 B站 cookies
├── .github/workflows/            # CI/CD 工作流
│   └── bilibili-summary.yml
├── .codebuddy/skills/            # Claude Code 技能定义
│   └── science-content-ppt/      # 科普内容 PPT 生成(43+ 模板)
├── output/                       # 转写/总结产物
├── pages/                        # Pages 部署暂存
├── pyproject.toml                # 项目配置 & 依赖
├── uv.lock                       # 依赖锁定
├── CLAUDE.md                     # Claude Code 指引
└── README.md
```

## 🏗️ 架构

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│ B站 API      │────▶│ ffmpeg       │────▶│ FunASR      │
│ 下载视频+音频 │     │ 合并/提取音频 │     │ paraformer-zh│
└──────────────┘     └──────────────┘     └───────┬──────┘
                                                  │
                    ┌─────────────────────────────▼─────┐
                    │ Claude Code (DeepSeek 后端)       │
                    │ · 阅读转写文本 + 截图辅助理解       │
                    │ · 总结为结构化科普文章              │
                    │ · science-content-ppt skill 生PPT │
                    └──────────────┬────────────────────┘
                                   │
            ┌──────────────────────┼──────────────────────┐
            ▼                      ▼                      ▼
   ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
   │ GitHub Pages │     │ CF Workers   │     │ QQ 邮件      │
   │ (主站)       │     │ (同步镜像)    │     │ (通知)       │
   └──────────────┘     └──────────────┘     └──────────────┘
```

## 🔗 链接

- **在线预览**: [bvs.woa.qzz.io](https://bvs.woa.qzz.io/)
- **GitHub Pages**: [HengXin666.github.io/HX-Video-Summary](https://HengXin666.github.io/HX-Video-Summary/)
- **GitHub 仓库**: [github.com/HengXin666/HX-Video-Summary](https://github.com/HengXin666/HX-Video-Summary)

## 📄 License

MIT
