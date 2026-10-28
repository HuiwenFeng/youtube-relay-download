# youtube-relay-download

一个 [WorkBuddy](https://www.workbuddy.cn) 技能（Skill）：在 YouTube 直连被反机器人验证拦截、又拿不到浏览器 cookies 的环境下，经公共 Invidious 实例中继，用**多连接并行分块**方式下载 YouTube 视频（含直播回放），再用 ffmpeg 无损合并为成品 MP4。

全程无需登录 YouTube、无需任何密码、无需 VPN。

## 背景

常规下载手段在这些场景下会全部失效：

- `yt-dlp` 直连报 `Sign in to confirm you're not a bot`（出口 IP 被风控）
- 读浏览器 cookies 需要钥匙串密码 / 被系统隐私权限拦截
- 手机快捷指令因 YouTube 改版集体失效（gluebyte 版失效、R⤓Download 官方不支持 YouTube）
- 服务器中转单连接被限速到 ~50 KB/s

本技能的解法：`latest_version?...&local=true` 代理直链 + 8 连接并行 + 4MB 分块 + 断点续传，实测聚合速度 **800 KB/s ~ 1.6 MB/s**。

## 功能特性

- **自动探测**：标题、时长、直播状态、全部可用格式（itag/分辨率/码率/精确大小），自动推荐最佳画质组合
- **并行分块下载**：8 连接绕开单连接限速；中断后原命令重跑自动续传
- **高可用**：实例列表动态拉取、故障自动切换、下载直链过期自动重取
- **无损合并**：ffmpeg 纯 remux（`-c:v copy -c:a copy`），不重编码，画质无损
- **常见画质全覆盖**：360p ~ 1080p60，H.264 / VP9 / AV1 自动择优（优先 H.264/mp4 保证兼容性）

## 安装

**方式一**：直接解压 zip 到用户技能目录

```bash
unzip youtube-relay-download.zip -d ~/.workbuddy/skills/
```

**方式二**：手动复制

```bash
git clone https://github.com/HuiwenFeng/youtube-relay-download.git
cp -r youtube-relay-download ~/.workbuddy/skills/
```

安装后在 WorkBuddy 中直接说「**下载这个 YouTube 视频：<链接>**」即可自动触发。

## 手动使用

```bash
# 1. 探测视频信息与可用格式（输出推荐 itag 组合）
python3 scripts/probe.py "https://www.youtube.com/watch?v=XXXXXXXXXXX"

# 2. 下载视频轨 + 音频轨（支持断点续传，可放后台）
python3 scripts/relay_dl.py "<URL或ID>" 299 video.mp4 --workers 8 --chunk-mb 4
python3 scripts/relay_dl.py "<URL或ID>" 140 audio.m4a --workers 8 --chunk-mb 4

# 3. 合并为成品 MP4（纯 remux，无损）
ffmpeg -y -i video.mp4 -i audio.m4a -c:v copy -c:a copy -movflags +faststart output.mp4
```

依赖：Python 3（仅标准库）+ ffmpeg（`pip3 install imageio-ffmpeg`）。

## 文件结构

```
youtube-relay-download/
├── SKILL.md               # WorkBuddy 技能主文件（触发条件 + 完整工作流）
├── scripts/
│   ├── probe.py           # 视频信息与格式探测
│   └── relay_dl.py        # 并行分块下载器
└── references/
    └── formats.md         # itag 速查表、Invidious API 要点、排障手册
```

## 注意事项

- 直播中（liveNow）的视频只能下载已播出部分，回放需等直播结束
- 公共 Invidious 实例常年仅个别可用，实例大面积报错时稍等重试即可（脚本自动续传）
- 仅供个人学习备份使用，请遵守 YouTube 服务条款与版权法规

## License

MIT
