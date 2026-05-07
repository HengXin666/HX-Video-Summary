"""
生成 GitHub Pages 索引页面
- 列出所有部署记录, 按时间倒序(最新的在最上面)
- 使用 science-content-ppt 同款配色和动画风格
- 输出到 pages/index.html
- 部署数据持久化: deployments.json 随 Pages 一起部署, 下次运行时从 Pages URL 读取
"""

import os
import re
import json
import urllib.request
import urllib.error
from datetime import datetime
from pathlib import Path

# 从 raw GitHub 拉取(无 CDN 延迟, 避免并发竞态)
RAW_URL = "https://raw.githubusercontent.com/HengXin666/HX-Video-Summary/gh-pages"

# 配色方案(与 science-content-ppt skill 保持一致)
COLORS = {
    "bg": "#0F0E17",
    "text": "#FFFFFE",
    "text_secondary": "#A7A9BE",
    "orange": "#FF6B35",
    "amber": "#F4A261",
    "coral": "#E76F51",
    "teal": "#2EC4B6",
    "red": "#E71D36",
}


def get_current_timestamp():
    """获取当前时间戳(CI 部署时刻)"""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def fetch_existing_deployments(retries: int = 3, delay: float = 0.5) -> list:
    """从 raw GitHub 获取已有部署记录（零 CDN 延迟，带重试）"""
    url = f"{RAW_URL}/deployments.json"
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                print(f"从 raw GitHub 加载了 {len(data)} 条已有记录")
                return data
        except urllib.error.HTTPError as e:
            if e.code == 404:
                print("deployments.json 不存在(首次运行?)")
                return []
            print(f"HTTP {e.code}, 重试 {attempt+1}/{retries}...")
        except Exception as e:
            print(f"获取失败: {e}, 重试 {attempt+1}/{retries}...")
        if attempt < retries - 1:
            import time
            time.sleep(delay)
    print("所有重试均失败, 返回空列表")
    return []


