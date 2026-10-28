#!/usr/bin/env python3
"""探测 YouTube 视频信息与可用格式（Invidious 路线）

用法：
    python3 probe.py <视频URL或ID>

输出：标题、频道、时长、是否直播回放、全部自适应格式（itag/分辨率/帧率/编码/码率/大小），
并给出推荐下载组合（优先 H.264/mp4 视频轨 + AAC 音频轨，合并兼容性最好）。
JSON 原文写入 probe_result.json 备用。

注意：部分 Invidious 实例的 adaptiveFormats 不返回 res 字段，分辨率按 itag 对照表推断；
码率字段单位为 bps，展示时换算为 kbps。
"""
import json, os, re, sys, urllib.request, ssl

INSTANCE_LIST_URL = "https://api.invidious.io/instances.json?sort_by=health"
FALLBACK_INSTANCES = ["yt.chocolatemoo53.com", "inv.nadeko.net",
                      "invidious.tiekoetter.com", "invidious.nerdvpn.de"]

# itag → (分辨率高度, 常见帧率说明)。查不到的显示 "?"，不影响下载（relay_dl 只用 itag）
ITAG_TABLE = {
    # 音频
    139: (0, "AAC 48k"), 140: (0, "AAC 128k"),
    249: (0, "Opus ~50k"), 250: (0, "Opus ~70k"), 251: (0, "Opus ~160k"),
    # H.264 30fps
    160: (144, "avc1"), 133: (240, "avc1"), 134: (360, "avc1"),
    135: (480, "avc1"), 136: (720, "avc1"), 137: (1080, "avc1"),
    # VP9 30fps
    278: (144, "vp9"), 242: (240, "vp9"), 243: (360, "vp9"),
    244: (480, "vp9"), 247: (720, "vp9"), 248: (1080, "vp9"),
    271: (1440, "vp9"), 313: (2160, "vp9"),
    # H.264 60fps
    298: (720, "avc1 60fps"), 299: (1080, "avc1 60fps"),
    # VP9 60fps
    302: (720, "vp9 60fps"), 303: (1080, "vp9 60fps"),
    308: (1440, "vp9 60fps"), 315: (2160, "vp9 60fps"),
    # AV1 30fps
    394: (144, "av01"), 395: (240, "av01"), 396: (360, "av01"),
    397: (480, "av01"), 398: (720, "av01"), 399: (1080, "av01"),
    # AV1 60fps
    400: (144, "av01 60fps"), 401: (240, "av01 60fps"), 402: (360, "av01 60fps"),
    571: (432, "av01 60fps"), 572: (864, "av01 60fps"),
    # muxed 一体
    18: (360, "muxed"), 22: (720, "muxed"),
}

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE


def normalize_id(s):
    s = s.strip()
    if re.fullmatch(r"[A-Za-z0-9_-]{11}", s):
        return s
    m = re.search(r"(?:v=|youtu\.be/|live/|shorts/|embed/)([A-Za-z0-9_-]{11})", s)
    return m.group(1) if m else None


def load_instances():
    hosts = []
    try:
        req = urllib.request.Request(INSTANCE_LIST_URL, headers={"User-Agent": "Mozilla/5.0"})
        data = json.loads(urllib.request.urlopen(req, timeout=20, context=ctx).read())
        for h, m in data:
            try:
                if m and m.get("type") == "https" and not (m.get("monitor") or {}).get("down"):
                    hosts.append(h)
            except Exception:
                pass
    except Exception:
        pass
    for h in reversed(FALLBACK_INSTANCES):
        if h in hosts:
            hosts.remove(h)
            hosts.insert(0, h)
        elif h not in hosts:
            hosts.insert(0, h)
    return hosts


def codec_of(f):
    """从 type MIME 字段提取编码名，如 avc1.64002A / vp9 / av01.0.08M.08 / mp4a.40.2 / opus"""
    t = f.get("type", "")
    m = re.search(r'codecs="([^"]+)"', t)
    return m.group(1) if m else (f.get("encoding") or "?")


def is_video(f):
    return f.get("type", "").startswith("video/")


def kbps(f):
    try:
        return int(f.get("bitrate", 0)) // 1000
    except Exception:
        return 0


def size_mb(f):
    try:
        return int(f.get("clen", 0)) / 1048576
    except Exception:
        return 0


