---
name: urnetwork-residential-proxy
description: 用 URnetwork（ur.io，运营方 BringYour）抽一个纯净的住宅（家宽）出口节点。钉死单个 provider、逐个验出口，抽到干净的美国（或指定国家）住宅节点为止，交付 V2rayN / Xray / Clash 可直接导入的配置。免费档专用，绝不付费。
---

# URnetwork 住宅代理抽取

用 URnetwork 的众包家宽网络，抽一个**干净、稳定、真实住宅**的出口节点。核心是“钉住单个 provider + 逐个验出口”，而不是相信 provider 列表里写的位置。

适用场景：需要一个真实住宅 IP 做一次性注册、浏览、测试（例如微软 Outlook 注册、Muse 注册等对机房 IP 风控很严的场景）。不适用：重要账号、付款、长期固定出口、流媒体解锁。

## 这是什么

- **URnetwork（ur.io，运营方 BringYour）**：众包住宅代理网络。流量走社区用户提供的家宽出口，不是机房。节点是一台真实家庭宽带设备，IP 属于 AT&T、Google Fiber 这类宽带运营商。
- **免费档**：每天 30 GiB 流量，邮箱注册即可，不绑卡、不要手机号。
- **免费档限制**：同时最多 5 个活跃代理；新建最多 5 个/分钟。超过会报限额，立刻停。
- **免费档给 HTTPS 代理**；SOCKS / WireGuard 在文档和对照表里标为 Pro 专属，但实测免费档 SOCKS 照常可用（见“已验证的坑”）。
- **只用免费档，绝不付费、绝不绑卡。**

## 快速开始（一行命令）

```bash
python3 scripts/ur-draw-round.py
```

这条命令把下面整套流程跑完：验凭据 → 拉 provider → 抽一轮（最多 5 个）→ 验出口 → 删失败的 → 留下干净的 → 写交付文件。抽到就停，没抽到如实报。

```bash
python3 scripts/ur-draw-round.py --dry-run   # 只验凭据、列 provider，不建代理
python3 scripts/ur-draw-round.py --tries 3   # 一轮最多试 3 个（默认 5）
```

交付文件写到 `~/workspace/your_files/`（或脚本里 `OUT_DIR` 指定的目录）：

| 文件 | 用途 |
|---|---|
| `urnetwork-us-node.txt` | V2rayN 明文链接，可直接导入 |
| `urnetwork-us-node-xray.json` | Xray outbound 配置 |
| `urnetwork-us-clash.yaml` | Clash / Clash Verge 配置，可直接导入 |

## 前置条件

- Python 3（标准库即可，脚本不依赖第三方包）+ `curl`。
- 一个 URnetwork 账号（ur.io，邮箱注册）。
- 凭据（二选一，见“认证”）。脚本自动读取，优先 API key，其次 JWT。
- 能访问 `https://api.bringyour.com`。如果本机 DNS 会返回假 IP（例如沙箱返回 `198.18.x.x`），走 HTTP 代理或 DoH 校验。

## 认证

API 基址：`https://api.bringyour.com`。所有请求 `Content-Type: application/json`，请求头 `Authorization: Bearer <token>`。

### 方式 A：长期 API key（推荐）

登录后调一次接口生成，长期有效，适合打包成“一键抽一轮”：

```bash
curl -X POST https://api.bringyour.com/account/api-key \
  -H "Authorization: Bearer <JWT>" \
  -H "Content-Type: application/json" -d '{}'
# 返回 {"id": "...", "api_key": "urn_..."}
```

把 `api_key`（`urn_` 开头）存入凭据文件，权限 600：

```bash
echo 'urn_...' > ~/workspace/weeny-cli/ur-api-key.txt
chmod 600 ~/workspace/weeny-cli/ur-api-key.txt
```

### 方式 B：JWT（临时）

用户在 https://ur.io/app/account/settings 拿 auth code（一次性），再换 JWT：

```bash
curl -X POST https://api.bringyour.com/auth/code-login \
  -H "Content-Type: application/json" -d '{"auth_code": "..."}'
# 返回 {"by_jwt": "..."}
```

