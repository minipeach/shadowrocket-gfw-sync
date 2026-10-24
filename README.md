# Shadowrocket GFW Sync

将 [Loyalsoldier/clash-rules](https://github.com/Loyalsoldier/clash-rules) 的 GFW 域名列表转换为可通过 URL 直接导入 Shadowrocket 的完整配置，每天自动更新并发布到 GitHub Pages。

## 导入配置

完整配置地址：

```text
https://minipeach.github.io/shadowrocket-gfw-sync/shadowrocket.conf
```

GitHub Raw 备用地址：

```text
https://raw.githubusercontent.com/minipeach/shadowrocket-gfw-sync/main/shadowrocket/shadowrocket.conf
```

在 Shadowrocket 的「配置」页面添加 URL，下载配置并选中使用；首页「全局路由」选择「配置」，并选好自己的代理节点。此项目提供分流配置，节点仍使用你已有的订阅。

服务端更新不会自动替换手机里已经下载的副本。需要在 Shadowrocket 中更新远程配置，或使用客户端支持的自动更新功能。

## 分流策略

规则按顺序匹配：

1. 本地网络直连。
2. `schwab.com`、`schwab.com.cn`、`schwab.com.hk`、`schwab.co.uk` 及其子域名直连。
3. `moomoo.com` 及其子域名走代理。
4. GFW 列表中的域名及其子域名走代理。
5. 中国 IP 和其余流量直连。

完整配置直接包含所有 GFW 域名，不依赖额外的远程规则集。此版本不包含广告过滤、HTTPS 解密或证书配置。

## 自动更新与部署

首次推送 `main`、后续推送、手动触发和每日 23:10 UTC（北京时间 07:10）都会运行工作流。GitHub 定时任务可能排队延迟。

1. 将本项目推送到 GitHub 公开仓库的 `main` 分支。
2. 在仓库 Settings → Pages → Build and deployment 中选择 GitHub Actions。
3. 在 Actions 中手动运行 `Update Shadowrocket GFW rules`，等待 `update` 和 `deploy` 两个任务完成。
4. 用上面的 GitHub Pages 地址导入配置。

工作流先测试并下载上游列表，再生成文件，有变化时提交回仓库，最后发布到 Pages。首次生成的未跟踪文件也会被正确检测并提交。分支保护如果禁止 Actions 直接推送，需要调整为允许此仓库的更新方式。

## 本地生成与自定义

仅依赖 Python 3 标准库：

```bash
python3 -m unittest discover -s tests -v
python3 scripts/update_gfw.py
```

离线验证可以使用 `python3 scripts/update_gfw.py --input /path/to/gfw.txt`。

修改 `shadowrocket_template.conf` 来调整 DNS 或自定义分流；将自定义规则放在 `# INSERT_GFW_RULES` 前面可以覆盖上游规则。生成文件会在下次运行时重建，应修改模板而不是生成结果。

生成文件：

| 文件 | 用途 |
| --- | --- |
| `shadowrocket/shadowrocket.conf` | 推荐：完整配置，直接导入 URL |
| `shadowrocket/gfw_domain_set.list` | 供已有配置中的 `DOMAIN-SET` 引用 |
| `shadowrocket/gfw_rule_set.list` | 供已有配置中的 `RULE-SET` 引用 |

`shadowrocket_example.conf` 保留了远程规则集的接入示例，供维护已有配置时参考。

## 上游来源

域名规则来自 [Loyalsoldier/clash-rules 的 release 分支](https://github.com/Loyalsoldier/clash-rules/tree/release)，主下载地址失败时尝试 jsDelivr。此项目对其进行格式转换；上游 GPL-3.0 许可证副本见 `UPSTREAM_LICENSE`。
