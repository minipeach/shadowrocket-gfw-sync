# Shadowrocket GFW Sync

将 [Loyalsoldier/clash-rules](https://github.com/Loyalsoldier/clash-rules) 的 GFW 域名列表和 Telegram IP 地址段转换为可通过 URL 直接导入 Shadowrocket 的完整配置，每天自动更新并发布到 GitHub Pages。

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
4. Telegram 的 IPv4/IPv6 地址段走代理（`no-resolve`）。
5. GFW 列表中的域名及其子域名走代理。
6. 中国 IP 和其余流量直连。

完整配置直接包含所有 GFW 域名和 Telegram IP 地址段，不依赖额外的远程规则集。保留原来的 `ipv6 = false` 默认设置；IPv6 分流规则也已生成，启用 IPv6 后可使用。此版本不包含广告过滤、HTTPS 解密或证书配置。

## 仓库设为私有的影响

| 功能 | 私有仓库的影响 |
| --- | --- |
| 定时同步规则 | Actions 支持私有仓库；需要保持 Actions 和写入权限可用，并留意账号的用量限制 |
| Pages 配置下载 | GitHub Free 不支持私有仓库的 Pages，转私有会撤下站点；Pro、Team 等支持私有仓库 Pages 的套餐可继续发布 |
| Raw 备用下载 | 私有仓库的 Raw 文件需要认证，不能再作为免登录的 Shadowrocket 订阅地址 |

私有仓库的 Pages 站点仍可设为公开，因此“源码私有”和“生成配置公开下载”是两件事。若需要免费保持当前 URL 可用，保留公开仓库；若源码必须私有，可以使用支持私有 Pages 的套餐，或另行将生成配置发布到公开仓库/其他托管服务。

规则更新在 `update` 任务中完成，Pages 配置和发布在单独的 `deploy` 任务中完成。即使 Pages 资格或设置导致发布失败，已经成功完成的规则同步提交仍会保留。

参考：[GitHub Pages 支持的套餐](https://docs.github.com/en/pages/getting-started-with-github-pages/what-is-github-pages)、[转为私有的影响](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/managing-repository-settings/setting-repository-visibility)、[Actions 用量](https://docs.github.com/en/billing/concepts/product-billing/github-actions)。

## 自动更新与部署

首次推送 `main`、后续推送、手动触发和每日 23:10 UTC（北京时间 07:10）都会运行工作流。GitHub 定时任务可能排队延迟。

1. 将本项目推送到 GitHub 公开仓库的 `main` 分支。
2. 在仓库 Settings → Pages → Build and deployment 中选择 GitHub Actions。
3. 在 Actions 中手动运行 `Update Shadowrocket GFW rules`，等待 `update` 和 `deploy` 两个任务完成。
4. 用上面的 GitHub Pages 地址导入配置。

工作流先测试并下载两份上游列表，再生成文件，有变化时提交回仓库，最后发布到 Pages。首次生成的未跟踪文件也会被正确检测并提交。任一上游无法下载或解析时，本轮不会覆盖已生成的文件。分支保护如果禁止 Actions 直接推送，需要调整为允许此仓库的更新方式。

## 在 GitHub 网页添加自定义规则

1. 打开 [`shadowrocket_template.conf`](https://github.com/minipeach/shadowrocket-gfw-sync/blob/main/shadowrocket_template.conf)，点击铅笔图标编辑。
2. 在 `[Rule]` 下的 `# Custom rules` 区域添加规则，放在 `# INSERT_TELEGRAM_RULES` 和 `# INSERT_GFW_RULES` 两个标记之前，例如：

   ```text
   DOMAIN-SUFFIX,schwab.com,DIRECT
   DOMAIN-SUFFIX,example.com,DIRECT
   DOMAIN-SUFFIX,example.org,PROXY
   ```

3. 点击 Commit changes，提交到 `main`。这会立即触发生成和部署，无需等到第二天。
4. 在 Actions 中确认 `update`、`deploy` 成功，再到 Shadowrocket 更新该远程配置。

`schwab.com` 的直连规则已内置，不需要重复添加。`DOMAIN-SUFFIX` 同时匹配域名本身和子域名；规则从上往下匹配，特定例外要放在较宽泛的规则前面。

应修改模板，避免直接编辑 `shadowrocket/shadowrocket.conf`；生成文件会在同步时重建，模板中的自定义规则则会一直保留。

## 本地生成与自定义

仅依赖 Python 3 标准库：

```bash
python3 -m unittest discover -s tests -v
python3 scripts/update_gfw.py
```

离线验证可以使用 `python3 scripts/update_gfw.py --input /path/to/gfw.txt --telegram-input /path/to/telegramcidr.txt`。

修改 `shadowrocket_template.conf` 来调整 DNS 或自定义分流；将自定义规则放在两个 `# INSERT_...` 标记前面可以覆盖生成的规则。

生成文件：

| 文件 | 用途 |
| --- | --- |
| `shadowrocket/shadowrocket.conf` | 推荐：完整配置，直接导入 URL |
| `shadowrocket/gfw_domain_set.list` | 供已有配置中的 `DOMAIN-SET` 引用 |
| `shadowrocket/gfw_rule_set.list` | 供已有配置中的 `RULE-SET` 引用 |
| `shadowrocket/telegramcidr_rule_set.list` | Telegram IPv4/IPv6 地址段，供已有配置中的 `RULE-SET` 引用 |

`shadowrocket_example.conf` 保留了远程规则集的接入示例，供维护已有配置时参考。

## 上游来源

规则来自 [Loyalsoldier/clash-rules 的 release 分支](https://github.com/Loyalsoldier/clash-rules/tree/release)，主下载地址失败或解析失败时尝试 jsDelivr。此项目对其进行格式转换；上游 GPL-3.0 许可证副本见 `UPSTREAM_LICENSE`。

- GFW 域名：`gfw.txt`
- Telegram 地址段：[GitHub Raw](https://raw.githubusercontent.com/Loyalsoldier/clash-rules/release/telegramcidr.txt) / [jsDelivr 备用](https://cdn.jsdelivr.net/gh/Loyalsoldier/clash-rules@release/telegramcidr.txt)
