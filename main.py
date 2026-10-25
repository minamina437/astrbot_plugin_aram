# -*- coding: utf-8 -*-
"""英雄联盟「海克斯大乱斗」查询插件。

数据源：ARAMKit（https://aramkit.cn），接口为 data.aramkit.com 的公开 JSON。

功能：
  /海克斯 亚索          英雄胜率 + 推荐强化
  /海克斯 推荐 亚索      同上（别名）
  /海克斯 强化 回归基本功 强化胜率 + 适配英雄
  /海克斯 英雄榜        英雄胜率 Top 10
  /海克斯 强化榜        强化胜率 Top 10
  /海克斯 高分段 亚索    高分段数据（dataset=high）
  /海克斯 帮助          帮助
"""
import time

import aiohttp

from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star, register

try:
    from . import render
except ImportError:  # pragma: no cover
    import render

DATA_BASE = "https://data.aramkit.com"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")

# 缓存 TTL（秒）
TTL_VERSIONS = 24 * 3600
TTL_RESOURCES = 24 * 3600
TTL_RANKINGS = 1800


def pct(x, nd=1):
    return f"{x * 100:.{nd}f}%"


def num(x):
    """把大整数格式化成 万/亿。"""
    if x >= 1e8:
        return f"{x / 1e8:.1f}亿"
    if x >= 1e4:
        return f"{x / 1e4:.0f}万"
    return str(int(x))


HELP = """海克斯大乱斗查询指令：
/海克斯 亚索           英雄胜率 + 推荐强化
/海克斯 推荐 亚索       同上
/海克斯 强化 回归基本功  强化胜率 + 适配英雄
/海克斯 英雄榜          英雄胜率 Top 10
/海克斯 强化榜          强化胜率 Top 10
/海克斯 高分段 亚索      高分段数据
/海克斯 帮助            本说明

英雄名可用：称号(疾风剑豪)/名字(亚索)/英文(yasuo)
强化名可用：中文名或英文
数据源 ARAMKit，版本跟随最新补丁。"""


