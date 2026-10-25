# 海克斯大乱斗查询插件

英雄联盟「海克斯大乱斗」数据查询：英雄胜率、强化胜率、推荐强化与适配英雄。

数据源：[ARAMKit](https://aramkit.cn)（数据随补丁每日更新）。

**输出形式：二次元风格图片卡片**（Pillow 本地渲染，不依赖在线 T2I 服务）。
浅粉渐变底 + 小々路立绘（右上角出血）+ 白色圆角卡片 + 玫瑰金点缀。
若渲染异常会自动回退为纯文本。

![预览](preview.png)

### 视觉规格

| 项 | 值 |
|---|---|
| 尺寸 | 760 × 自适应高度 |
| 背景 | 竖向渐变 `#FFFAFD → #FDE8F3` |
| 立绘 | `assets/chara.png`（透明背景 PNG，右上出血 62px） |
| 主色 | 玫瑰红 `#E65892`，辅助粉 `#FFA0C6` |
| 字体 | 内置 AlibabaPuHuiTi（`fonts/`），不依赖系统字体 |
| 梯队色 | S 金 / A 绿 / B 蓝 |

---

## 指令

| 指令 | 作用 | 示例 |
|---|---|---|
| `/海克斯 亚索` | 英雄胜率 + 推荐强化 | `/海克斯 疾风剑豪` |
| `/海克斯 推荐 亚索` | 同上 | |
| `/海克斯 强化 回归基本功` | 强化胜率 + 适配英雄 | |
| `/海克斯 英雄榜` | 英雄胜率 Top 10 | |
| `/海克斯 强化榜` | 强化胜率 Top 10 | |
| `/海克斯 高分段 亚索` | 高分段数据 | |
| `/海克斯 帮助` | 帮助 | |

别名：`/aram`、`/hx`

### 名字匹配

- 英雄：称号（疾风剑豪）/ 名字（亚索）/ 英文（yasuo）均可
- 强化：中文名（回归基本功）/ 英文（back-to-basics）均可

---

## 示例输出

```
疾风剑豪 亚索
胜率 58.5%  选取率 11.5%  梯队 S  样本 173万

推荐强化 Top5：
  鼓声暴起 低音轰鸣  66.9% (选取12.8%)
  秘术冲拳  65.2% (选取...)
  ...
```

---

## 数据接口

| 数据 | 地址 |
|---|---|
| 版本 | `https://data.aramkit.com/data/versions.json` |
| 英雄胜率 | `{dataPath}/stats/{all\|high}/champion-rankings.json` |
| 强化胜率 | `{dataPath}/stats/{all\|high}/augment-rankings.json` |
| 英雄详情（推荐强化） | `{dataPath}/stats/{all\|high}/champion-details/{id}.json` |
| 强化详情（适配英雄） | `{dataPath}/stats/{all\|high}/augment-details/{id}.json` |
| 名字映射 | `{resourcePath}/zh-CN/resources/{champions\|augments}.json` |

`dataPath` / `resourcePath` 从 `versions.json` 动态获取，插件会自动跟随最新补丁。

> 注意：接口要求带浏览器 User-Agent，否则会被 Cloudflare 拦截（HTTP 403）。

---

## 缓存策略

| 数据 | TTL |
|---|---|
| 版本 / 名字映射 | 24 小时 |
| 胜率 / 排行 | 30 分钟 |

重启插件后缓存清空。

---

## 故障排查

- 返回「数据源返回 HTTP 4xx」→ 检查服务器能否访问 `data.aramkit.com`
- 返回「没找到英雄」→ 确认名字正确（可用英文 slug）
- 数据为空 → 等待 ARAMKit 更新补丁数据

---

## 版本

| 版本 | 说明 |
|---|---|
| 1.0.0 | 初始版本：英雄/强化胜率、推荐与适配 |
