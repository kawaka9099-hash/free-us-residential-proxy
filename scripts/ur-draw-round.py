#!/usr/bin/env python3
"""URnetwork 一轮抽取：打包好的完整流程。
用法：
  python3 ur-draw-round.py            # 抽一轮（最多 5 个），抽到干净节点就停，写交付文件
  python3 ur-draw-round.py --dry-run  # 只验凭据、列 provider，不建代理
凭据：优先 ~/workspace/weeny-cli/ur-api-key.txt（长期 urn_ key），
      其次 ~/workspace/weeny-cli/ur-jwt.txt（JWT，会过期）。
交付文件写到 ~/workspace/your_files/：
  urnetwork-us-node.txt       V2rayN 明文链接
  urnetwork-us-node-xray.json Xray outbound
  urnetwork-us-clash.yaml     Clash Verge 配置
回报里绝不打印 api_key / JWT / auth_token 原文。
"""
import argparse, json, os, re, subprocess, sys, time, urllib.request

BASE = "https://api.bringyour.com"
HOME = os.path.expanduser("~")
CREDS = [
    os.path.join(HOME, "workspace/weeny-cli/ur-api-key.txt"),
    os.path.join(HOME, "workspace/weeny-cli/ur-jwt.txt"),
]
LOCID_FILE = os.path.join(HOME, "workspace/weeny-cli/ur-us-locid.txt")
OUT_DIR = os.path.join(HOME, "workspace/your_files")
PROXY_ENV = {"http_proxy": "http://198.19.0.1:3128", "https_proxy": "http://198.19.0.1:3128"}
MAX_TRIES = 5


def load_token():
    for path in CREDS:
        if os.path.exists(path):
            tok = open(path).read().strip()
            if tok:
                return tok, path
    return None, None


def curl_json(method, path, body=None, timeout=60):
    """用 curl 调 API（urllib 读大块分块响应会 IncompleteRead 截断）。返回 (status, parsed_json_or_None)。"""
    cmd = ["curl", "-s", "-m", str(timeout), "-X", method, BASE + path,
           "-H", f"Authorization: Bearer {TOKEN}", "-H", "Content-Type: application/json"]
    if body is not None:
        cmd += ["-d", json.dumps(body)]
    env = dict(os.environ)
    env.update(PROXY_ENV)
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + 10, env=env)
    try:
        return r.returncode, json.loads(r.stdout)
    except Exception:
        return r.returncode, None


def api_post(path, body, timeout=60):
    _, data = curl_json("POST", path, body, timeout)
    return data


def remove_client(client_id):
    api_post("/network/remove-client", {"client_id": client_id}, timeout=30)


def exit_via_proxy(proxy_url):
    """经 SOCKS 代理查出口。返回 ip-api 字典或 None。"""
    env = {k: v for k, v in os.environ.items() if k.lower() not in ("http_proxy", "https_proxy", "all_proxy")}
    cmd = ["curl", "-s", "-m", "20", "--proxy", proxy_url,
           "http://ip-api.com/json/?fields=status,country,regionName,city,isp,org,as,proxy,hosting,query"]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=30, env=env)
        d = json.loads(r.stdout)
        return d if d.get("status") == "success" else None
    except Exception:
        return None


def accept(exit_info, country="United States"):
    """验收：双 false、真宽带 ISP、国家一致。返回 (ok, reason)。"""
    if not exit_info:
        return False, "no exit"
    if exit_info.get("proxy") is not False or exit_info.get("hosting") is not False:
        return False, f"proxy={exit_info.get('proxy')} hosting={exit_info.get('hosting')}"
    if exit_info.get("country") != country:
        return False, f"country={exit_info.get('country')}"
    isp = (exit_info.get("isp") or "").lower()
    bad = ["hosting", "datacenter", "data center", "cloud", "vps", "server"]
    if any(b in isp for b in bad):
        return False, f"isp looks datacenter: {exit_info.get('isp')}"
    return True, "ok"