def codec_pref(f):
    """H.264 优先（合并/兼容性最好），其次 VP9，AV1 最后"""
    c = codec_of(f).lower()
    if c.startswith("avc1") or c.startswith("h264"):
        return 2
    if c.startswith("vp9"):
        return 1
    return 0


def main():
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        print(__doc__)
        sys.exit(0 if "--help" in sys.argv else 1)
    video_id = normalize_id(sys.argv[1])
    if not video_id:
        print(f"无法从参数解析视频 ID: {sys.argv[1]}")
        sys.exit(1)

    data = None
    used = None
    for host in load_instances():
        try:
            req = urllib.request.Request(
                f"https://{host}/api/v1/videos/{video_id}",
                headers={"User-Agent": "Mozilla/5.0"})
            data = json.loads(urllib.request.urlopen(req, timeout=25, context=ctx).read())
            used = host
            break
        except Exception as e:
            print(f"[probe] {host} 失败: {type(e).__name__}", flush=True)
    if not data:
        print("所有实例均无法获取视频信息")
        sys.exit(1)

    title = data.get("title", "?")
    author = data.get("author", "?")
    length = data.get("lengthSeconds", 0)
    live = data.get("liveNow", False)
    dvr = data.get("isPostLiveDvr", False)
    print(f"标题: {title}")
    print(f"频道: {author} | 时长: {length//60} 分 {length%60} 秒 | "
          f"直播中: {live} | 回放可用: {dvr or not live}")
    print(f"信息来自实例: {used}")

    af = data.get("adaptiveFormats", [])
    vids = [f for f in af if is_video(f)]
    auds = [f for f in af if not is_video(f)]

    def height(f):
        return ITAG_TABLE.get(int(f.get("itag", 0)), (0, "?"))[0]

    print("\n== 视频轨（按画质降序，前 12） ==")
    for f in sorted(vids, key=lambda f: (height(f), f.get("fps") or 0, codec_pref(f)),
                    reverse=True)[:12]:
        h = height(f)
        res = f"{h}p" if h else "?"
        print(f"  itag={int(f.get('itag',0)):>4} {res:>6} {f.get('fps','?'):>3}fps "
              f"{codec_of(f)[:20]:<20} {kbps(f):>6}kbps {size_mb(f):>7.1f}MB")

    print("\n== 音频轨（前 6） ==")
    for f in sorted(auds, key=kbps, reverse=True)[:6]:
        print(f"  itag={int(f.get('itag',0)):>4} {codec_of(f)[:20]:<20} "
              f"{kbps(f):>6}kbps {size_mb(f):>7.1f}MB")

    muxed = data.get("formatStreams", [])
    if muxed:
        print("\n== 一体格式 muxed（自带音频，前 5） ==")
        for f in sorted(muxed, key=lambda f: height(f), reverse=True)[:5]:
            h = height(f)
            print(f"  itag={int(f.get('itag',0)):>4} {(f'{h}p' if h else '?'):>6} "
                  f"{codec_of(f)[:20]:<20} {kbps(f):>6}kbps {size_mb(f):>7.1f}MB")

    if vids and auds:
        best_v = max(vids, key=lambda f: (height(f), f.get("fps") or 0, codec_pref(f)))
        # 音频优先 AAC（140）以便与 mp4 直合；无 AAC 则取最高码率
        aac = [f for f in auds if codec_of(f).startswith("mp4a")]
        best_a = max(aac or auds, key=kbps)
        hv = height(best_v)
        print(f"\n推荐组合: 视频 itag={int(best_v.get('itag',0))}"
              f" ({hv if hv else '?'}p{best_v.get('fps','')}, "
              f"{size_mb(best_v):.0f}MB) + 音频 itag={int(best_a.get('itag',0))}"
              f" ({kbps(best_a)}kbps, {size_mb(best_a):.0f}MB)")
        print(f"用法: python3 relay_dl.py {video_id} {int(best_v.get('itag',0))} video.mp4 && "
              f"python3 relay_dl.py {video_id} {int(best_a.get('itag',0))} audio.m4a")

    with open("probe_result.json", "w") as fp:
        json.dump({"host": used, "video_id": video_id, "data": data}, fp)
    print("\n完整 JSON 已存 probe_result.json")


if __name__ == "__main__":
    main()