把 JWT 存入 `~/workspace/weeny-cli/ur-jwt.txt`（权限 600）。JWT 会过期，过期就让用户再拿一个 code 换。脚本会在凭据失效时明确报错，不会静默用坏凭据跑。

### 凭据保密

`api_key`、`by_jwt`、`auth_token` 是凭据：

- 只在脚本和配置里用，**绝不打印到聊天、日志、回报里**。
- 回报里不许出现它们原文。
- 凭据文件权限 600，不要提交到公开仓库，不要贴到聊天记录里。

## 抽取流程（核心，七步）

### 1. 取目标国家的 `location_id`

```bash
curl -X POST https://api.bringyour.com/network/find-provider-locations \
  -H "Authorization: Bearer <token>" -H "Content-Type: application/json" \
  -d '{"query": "United States"}'
```

返回的 `locations` 数组里过滤 `location_type == "country"`，取它的 `location_id`。这个值稳定，可存下来复用（脚本存在 `ur-us-locid.txt`）。

### 2. 拉 provider 名单，按速度排序

```bash
curl -X POST https://api.bringyour.com/network/find-providers2 \
  -H "Authorization: Bearer <token>" -H "Content-Type: application/json" \
  -d '{"specs": [{"location_id": "<上一步的 id>"}], "count": 50}'
```

每个 provider 有 `client_id`、`estimated_bytes_per_second`、`location`（`city` / `region` / `country`）。按 `estimated_bytes_per_second` 从高到低排序。

### 3. 优先选真实城市的 provider

优先选 `location.city` 是**真实城市**的 provider（例如 New York、Swanville、Mt. Pleasant），不要只写国家名的通用条目。

原因：速度最高的通用条目可能被污染——2026-11-21 实测，美国速度最高的几个 provider 出口全是同一个机房 IP（见“已验证的坑”）。真实城市的 provider 更可能是真住宅。

### 4. 钉住单个 provider 建代理

```bash
curl -X POST https://api.bringyour.com/network/auth-client \
  -H "Authorization: Bearer <token>" -H "Content-Type: application/json" \
  -d '{"proxy_config": {"initial_device_state": {"location": {"connect_location_id": {"client_id": "<该 provider 的 client_id>"}}}}}'
```

取返回 `proxy_config_result` 里的：

- `auth_token`：代理的用户名（密码固定是 `x`，见“代理地址怎么拼”）。
- `socks_proxy_url` / `https_proxy_url`：代理的 host/port。
- 刚建代理的 `client_id`（在 `proxy_config_result.client_id` 里）。**删代理时要用这个 id，注意不是 provider 的 id。**

### 5. 等 3 秒生效，查出口

```bash
curl http://ip-api.com/json/?fields=status,country,regionName,city,isp,org,as,proxy,hosting,query
```

注意：这条查询要**走代理**发（`curl --proxy socks5h://<auth_token>:x@<host>:<port> ...`），查的是代理的出口，不是你本机的 IP。

### 6. 验收，全部满足才留下

- `proxy=false` 且 `hosting=false`（**双 false**，缺一不可）。
- ISP 是真实宽带运营商（如 AT&T、Google Fiber、Burlington Telecom），不是机房 / 托管商 / 云厂商。
- 城市、ISP、AS 互相吻合，地理信息不自相矛盾；国家必须是目标国家。
- **隔几秒二次查询，出口 IP 与第一次完全一致**（钉住了、稳定）。IP 变了说明没钉住，不能留。

### 7. 不合格就删掉，抽下一个

```bash
curl -X POST https://api.bringyour.com/network/remove-client \
  -H "Authorization: Bearer <token>" -H "Content-Type: application/json" \
  -d '{"client_id": "<刚建代理的 client_id>"}'
```

边抽边删（5 个活跃上限）。**一轮最多试 5 个；5 个全不过就停下来如实回报，不要无限重试。**

## 代理地址怎么拼

返回的 `socks_proxy_url` 只给 host/port，**不带凭据**（见“已验证的坑”）。不要直接用它。

一律自己拼：