def write_deliverables(kept):
    token = kept["auth_token"]
    host = kept["host"]
    port = kept["port"]
    exit_info = kept["exit"]
    city = exit_info.get("city") or "US"
    isp = exit_info.get("isp") or "ISP"
    city_clean = re.sub(r"[^A-Za-z0-9]+", "", city)
    isp_clean = re.sub(r"[^A-Za-z0-9]+", "", isp.split(",")[0].split(" ")[0])
    frag = f"URnetwork-US-{city_clean}-{isp_clean}-Clean"
    v2link = f"socks://{token}:x@{host}:{port}#{frag}"
    os.makedirs(OUT_DIR, exist_ok=True)
    txt = os.path.join(OUT_DIR, "urnetwork-us-node.txt")
    with open(txt, "w") as f:
        f.write(v2link + "\n")
    os.chmod(txt, 0o600)
    xray = {"outbounds": [{"protocol": "socks",
        "settings": {"servers": [{"address": host, "port": port, "users": [{"user": token, "pass": "x"}]}]},
        "tag": "urnetwork-us"}]}
    xj = os.path.join(OUT_DIR, "urnetwork-us-node-xray.json")
    with open(xj, "w") as f:
        json.dump(xray, f, indent=2)
    os.chmod(xj, 0o600)
    cy = os.path.join(OUT_DIR, "urnetwork-us-clash.yaml")
    with open(cy, "w") as f:
        f.write(f"# URnetwork 美国住宅节点（SOCKS5）\n# 出口：{exit_info.get('query')}，{city}，{exit_info.get('regionName')}，{exit_info.get('country')}，{isp}\n# 节点是一次性的：provider 下线即作废，到时重抽一个替换这里的账号密码即可\nproxies:\n  - name: \"URnetwork-US-{city_clean}-{isp_clean}\"\n    type: socks5\n    server: {host}\n    port: {port}\n    username: \"{token}\"\n    password: \"x\"\n    udp: true\n")
    os.chmod(cy, 0o600)
    return txt, xj, cy