def load_local_deployments(data_file: Path) -> list:
    """加载本地已有部署记录(备用)"""
    if data_file.exists():
        with open(data_file, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def save_deployments(data_file: Path, deployments: list):
    """保存部署记录"""
    data_file.parent.mkdir(parents=True, exist_ok=True)
    with open(data_file, "w", encoding="utf-8") as f:
        json.dump(deployments, f, ensure_ascii=False, indent=2)


def add_current_deployment(deployments: list) -> list:
    """添加当前运行到部署列表"""
    run_number = os.environ.get("RUN_NUMBER", "")
    run_title = os.environ.get("RUN_TITLE", "B站视频")
    bilibili_url = os.environ.get("BILIBILI_URL", "")
    cover_url = fetch_bilibili_cover(bilibili_url)

    # 检查是否已存在(相同 run_number 跳过, 避免重复)
    for d in deployments:
        if d.get("run_number") == run_number:
            # 仅更新可变字段, 保留原始时间戳
            d["title"] = run_title
            d["bilibili_url"] = bilibili_url
            if cover_url:
                d["cover_url"] = cover_url
            return deployments

    # 新增
    entry = {
        "run_number": run_number,
        "title": run_title,
        "bilibili_url": bilibili_url,
        "timestamp": get_current_timestamp(),
        "ppt_file": "bilibili_ppt.html",
        "summary_file": "summary.txt",
    }
    if cover_url:
        entry["cover_url"] = cover_url
    deployments.append(entry)
    return deployments


def format_datetime(dt_str: str) -> str:
    """格式化时间戳为 2026-05-05 22:27:19 格式"""
    try:
        dt = datetime.fromisoformat(dt_str.replace(" ", "T"))
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return dt_str


def extract_video_key(bilibili_url: str, title: str) -> str:
    """提取视频唯一标识，用于去重分组"""
    if bilibili_url:
        m = re.search(r"BV[a-zA-Z0-9]+", bilibili_url)
        if m:
            return m.group(0)
        m = re.search(r"video/([a-zA-Z0-9]+)", bilibili_url)
        if m:
            return m.group(1)
    return title


def fetch_bilibili_cover(bilibili_url: str) -> str:
    """从 B站 API 获取视频封面图 URL"""
    if not bilibili_url:
        return ""
    m = re.search(r"BV[a-zA-Z0-9]+", bilibili_url)
    if not m:
        return ""
    bvid = m.group(0)
    try:
        api_url = f"https://api.bilibili.com/x/web-interface/view?bvid={bvid}"
        req = urllib.request.Request(api_url, headers={
            "User-Agent": "Mozilla/5.0",
            "Referer": "https://www.bilibili.com/",
        })
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data.get("data", {}).get("pic", "")
    except Exception as e:
        print(f"获取封面失败 {bvid}: {e}")
        return ""


def group_deployments(deployments: list) -> list:
    """按视频分组，每组包含最新记录和历史记录"""
    groups = {}
    for d in deployments:
        key = extract_video_key(d.get("bilibili_url", ""), d.get("title", ""))
        groups.setdefault(key, []).append(d)
    for items in groups.values():
        items.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
    result = []
    for key, items in sorted(
        groups.items(),
        key=lambda kv: kv[1][0].get("timestamp", ""),
        reverse=True,
    ):
        result.append({"key": key, "latest": items[0], "history": items[1:]})
    return result


def render_card(d: dict, is_history: bool = False) -> str:
    """渲染单张部署卡片 HTML"""
    ts = format_datetime(d.get("timestamp", ""))
    run_num = d.get("run_number", "")
    title = d.get("title", "未知视频")
    bilibili_url = d.get("bilibili_url", "")
    cover_url = d.get("cover_url", "")
    ppt_url = f"{run_num}/bilibili_ppt.html"
    summary_url = f"{run_num}/summary.txt"

    bilibili_link = (
        f'<a href="{bilibili_url}" target="_blank" class="bilibili-link">'
        f'<i class="fa-brands fa-bilibili"></i> B站原视频</a>'
        if bilibili_url
        else ""
    )
    hist_cls = " history-item" if is_history else ""

    cover_html = ""
    if cover_url:
        cover_html = (
            f'<div class="card-cover">'
            f'<img src="{cover_url}" alt="{title}" loading="lazy" '
            f'onerror="this.parentElement.style.display=\'none\'">'
            f'</div>'
        )

    return f"""
          <div class="deploy-card{hist_cls}">
            {cover_html}
            <div class="card-body">
              <div class="card-header">
                <span class="run-badge">#{run_num}</span>
                <span class="timestamp">{ts}</span>
              </div>
              <h3 class="video-title">{title}</h3>
              <div class="card-actions">
                <a href="{ppt_url}" target="_blank" class="btn btn-primary">
                  <i class="fa-solid fa-tv"></i> 查看PPT
                </a>
                <a href="{summary_url}" target="_blank" class="btn btn-secondary">
                  <i class="fa-solid fa-file-lines"></i> 文字总结
                </a>
                {bilibili_link}
              </div>
            </div>
          </div>"""


def generate_html(groups: list) -> str:
    """生成索引页面 HTML（按视频分组，默认只展示最新，可展开历史）"""
    total_deployments = sum(1 + len(g["history"]) for g in groups)
    total_videos = len(groups)

    entries = ""
    for i, g in enumerate(groups):
        delay = i * 0.08
        hist_count = len(g["history"])

        entries += f"""
        <div class="video-group an" style="animation-delay: {delay}s">
          {render_card(g["latest"])}"""

        if hist_count > 0:
            gid = f"hist-{i}"
            entries += f"""
          <button class="history-toggle" onclick="toggleHistory('{gid}', this)" aria-expanded="false">
            <i class="fa-solid fa-clock-rotate-left"></i>
            展开历史记录 ({hist_count})
            <i class="fa-solid fa-chevron-down toggle-icon"></i>
          </button>
          <div class="history-list" id="{gid}" style="display:none">"""
            for h in g["history"]:
                entries += render_card(h, is_history=True)
            entries += """
          </div>"""

        entries += """
        </div>"""

    # 最新 run_number 用于 header stats
    latest_run = groups[0]["latest"]["run_number"] if groups else "-"

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>HX Video Summary - 视频总结索引</title>
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
  <style>
    /* ===== Reset & Base ===== */
    *, *::before, *::after {{ margin: 0; padding: 0; box-sizing: border-box; }}

    body {{
      background: {COLORS["bg"]};
      color: {COLORS["text"]};
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC",
                   "Hiragino Sans GB", "Microsoft YaHei", sans-serif;
      min-height: 100vh;
      overflow-x: hidden;
    }}

    /* ===== Background Decoration ===== */
    body::before {{
      content: "";
      position: fixed;
      top: 0; left: 0; right: 0; bottom: 0;
      background:
        radial-gradient(ellipse at 20% 20%, {COLORS["orange"]}22 0%, transparent 50%),
        radial-gradient(ellipse at 80% 80%, {COLORS["coral"]}22 0%, transparent 50%);
      pointer-events: none;
      z-index: 0;
    }}

    .bg-grid {{
      position: fixed;
      top: 0; left: 0; right: 0; bottom: 0;
      background-image:
        linear-gradient({COLORS["bg"]}88 1px, transparent 1px),
        linear-gradient(90deg, {COLORS["bg"]}88 1px, transparent 1px);
      background-size: 60px 60px;
      pointer-events: none;
      z-index: 0;
    }}

    /* ===== Header ===== */
    .header {{
      position: relative;
      z-index: 1;
      text-align: center;
      padding: 60px 20px 40px;
    }}

    .header h1 {{
      font-size: 2.8rem;
      font-weight: 800;
      background: linear-gradient(135deg, {COLORS["orange"]}, {COLORS["amber"]}, {COLORS["coral"]});
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
      background-clip: text;
      margin-bottom: 12px;
      letter-spacing: -1px;
    }}

    .header .subtitle {{
      color: {COLORS["text_secondary"]};
      font-size: 1.1rem;
      letter-spacing: 2px;
    }}

    .header .stats {{
      margin-top: 20px;
      display: inline-flex;
      gap: 30px;
      padding: 12px 30px;
      background: {COLORS["bg"]}cc;
      border: 1px solid {COLORS["orange"]}33;
      border-radius: 40px;
    }}

    .header .stat-item {{
      text-align: center;
    }}

    .header .stat-num {{
      display: block;
      font-size: 1.8rem;
      font-weight: 800;
      color: {COLORS["orange"]};
    }}

    .header .stat-label {{
      font-size: 0.8rem;
      color: {COLORS["text_secondary"]};
    }}

    /* ===== Container ===== */
    .container {{
      position: relative;
      z-index: 1;
      max-width: 900px;
      margin: 0 auto;
      padding: 0 20px 80px;
    }}

    /* ===== Deploy Card ===== */
    .deploy-card {{
      background: linear-gradient(135deg, #1a1929, #16151f);
      border: 1px solid {COLORS["orange"]}22;
      border-radius: 16px;
      margin-bottom: 20px;
      transition: all 0.3s ease;
      position: relative;
      overflow: hidden;
      display: flex;
      gap: 20px;
      padding: 20px 24px;
      align-items: flex-start;
    }}

    .deploy-card::before {{
      content: "";
      position: absolute;
      top: 0; left: 0;
      width: 4px;
      height: 100%;
      background: linear-gradient(180deg, {COLORS["orange"]}, {COLORS["coral"]});
      border-radius: 4px 0 0 4px;
    }}

    .deploy-card:hover {{
      border-color: {COLORS["orange"]}55;
      transform: translateX(4px);
      box-shadow: 0 8px 32px {COLORS["orange"]}22;
    }}

    /* ===== Card Cover ===== */
    .card-cover {{
      flex-shrink: 0;
      width: 180px;
      border-radius: 10px;
      overflow: hidden;
      aspect-ratio: 16/9;
    }}

    .card-cover img {{
      width: 100%;
      height: 100%;
      object-fit: cover;
      display: block;
    }}

    .card-body {{
      flex: 1;
      min-width: 0;
    }}

    .card-header {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 14px;
    }}

    .run-badge {{
      background: linear-gradient(135deg, {COLORS["orange"]}, {COLORS["coral"]});
      color: {COLORS["bg"]};
      font-weight: 800;
      font-size: 0.9rem;
      padding: 4px 14px;
      border-radius: 20px;
      letter-spacing: 1px;
    }}

    .timestamp {{
      color: {COLORS["text_secondary"]};
      font-size: 0.85rem;
      font-variant-numeric: tabular-nums;
    }}

    .video-title {{
      font-size: 1.3rem;
      font-weight: 700;
      color: {COLORS["text"]};
      margin-bottom: 18px;
      line-height: 1.5;
      padding-left: 2px;
    }}

    .card-actions {{
      display: flex;
      gap: 12px;
      flex-wrap: wrap;
      align-items: center;
    }}

    /* ===== Buttons ===== */
    .btn {{
      display: inline-flex;
      align-items: center;
      gap: 8px;
      padding: 10px 20px;
      border-radius: 10px;
      font-size: 0.9rem;
      font-weight: 600;
      text-decoration: none;
      transition: all 0.25s ease;
      border: none;
      cursor: pointer;
    }}

    .btn-primary {{
      background: linear-gradient(135deg, {COLORS["orange"]}, {COLORS["coral"]});
      color: {COLORS["bg"]};
      box-shadow: 0 4px 15px {COLORS["orange"]}44;
    }}

    .btn-primary:hover {{
      transform: translateY(-2px);
      box-shadow: 0 6px 20px {COLORS["orange"]}66;
    }}

    .btn-secondary {{
      background: {COLORS["bg"]};
      color: {COLORS["text_secondary"]};
      border: 1px solid {COLORS["text_secondary"]}33;
    }}

    .btn-secondary:hover {{
      border-color: {COLORS["amber"]};
      color: {COLORS["amber"]};
    }}

    .bilibili-link {{
      display: inline-flex;
      align-items: center;
      gap: 6px;
      color: {COLORS["text_secondary"]};
      text-decoration: none;
      font-size: 0.85rem;
      transition: color 0.2s;
    }}

    .bilibili-link:hover {{
      color: {COLORS["orange"]};
    }}

    .bilibili-link .fa-bilibili {{
      color: #00A1D6;
    }}

    /* ===== Empty State ===== */
    .empty-state {{
      text-align: center;
      padding: 80px 20px;
      color: {COLORS["text_secondary"]};
    }}

    .empty-state i {{
      font-size: 4rem;
      color: {COLORS["orange"]}44;
      margin-bottom: 20px;
      display: block;
    }}

    /* ===== Footer ===== */
    .footer {{
      position: relative;
      z-index: 1;
      text-align: center;
      padding: 40px 20px;
      color: {COLORS["text_secondary"]};
      font-size: 0.85rem;
      border-top: 1px solid {COLORS["orange"]}11;
    }}

    .footer a {{
      color: {COLORS["orange"]};
      text-decoration: none;
    }}

    /* ===== Video Group & History ===== */
    .video-group {{
      margin-bottom: 24px;
    }}

    .video-group .deploy-card {{
      margin-bottom: 0;
      border-radius: 16px 16px 0 0;
    }}

    .video-group .deploy-card.history-item {{
      border-radius: 0;
      border-top: none;
      opacity: 0.7;
    }}

    .video-group .deploy-card.history-item:last-of-type {{
      border-radius: 0 0 16px 16px;
    }}

    .video-group .deploy-card.history-item:hover {{
      opacity: 1;
    }}

    .history-toggle {{
      display: flex;
      align-items: center;
      gap: 8px;
      width: 100%;
      padding: 12px 32px;
      background: #1a1929;
      border: 1px solid {COLORS["orange"]}22;
      border-top: 1px solid {COLORS["orange"]}11;
      border-radius: 0 0 16px 16px;
      color: {COLORS["text_secondary"]};
      font-size: 0.85rem;
      font-weight: 600;
      cursor: pointer;
      transition: all 0.25s ease;
      font-family: inherit;
    }}

    .history-toggle:hover {{
      background: #1e1d33;
      border-color: {COLORS["orange"]}44;
      color: {COLORS["amber"]};
    }}

    .history-toggle .toggle-icon {{
      margin-left: auto;
      transition: transform 0.3s ease;
    }}

    .history-toggle[aria-expanded="true"] .toggle-icon {{
      transform: rotate(180deg);
    }}

    .history-list {{
      overflow: hidden;
    }}

    .history-list .deploy-card::before {{
      background: linear-gradient(180deg, {COLORS["text_secondary"]}44, {COLORS["orange"]}44);
    }}

    /* solo card (no history) gets full border-radius */
    .video-group:not(:has(.history-toggle)) .deploy-card {{
      border-radius: 16px;
    }}

    /* ===== Animation ===== */
    .an {{
      opacity: 0;
      transform: translateY(20px);
      animation: fadeInUp 0.5s ease forwards;
    }}

    @keyframes fadeInUp {{
      to {{
        opacity: 1;
        transform: translateY(0);
      }}
    }}

    /* ===== Responsive ===== */
    @media (max-width: 640px) {{
      .header h1 {{ font-size: 2rem; }}
      .deploy-card {{ padding: 16px; flex-direction: column; }}
      .card-cover {{ width: 100%; }}
      .card-actions {{ flex-direction: column; align-items: flex-start; }}
      .header .stats {{ flex-direction: column; gap: 12px; }}
    }}
  </style>
</head>
<body>
  <div class="bg-grid"></div>

  <!-- Header -->
  <header class="header">
    <h1><i class="fa-solid fa-film"></i> HX Video Summary</h1>
    <p class="subtitle">B站视频智能总结 & PPT 生成记录</p>
    <div class="stats">
      <div class="stat-item">
        <span class="stat-num">{total_videos}</span>
        <span class="stat-label">独立视频</span>
      </div>
      <div class="stat-item">
        <span class="stat-num">{total_deployments}</span>
        <span class="stat-label">总计部署</span>
      </div>
      <div class="stat-item">
        <span class="stat-num">#{latest_run}</span>
        <span class="stat-label">最近部署</span>
      </div>
    </div>
  </header>

  <!-- Main Content -->
  <main class="container">
    {entries if entries else '''
    <div class="empty-state">
      <i class="fa-solid fa-inbox"></i>
      <p>暂无部署记录, 请先运行工作流生成视频总结</p>
    </div>
    '''}
  </main>

  <!-- Footer -->
  <footer class="footer">
    <p>
      Powered by <a href="https://github.com/HengXin666/HX-Video-Summary" target="_blank">HX-Video-Summary</a>
      &nbsp;·&nbsp;
      <i class="fa-solid fa-heart" style="color:{COLORS["coral"]}"></i>
      &nbsp;自动部署于 GitHub Pages
    </p>
    <p style="margin-top:8px;font-size:0.8rem;color:{COLORS["text_secondary"]}77">
      索引页面自动生成 · 同一视频仅展示最新 · 点击展开历史
    </p>
  </footer>

  <script>
    function toggleHistory(gid, btn) {{
      const list = document.getElementById(gid);
      const expanded = btn.getAttribute("aria-expanded") === "true";
      if (expanded) {{
        list.style.display = "none";
        btn.setAttribute("aria-expanded", "false");
        btn.style.borderRadius = "0 0 16px 16px";
      }} else {{
        list.style.display = "block";
        btn.setAttribute("aria-expanded", "true");
        btn.style.borderRadius = "0";
      }}
    }}
  </script>
</body>
</html>"""
    return html


def main():
    output_dir = Path("pages")
    output_dir.mkdir(parents=True, exist_ok=True)

    # 优先从 Pages URL 读取已有部署数据(跨运行持久化)
    deployments = fetch_existing_deployments()

    # 备用: 如果 URL 读取失败, 尝试读取本地文件
    if not deployments:
        deployments = load_local_deployments(Path("data/deployments.json"))

    # 添加当前部署
    deployments = add_current_deployment(deployments)

    # 回填缺失的封面
    for d in deployments:
        if not d.get("cover_url") and d.get("bilibili_url"):
            cover = fetch_bilibili_cover(d["bilibili_url"])
            if cover:
                d["cover_url"] = cover
                print(f"回填封面: #{d.get('run_number')} -> {cover}")

    # 按时间戳倒序排列(最新的在最上面)
    deployments.sort(key=lambda x: x.get("timestamp", ""), reverse=True)

    # 保存数据到本地(备用)和 pages 目录(用于持久化到 Pages)
    save_deployments(Path("data/deployments.json"), deployments)
    save_deployments(output_dir / "deployments.json", deployments)

    # 按视频分组（同一视频只展示最新，历史可展开）
    groups = group_deployments(deployments)

    # 生成 HTML
    html = generate_html(groups)

    # 写入输出
    output_file = output_dir / "index.html"
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(html)

    total = sum(1 + len(g["history"]) for g in groups)
    print(f"索引页面已生成: {output_file}")
    print(f"共 {len(groups)} 个独立视频, {total} 条部署记录")


if __name__ == "__main__":
    main()
