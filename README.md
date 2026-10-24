# Shadowrocket GFW Sync

将 [Loyalsoldier/clash-rules](https://github.com/Loyalsoldier/clash-rules) 的 GFW 域名列表和 Telegram IP 地址段转换为可通过 URL 直接导入 Shadowrocket 的完整配置，每天自动更新并发布到 GitHub Pages。

## 广告规则集

主配置通过一行规则引用独立广告列表，广告条目不会展开到主配置：

```ini
RULE-SET,https://minipeach.github.io/shadowrocket-gfw-sync/adblock_rule_set.list,REJECT
```

每天从 [Johnshall 的 sr_ad_only.conf](https://johnshall.github.io/Shadowrocket-ADBlock-Rules-Forever/sr_ad_only.conf) 提取 `[Rule]` 中的 REJECT 规则，移除策略字段、规范化 CIDR 并去重，生成 `shadowrocket/adblock_rule_set.list`；主源失败时使用其 GitHub release 分支。此转换不导入 URL Rewrite、MITM 或脚本。

自定义规则放在模板中的广告 `RULE-SET` 之前，可以覆盖误拦截；广告规则集放在 Telegram、GFW、GEOIP 和 FINAL 规则之前。Shadowrocket 需要下载并加载远程规则集，更新时也应更新规则集缓存。任一上游下载或解析失败，本轮不会覆盖现有生成文件。

广告规则原作者为 Moshel 和 Johnshall，来源项目 [Shadowrocket-ADBlock-Rules-Forever](https://github.com/Johnshall/Shadowrocket-ADBlock-Rules-Forever)，按 [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/) 许可提供；转换后的广告列表保留同一许可与署名，许可声明见 `ADBLOCK_UPSTREAM_LICENSE`。

## 特别声明

* 编写本项目主要目的为学习和研究，无法保证项目内容的合法性、准确性、完整性和有效性。
* 本项目涉及的数据由使用的个人或组织自行填写，本项目不对数据内容负责，包括但不限于数据的真实性、准确性、合法性。使用本项目所造成的一切后果，与本项目的所有贡献者无关，由使用的个人或组织完全承担。
* 本项目中涉及的第三方硬件、软件等，与本项目没有任何直接或间接的关系。本项目仅对部署和使用过程进行客观描述，不代表支持使用任何第三方硬件、软件。使用任何第三方硬件、软件，所造成的一切后果由使用的个人或组织承担，与本项目无关。
* 本项目中所有内容只供学习和研究使用，不得将本项目中任何内容用于违反国家/地区/组织等的法律法规或相关规定的其他用途。
* 所有基于本项目源代码，进行的任何修改，为其他个人或组织的自发行为，与本项目没有任何直接或间接的关系，所造成的一切后果亦与本项目无关。
* 所有直接或间接使用本项目的个人和组织，应24小时内完成学习和研究，并及时删除本项目中的所有内容。如对本项目的功能有需求，应自行开发相关功能。
* 本项目保留随时对免责声明进行补充或更改的权利，直接或间接使用本项目内容的个人或组织，视为接受本项目的特别声明。