```
socks5h://<auth_token>:x@<host>:<port>
```

- host/port 取返回的 `socks_proxy_url` 的 host/port；它为空时用 `crisp.bringyour.com:7117`。
- 密码必须是 `x`（非空）。空密码认证失败。
- 网关 host 常见 `crisp.bringyour.com`、`fireside.bringyour.com`，端口 7117 / 7129 / 7135 / 7153 / 7159 / 7165 / 7171。
- 如果 SOCKS 实测确实连不上，再改走返回的 `https_proxy_url`，按同样的验收规则验出口交付，并在回报中如实说明 SOCKS 未能取得的原因和接口原始返回。

## 留下后的复验

对留下的代理实测并记录：

| 检查 | 期望 |
|---|---|
| `https://www.google.com/generate_204` | 204 |
| `https://x.com/` | 200 |
| 一次小文件测速（例如 1MB） | 记录耗时和速度 |

任一关键项失败视为不稳定，删掉重抽。

## 交付

### V2rayN 链接（明文 `.txt` 文件）

```
socks://<auth_token>:x@<host>:<port>#URnetwork-<CC>-<City>-<ISP>-Clean
```

- host/port 以代理实际返回的 `socks_proxy_url` 为准，没有时用 `crisp.bringyour.com:7117`。
- fragment 里的城市和 ISP 去掉空格及特殊字符再拼（例如 `MtPleasant`、`ATT`），避免导入乱码。
- **不要 base64**：base64 版导入会乱码。
- 注意：网友原版格式密码位是空的（`token:@`），但 2026-11-21 实测空密码 SOCKS 认证失败，密码 `x` 才通。统一用 `x`。

### Xray 配置

```json
{
  "outbounds": [
    {
      "protocol": "socks",
      "settings": {
        "servers": [
          { "address": "<host>", "port": <port>, "users": [{ "user": "<auth_token>", "pass": "x" }] }
        ]
      },
      "tag": "urnetwork-us"
    }
  ]
}
```

### Clash / Clash Verge 配置

```yaml
proxies:
  - name: "URnetwork-US-<City>-<ISP>"
    type: socks5
    server: <host>
    port: <port>
    username: <auth_token>
    password: "x"
    udp: true
```

把这段贴进 Clash 配置的 `proxies:` 列表，或把 `urnetwork-us-clash.yaml` 当作一个配置导入，再在代理组里选这个节点。

### 回报格式

结论先行：抽了几个、中了哪个。给出出口 IP / 城市 / ISP / 双 false 证据 / 实测状态码与速度，未核实的单列。**回报里不许出现 `api_key` 和 `auth_token` 原文。**

示例：

```
中了，第二轮第 1 个就是干净的美国住宅节点。
出口：76.239.36.24，Mt. Pleasant, South Carolina，美国，AT&T Enterprises, LLC（AS7018），proxy=false、hosting=false，双 false。隔 5 秒复查 IP 完全一致。
实测：generate_204 → 204（1.43 秒），x.com → 200（1.62 秒），1MB 下载 6.84 秒（约 1.1 Mbps）。
```

## 已验证的坑（2026-11-21，必读）

