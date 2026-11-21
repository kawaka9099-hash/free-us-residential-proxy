# URnetwork 住宅代理抽取

用 [URnetwork](https://ur.io/)（运营方 BringYour）的众包家宽网络，抽一个**干净、稳定、真实住宅**的出口节点。钉死单个 provider、逐个验出口，抽到干净的美国（或指定国家）住宅节点为止，交付 V2rayN / Xray / Clash 可直接导入的配置。

**免费档专用，绝不付费、绝不绑卡。**

## 一行命令

```bash
python3 scripts/ur-draw-round.py
```

抽到干净节点就停，没抽到如实报。交付文件写到 `~/workspace/your_files/`：

- `urnetwork-us-node.txt` — V2rayN 明文链接
- `urnetwork-us-node-xray.json` — Xray outbound 配置
- `urnetwork-us-clash.yaml` — Clash / Clash Verge 配置

## 为什么是这个方法

URnetwork 的 provider 列表不能全信：2026-11-21 实测，美国速度最高的几个 provider 出口全是同一个机房 IP（GoCodeIT，加拿大蒙特利尔），根本不是美国住宅。所以必须**钉住单个 provider 再验出口**，双 false（`proxy=false` 且 `hosting=false`）+ 真实宽带 ISP + 二次查询 IP 一致，才算干净。

## 快速上手

1. 注册 URnetwork 账号（ur.io，邮箱即可）。
2. 生成一个长期 API key（或拿 JWT，见 `SKILL.md` 的“认证”一节），存入凭据文件（权限 600）。
3. 跑 `python3 scripts/ur-draw-round.py`。

完整方法、API 说明、验收规则、排错和所有已验证的坑，见 **[SKILL.md](SKILL.md)**。

## 节点的性质

节点是一次性的：它只活在那个 provider 在线期间，provider 下线节点就作废，届时重抽一个。节点只用于一次性注册 / 浏览，不走重要账号、不走付款。

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

## 实测

2026-11-21：Sullivans Island, SC → 出口 `76.239.36.24`，Mt. Pleasant, South Carolina，美国，AT&T Enterprises, LLC（AS7018），双 false，复验 IP 一致；`generate_204`=204，`x.com`=200，1MB 下载 6.84s。

## License

MIT