@register(
    "astrbot_plugin_aram",
    "kokoro",
    "英雄联盟海克斯大乱斗查询：英雄/强化胜率、推荐与适配",
    "1.0.0",
)
class AramQuery(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self._cache = {}          # key -> (expire_ts, value)

    # ---------------- 数据层 ----------------
    async def _fetch_json(self, url: str) -> dict:
        async with aiohttp.ClientSession() as s:
            async with s.get(url, headers={"User-Agent": UA, "Accept": "application/json"},
                             timeout=aiohttp.ClientTimeout(total=30)) as r:
                if r.status != 200:
                    raise RuntimeError(f"数据源返回 HTTP {r.status}")
                return await r.json(content_type=None)

    async def _cached(self, key: str, ttl: int, fetcher):
        now = time.time()
        hit = self._cache.get(key)
        if hit and hit[0] > now:
            return hit[1]
        val = await fetcher()
        self._cache[key] = (now + ttl, val)
        return val

    async def _versions(self):
        async def f():
            d = await self._fetch_json(f"{DATA_BASE}/data/versions.json")
            latest = d["versions"][0]
            return latest["dataPath"], latest["resourcePath"], latest["version"]
        return await self._cached("versions", TTL_VERSIONS, f)

    async def _resources(self, kind: str):
        async def f():
            data_path, res_path, ver = await self._versions()
            url = f"{DATA_BASE}/{res_path}/zh-CN/resources/{kind}.json"
            return await self._fetch_json(url)
        return await self._cached(f"res_{kind}", TTL_RESOURCES, f)

    async def _champions(self):
        return await self._resources("champions")

    async def _augments(self):
        return await self._resources("augments")

    async def _ranking(self, dataset: str, what: str):
        """what: champion-rankings | augment-rankings"""
        async def f():
            data_path, _, ver = await self._versions()
            url = f"{DATA_BASE}/{data_path}/stats/{dataset}/{what}.json"
            return await self._fetch_json(url)
        return await self._cached(f"{dataset}_{what}", TTL_RANKINGS, f)

    async def _detail(self, dataset: str, what: str, cid: int):
        async def f():
            data_path, _, ver = await self._versions()
            url = f"{DATA_BASE}/{data_path}/stats/{dataset}/{what}-details/{cid}.json"
            return await self._fetch_json(url)
        return await self._cached(f"{dataset}_{what}_{cid}", TTL_RANKINGS, f)

    # ---------------- 名字匹配 ----------------
    async def find_champion(self, q: str):
        q = q.strip().lower()
        ch = await self._champions()
        exact = []
        partial = []
        for cid, info in ch.items():
            names = [str(info.get("title", "")), str(info.get("name", "")),
                     str(info.get("slug", "")), str(info.get("riotId", ""))]
            lowered = [n.lower() for n in names]
            if any(n == q for n in lowered):
                exact.append((cid, info))
            elif any(q in n and n for n in lowered):
                partial.append((cid, info))
        pool = exact or partial
        return pool[0] if pool else None

    async def find_augment(self, q: str):
        q = q.strip().lower()
        au = await self._augments()
        exact, partial = [], []
        for aid, info in au.items():
            names = [str(info.get("name", "")), str(info.get("slug", ""))]
            lowered = [n.lower() for n in names]
            if any(n == q for n in lowered):
                exact.append((aid, info))
            elif any(q in n and n for n in lowered):
                partial.append((aid, info))
        pool = exact or partial
        return pool[0] if pool else None

    # ---------------- 格式化 ----------------
    def _fmt_champ(self, cid, info, stats):
        title = info.get("name", "")   # 称号
        name = info.get("title", "")   # 名字
        return (f"{title} {name}".strip() + "\n" +
                f"胜率 {pct(stats.get('winRate', 0))}  "
                f"选取率 {pct(stats.get('pickRate', 0))}  "
                f"梯队 {stats.get('tier', '?')}  样本 {num(stats.get('sampleCount', 0))}")

    def _fmt_aug(self, aid, info, stats):
        return (f"{info.get('name', aid)}\n" +
                f"胜率 {pct(stats.get('winRate', 0))}  "
                f"选取率 {pct(stats.get('pickRate', 0))}  "
                f"梯队 {stats.get('tier', '?')}  样本 {num(stats.get('sampleCount', 0))}")

    # ---------------- 出图 ----------------
    def _emit(self, event: AstrMessageEvent, *, title, subtitle="", hero=None,
              rows=None, footer="", kind_label="", fallback="", section=""):
        """优先发图片卡片，渲染失败则回退纯文本。"""
        try:
            path = render.render(title=title, subtitle=subtitle, hero=hero,
                                 rows=rows, footer=footer, kind_label=kind_label,
                                 section=section)
            if path:
                try:
                    event.track_temporary_local_file(path)
                except Exception:
                    pass
                return event.image_result(path)
            logger.warning("[aram] 渲染不可用，回退文本")
        except Exception as e:
            logger.error(f"[aram] 渲染失败: {e!r}", exc_info=True)
        return event.plain_result(fallback or title)

    # ---------------- 指令 ----------------
    @filter.command("海克斯", alias={"aram", "hx"})
    async def aram(self, event: AstrMessageEvent, a: str = "", b: str = ""):
        logger.info(f"[aram] handler entered, a={a!r} b={b!r}")
        raw = (a + " " + b).strip()
        if not a or a in ("帮助", "help", "?", "？"):
            yield event.plain_result(HELP)
            return

        parts = raw.split()
        dataset = "all"
        # 高分段前缀
        if parts and parts[0] in ("高分段", "高分", "high"):
            dataset = "high"
            parts = parts[1:]
            raw = " ".join(parts)
        if not parts:
            yield event.plain_result(HELP)
            return

        ds_label = "高分段" if dataset == "high" else "全分段"

        try:
            cmd = parts[0]
            rest = " ".join(parts[1:]).strip()

            if cmd in ("英雄榜", "排行", "榜", "top"):
                r = await self._ranking(dataset, "champion-rankings")
                data = r.get("rows", [])[:10]
                ch = await self._champions()
                rows, lines = [], []
                for row in data:
                    info = ch.get(str(row["id"]), {})
                    nm = f"{info.get('name', '')} {info.get('title', '')}".strip() or str(row["id"])
                    rows.append({"rank": row["rank"], "name": nm,
                                 "value": pct(row["winRate"]),
                                 "extra": f"选取 {pct(row['pickRate'])}",
                                 "ratio": row["winRate"], "tier": row.get("tier", "")})
                    lines.append(f"{row['rank']}. {nm}  {pct(row['winRate'])} ({pct(row['pickRate'])})")
                yield self._emit(
                    event,
                    title="海克斯大乱斗 · 英雄胜率 Top10",
                    subtitle=f"{ds_label}数据",
                    rows=rows, kind_label="英雄榜", section="胜率排行",
                    footer="数据源 ARAMKit",
                    fallback="海克斯英雄胜率 Top10\n" + "\n".join(lines))
                return

            if cmd in ("强化榜", "强化排行"):
                r = await self._ranking(dataset, "augment-rankings")
                data = (r.get("all") or [])[:10]
                au = await self._augments()
                rows, lines = [], []
                for row in data:
                    info = au.get(str(row["id"]), {})
                    nm = info.get("name", str(row["id"]))
                    rows.append({"rank": row["rank"], "name": nm,
                                 "value": pct(row["winRate"]),
                                 "extra": f"选取 {pct(row['pickRate'])}",
                                 "ratio": row["winRate"], "tier": row.get("tier", "")})
                    lines.append(f"{row['rank']}. {nm}  {pct(row['winRate'])} ({pct(row['pickRate'])})")
                yield self._emit(
                    event,
                    title="海克斯强化 · 胜率 Top10",
                    subtitle=f"{ds_label}数据",
                    rows=rows, kind_label="强化榜", section="胜率排行",
                    footer="数据源 ARAMKit",
                    fallback="海克斯强化胜率 Top10\n" + "\n".join(lines))
                return

            if cmd in ("强化", "海克斯强化", "augment"):
                if not rest:
                    yield event.plain_result("用法：/海克斯 强化 <强化名>\n例：/海克斯 强化 回归基本功")
                    return
                hit = await self.find_augment(rest)
                if not hit:
                    yield event.plain_result(f"没找到强化「{rest}」，换个名字试试（可用中文名或英文）")
                    return
                aid, info = hit
                detail = await self._detail(dataset, "augment", int(aid))
                aug_stats = detail.get("augment", {})
                champs = detail.get("champions", {})
                champ_rows = champs.get("all") or champs.get("stages", {}).get("all") or []
                ch = await self._champions()

                rows, lines = [], []
                for row in champ_rows[:8]:
                    ci = ch.get(str(row.get("championId") or row.get("id")), {})
                    nm = f"{ci.get('name', '')} {ci.get('title', '')}".strip() or "?"
                    wr = row.get("winRate") or 0
                    rows.append({"rank": row.get("rank", len(rows) + 1), "name": nm,
                                 "value": pct(wr), "extra": "该英雄拿到此强化",
                                 "ratio": wr, "tier": row.get("tier", "")})
                    lines.append(f"  {nm}  {pct(wr)}")

                yield self._emit(
                    event,
                    title=info.get("name", str(aid)),
                    subtitle="海克斯强化",
                    hero={"name": info.get("name", str(aid)),
                          "tag": "",
                          "big": pct(aug_stats.get("winRate", 0)),
                          "sub": f"选取率 {pct(aug_stats.get('pickRate', 0))}\n样本 {num(aug_stats.get('sampleCount', 0))}",
                          "tier": aug_stats.get("tier", "")},
                    rows=rows, kind_label="强化", section="适配英雄",
                    footer="数据源 ARAMKit",
                    fallback="\n".join(lines))
                return

            # 默认：英雄查询（含"推荐"前缀）
            query = rest if cmd in ("推荐", "英雄") and rest else (" ".join(parts))
            query = query.strip()
            if not query:
                yield event.plain_result(HELP)
                return
            hit = await self.find_champion(query)
            if not hit:
                yield event.plain_result(f"没找到英雄「{query}」，换个名字试试（可用称号/名字/英文）")
                return
            cid, info = hit
            detail = await self._detail(dataset, "champion", int(cid))
            stats = detail.get("champion", {}).get("stats", {})
            augs = detail.get("augments", {})
            aug_rows = augs.get("all") or []
            au = await self._augments()

            rows, lines = [], []
            for row in aug_rows[:8]:
                ai = au.get(str(row["id"]), {})
                nm = ai.get("name", str(row["id"]))
                wr = row.get("winRate") or 0
                rows.append({"rank": row.get("rank", len(rows) + 1), "name": nm,
                             "value": pct(wr),
                             "extra": f"选取 {pct(row.get('pickRate', 0))}",
                             "ratio": wr, "tier": row.get("tier", "")})
                lines.append(f"  {nm}  {pct(wr)} (选取{pct(row.get('pickRate', 0))})")

            display = f"{info.get('name', '')} {info.get('title', '')}".strip()
            yield self._emit(
                event,
                title=display or str(cid),
                subtitle=f"{ds_label} · 推荐强化",
                hero={"name": display or str(cid),
                      "tag": "",
                      "big": pct(stats.get("winRate", 0)),
                      "sub": f"选取率 {pct(stats.get('pickRate', 0))}\n样本 {num(stats.get('sampleCount', 0))}",
                      "tier": stats.get("tier", "")},
                rows=rows, kind_label="英雄", section="推荐强化",
                footer="数据源 ARAMKit",
                fallback=self._fmt_champ(cid, info, stats) + "\n" + "\n".join(lines))

        except Exception as e:
            logger.error(f"[aram] 查询失败: {e!r}", exc_info=True)
            yield event.plain_result(f"查询失败：{type(e).__name__}: {e}\n数据源可能暂时不可用，稍后再试。")