1. **返回的 `socks_proxy_url` 只带 host/port、不带凭据**，直接用会 SOCKS 认证失败；空密码也失败。必须自己拼 `socks5h://<auth_token>:x@<host>:<port>`，密码 `x`（非空）才通。
2. **免费档 SOCKS 实测可用**：文档说 SOCKS 是 Pro 专属，但用 `auth_token` 连 crisp/fireside 网关不查套餐、SOCKS 照常可用。必须真调一次接口、真连一次网关，用实测下结论，不许只凭文档拒绝执行。
3. **沙箱（及某些网络）下 Python urllib 读大块分块响应会 `IncompleteRead` 截断**。API 调用一律用 curl，不要用 urllib。ip-api 的**批量**接口会把 `proxy` / `hosting` 返回成 `None`，要用**单个**查询（带 `?fields=`）才拿得到真实的 true/false。
4. **头部 provider 出口可能全是同一个机房 IP**：2026-11-21 实测，美国速度最高的几个 provider 出口全是 `23.246.184.33`（GoCodeIT Inc，加拿大蒙特利尔，AS835，机房/托管商），根本不是美国住宅。所以要优先带真实城市的 provider、必须验出口，不能信 provider 列表里的位置。
5. **沙箱 DNS 可能返回 `198.18.x.x` 假 IP**；URnetwork 网关域名实测解析正常，但一律以实际连通为准。
6. **`GET /network/client-data-caps` 可列出本网络下所有活跃代理**。清理后应为 0 个，用它确认没有孤儿代理残留。注意：该接口在某些网络下会返回 `Embed isn't enabled for this network` 的错误，不代表凭据失效；凭据是否有效以 `find-provider-locations` / `find-providers2` 能不能调通为准。
7. **不要用默认的托管代理**：默认代理会在多个 provider 之间分散连接，出口不固定。必须用 API 钉到单个 provider（`auth-client` + `connect_location_id`），出口才会固定。

## 排错

| 现象 | 原因 / 处理 |
|---|---|
| `auth-client` 返回截断 / 读不到完整 JSON | urllib 的 `IncompleteRead`，改用 curl（见坑 3） |
| SOCKS 连上但认证失败（curl 返回 97 或 407） | 没拼凭据或密码为空。必须 `socks5h://<auth_token>:x@<host>:<port>`，密码 `x` |
| 出口是加拿大 / 机房 ISP / GoCodeIT | provider 列表被污染。删掉，换带真实城市的 provider（见坑 4） |
| 二次查询 IP 变了 | 没钉住或 provider 不稳定。删掉重抽 |
| API 返回 401 / 403 | 凭据过期或无效。JWT 过期就让用户去 ur.io 拿新 auth code 换；API key 无效就重新生成 |
| `client-data-caps` 返回 `Embed isn't enabled` | 该接口在当前网络下不可用，不代表凭据失效，换 `find-provider-locations` 验凭据 |
| 一轮 5 个全不过 | 停下来如实回报，不要无限重试。可能是该时段干净 provider 少，换个时间再抽 |

## 使用约束

- 节点只用于一次性注册 / 浏览，不许走重要账号、不许走付款。
- 节点只活在那个 provider 在线期间，它下线就作废，届时重抽，不要囤。
- 只用免费档，绝不付费、绝不绑卡。
- 一次只抽一轮（最多 5 个），不要并发抽一堆，避免触发限额和浪费配额。

## 平台已知问题（交付时提醒用户一次）

- 2026 年 10 月多次全站中断（数据库过载约 80 小时、磁盘写满累计约 23.5 小时），平台稳定性差。
- 协议和服务端代码没有独立审计（只有 Web/API 和安卓 App 被第三方评估过）。
- 托管代理和浏览器扩展这两条路径没有端到端加密会话，靠的是运营方“不落盘”的纪律。

## 实测记录（2026-11-21）

**成功**：Sullivans Island, SC（速度 7810926）→ 出口 `76.239.36.24`，Mt. Pleasant, South Carolina，美国，AT&T Enterprises, LLC（AS7018），proxy=false、hosting=false，隔 5 秒复验 IP 一致；`generate_204`=204（1.43s）、`x.com`=200（1.62s）、1MB 下载 6.84s（约 1.1 Mbps）。

**失败（第一轮）**：5 个全没过——头部 provider 出口全是 GoCodeIT `23.246.184.33`（加拿大蒙特利尔机房）；另有 2 个 provider 的 SOCKS 网关连不上；1 个中途断了没建上代理。活跃代理已清零。

## 仓库结构

```
.
├── README.md                 # 仓库说明与快速开始
├── SKILL.md                  # 本文件：完整方法说明
├── scripts/
│   └── ur-draw-round.py      # 打包好的一键抽一轮脚本（Python 标准库 + curl）
└── examples/
    ├── node-v2ray.txt        # V2rayN 链接示例（占位符，非真实凭据）
    ├── node-xray.json        # Xray 配置示例
    └── node-clash.yaml       # Clash 配置示例
```