def main():
    global TOKEN
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--tries", type=int, default=MAX_TRIES)
    args = ap.parse_args()

    TOKEN, src = load_token()
    if not TOKEN:
        print("ERROR: no credential file found (ur-api-key.txt / ur-jwt.txt). Need a fresh auth code from ur.io settings.")
        return 2
    print(f"credential: {os.path.basename(src)} (not printed)")

    # 1. 验凭据：取 US location_id（顺带验 token 有效）
    locid = None
    if os.path.exists(LOCID_FILE):
        locid = open(LOCID_FILE).read().strip()
    data = api_post("/network/find-provider-locations", {"query": "United States"})
    if not data or "locations" not in data:
        print("ERROR: credential invalid/expired or API unreachable. Need a fresh auth code from ur.io settings.")
        return 2
    us = [l for l in data.get("locations", []) if l.get("location_type") == "country"]
    if us:
        locid = us[0]["location_id"]
        open(LOCID_FILE, "w").write(locid)
        os.chmod(LOCID_FILE, 0o600)
    if not locid:
        print("ERROR: US location_id not found.")
        return 2
    print("auth OK, US location_id ready")

    # 2. 拉 provider，优先真实城市，按速度排序
    data = api_post("/network/find-providers2", {"specs": [{"location_id": locid}], "count": 50})
    providers = (data or {}).get("providers", [])
    city = [p for p in providers if (p.get("location") or {}).get("city") and (p.get("location") or {}).get("city") != "United States"]
    city.sort(key=lambda p: p.get("estimated_bytes_per_second") or 0, reverse=True)
    print(f"providers: {len(providers)} total, {len(city)} city-specific")
    for p in city[:args.tries]:
        loc = p.get("location") or {}
        print(f"  candidate speed={p.get('estimated_bytes_per_second')} city={loc.get('city')} region={loc.get('region')}")
    if args.dry_run:
        print("DRY-RUN OK: credential valid, providers listed, no proxy created.")
        return 0

    # 3. 抽一轮
    tried = 0
    for idx, provider in enumerate(city[:args.tries]):
        tried += 1
        loc = provider.get("location") or {}
        print(f"\n=== try {tried}/{args.tries} speed={provider.get('estimated_bytes_per_second')} city={loc.get('city')} region={loc.get('region')} ===", flush=True)
        resp = api_post("/network/auth-client", {"proxy_config": {"initial_device_state": {"location": {"connect_location_id": {"client_id": provider.get("client_id")}}}}})
        if not resp:
            print("auth-client: no response, skip", flush=True)
            continue
        result = resp.get("proxy_config_result") or {}
        auth_token = result.get("auth_token")
        created_id = result.get("client_id")
        socks_url = result.get("socks_proxy_url") or ""
        if not auth_token or not created_id:
            print("auth-client: missing auth_token/client_id, skip", flush=True)
            continue
        if socks_url:
            m = re.match(r"socks5?h?://([^:/]+):(\d+)", socks_url)
            host, port = (m.group(1), int(m.group(2))) if m else ("crisp.bringyour.com", 7117)
        else:
            host, port = "crisp.bringyour.com", 7117
        proxy = f"socks5h://{auth_token}:x@{host}:{port}"
        time.sleep(3)
        e1 = exit_via_proxy(proxy)
        if e1:
            print(f"exit1: ip={e1.get('query')} country={e1.get('country')} region={e1.get('regionName')} city={e1.get('city')} isp={e1.get('isp')} as={e1.get('as')} proxy={e1.get('proxy')} hosting={e1.get('hosting')}", flush=True)
        ok, reason = accept(e1)
        if ok:
            time.sleep(5)
            e2 = exit_via_proxy(proxy)
            if e2:
                print(f"exit2: ip={e2.get('query')} city={e2.get('city')} isp={e2.get('isp')} proxy={e2.get('proxy')} hosting={e2.get('hosting')}", flush=True)
            if e2 and e2.get("query") == e1.get("query"):
                kept = {"auth_token": auth_token, "host": host, "port": port, "exit": e1, "provider_client_id": provider.get("client_id"), "created_client_id": created_id}
                json.dump(kept, open("/tmp/ur-kept.json", "w"))
                # 复验
                env = {k: v for k, v in os.environ.items() if k.lower() not in ("http_proxy", "https_proxy", "all_proxy")}
                for label, url in [("generate_204", "https://www.google.com/generate_204"), ("x.com", "https://x.com/")]:
                    r = subprocess.run(["curl", "-s", "-o", "/dev/null", "-w", "%{http_code} time=%{time_total}s", "-m", "25", "--proxy", proxy, url], capture_output=True, text=True, timeout=35, env=env)
                    print(f"{label}: {r.stdout.strip()}", flush=True)
                r = subprocess.run(["curl", "-s", "-o", "/dev/null", "-w", "%{http_code} time=%{time_total}s size=%{size_download}", "-m", "30", "--proxy", proxy, "https://speed.cloudflare.com/__down?bytes=1000000"], capture_output=True, text=True, timeout=40, env=env)
                print(f"speed 1MB: {r.stdout.strip()}", flush=True)
                txt, xj, cy = write_deliverables(kept)
                print(f"\n*** KEEP *** exit={e1.get('query')} city={e1.get('city')} isp={e1.get('isp')}", flush=True)
                print(f"FILES: {txt} | {xj} | {cy}", flush=True)
                return 0
            print("exit changed on re-check, unstable -> delete", flush=True)
        else:
            print(f"REJECT: {reason}", flush=True)
        remove_client(created_id)
        print("removed failed proxy", flush=True)

    print(f"\n==== SUMMARY: {tried} tried, 0 kept ====", flush=True)
    return 1


if __name__ == "__main__":
    sys.exit(main())
