# 免费美国住宅代理（自动抓取）

自动抓一个**干净的美国住宅家宽**出口节点：锁定单个提供方、逐个验出口，抽到干净的为止，一键输出 V2rayN / Xray / Clash 可直接导入的配置。

**免费档专用，绝不付费、绝不绑卡。**

数据中心 IP 注册账号基本都会被风控拦下来，住宅家宽 IP 才是能用的。这个工具就是帮你自动找到干净的家宽 IP。

## 零基础三步上手

### 第一步：注册 URnetwork 账号

打开 https://ur.io/ ，用邮箱注册一个账号。免费，不绑卡、不要手机号。

### 第二步：拿到 API Key

1. 登录后打开 https://ur.io/app/account/settings ，找到生成 auth code 的地方，生成一个（一次性，用完作废）。
2. 把下面两条命令里的 `你的auth_code` 换成你刚拿到的 code，逐条跑：

```bash
# 换 JWT（有效期较短，过期就重新拿 code 换）
curl -s -X POST https://api.bringyour.com/auth/code-login \
  -H "Content-Type: application/json" \
  -d '{"auth_code": "你的auth_code"}'
# 返回里找 by_jwt，复制下来

# 用 JWT 生成长期 API Key（urn_ 开头，长期有效）
curl -s -X POST https://api.bringyour.com/account/api-key \
  -H "Authorization: Bearer 你的JWT" \
  -H "Content-Type: application/json" -d '{}'
# 返回里找 api_key，复制下来
```

3. 把 API Key 存到文件（脚本会自动读它）：

```bash
echo 'urn_你的API_Key' > ur-api-key.txt
chmod 600 ur-api-key.txt
```

### 第三步：一键抽节点

```bash
python3 scripts/ur-draw-round.py
```

脚本会自己跑完：验凭据 → 拉 provider → 抽一轮（最多 5 个）→ 验出口 → 删失败的 → 留下干净的 → 写交付文件。抽到就停，没抽到如实报。

也可以只看不抽：

```bash
python3 scripts/ur-draw-round.py --dry-run   # 只验凭据、列 provider，不建代理
python3 scripts/ur-draw-round.py --tries 3   # 一轮最多试 3 个（默认 5）
python3 scripts/ur-draw-round.py --start 1   # 跳过速度最高的 1 个 provider，从第 2 个开始抽
```

## 抽到之后怎么用

交付文件默认写到 `~/workspace/your_files/`（或脚本里 `OUT_DIR` 指定的目录）：

| 文件 | 用途 |
|---|---|
| `urnetwork-us-node.txt` | V2rayN 明文链接，可直接导入 |
| `urnetwork-us-node-xray.json` | Xray outbound 配置 |
| `urnetwork-us-clash.yaml` | Clash / Clash Verge 配置，可直接导入 |

导入之后，在 Clash 里把代理组选成这个节点，再把出站模式切到全局（或规则），浏览器打开 [ippure.com](https://ippure.com/) 验证：显示美国住宅 IP、IPPure 系数很低，就是通了。

## 验收标准（什么样的节点算干净）

脚本按这个标准留节点，缺一个都不要：

- 出口是美国，`proxy=false` 且 `hosting=false`（双 false）
- ISP 是真实宽带运营商（例如 AT&T、Google Fiber），不是机房 / 托管
- 隔几秒再查一次，出口 IP 不变（稳定、不轮换）

## 为什么必须验出口

URnetwork 的 provider 列表不能全信。2026-11-21 实测：美国速度最高的几个 provider，出口全是同一个机房 IP（GoCodeIT，加拿大蒙特利尔），根本不是美国住宅。所以必须钉住单个 provider 再验出口，不能只看列表。

## 注意事项

- **节点是一次性的**：它只活在那个 provider 在线期间，provider 下线节点就作废，届时重抽一个，不要囤。
- **只用于一次性注册 / 浏览**，不走重要账号、不走付款。
- **只用免费档**，绝不付费、绝不绑卡。免费档每天 30 GiB，同时最多 5 个活跃代理。
- **每次重抽都会换端口和账号**：抽到新节点后，一定要用最新生成的配置文件，旧文件直接作废。
- 平台稳定性一般（2026 年 10 月多次全站中断），抽不到干净节点就换个时间再抽，不要无限重试。

## 完整方法

完整方法、API 说明、验收规则、排错和所有已验证的坑，见 **[SKILL.md](SKILL.md)**。

## 实测

2026-11-21：Sullivans Island, SC → 出口 `76.239.36.24`，Mt. Pleasant, South Carolina，美国，AT&T Enterprises, LLC（AS7018），双 false，复验 IP 一致；`generate_204`=204，`x.com`=200，1MB 下载 6.84s。

## 仓库结构

```
.
├── README.md                 # 本文件
├── SKILL.md                  # 完整方法说明
├── scripts/
│   └── ur-draw-round.py      # 打包好的一键抽一轮脚本（Python 标准库 + curl）
└── examples/
    ├── node-v2ray.txt        # V2rayN 链接示例（占位符，非真实凭据）
    ├── node-xray.json        # Xray 配置示例
    └── node-clash.yaml       # Clash 配置示例
```

## License

MIT
