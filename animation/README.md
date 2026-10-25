# 卡片展开动画 · 需求存档（暂不实现）

> 2026-10-25 记录。当时为了赶时间先不做，`recommend.html` 目前**没有**这套交互。
> 需要时按本文件的方案直接实现，避免重新想一遍。

## 一句话需求

点某张卡片 → 这张卡展开（挤窄另外两张）→ 展开区列出这单的全部明细 → 底部一个「去付款」按钮。
再点一次 / 点另一张 → 收回或切换。

## 展开区要列什么（之前从卡片上删掉、说留给详情页的东西）

1. **逐行明细**：商品名 · 单价 × 数量 · 行小计 · 每件热量/蛋白/脂肪 · 划线价与券后价来源
2. **汇总**：原价合计 / 实付 / 立省 / 总热量 / 总蛋白 / 件数
3. **这单怎么算**：直接用 `tagBlock(tier, p).recon` 的 HTML（三派各自的参照单口径，已经写好）
4. **本派独白**：`pitchOf(tier, p, must)` 的输出（当初从卡片上撤掉的「同样一个薯条…」那段）
5. **这单查了什么**：`query-meals → list-nutrition-foods → calculate-price`，3 次 MCP 调用
6. **去付款按钮**：演示环境只改按钮文案为「已下单 · 演示」并禁用，不伪造支付流程

## 动画方案（按 animate 技能的口径定的，实现时照抄）

**先过闸门**：卡片展开属于「偶发交互」，不是 100+/天，允许标准动画。
**目的**：`preventing a jarring change`（一张卡变宽、另两张让位，不靠动画会像瞬移）+ `state indication`。

**工具**：CSS transition（状态由 class 控制，最便宜的可用方案）。

**属性**（只动这些）：

| 元素 | 属性 | 值 |
|---|---|---|
| `.arena` | `grid-template-columns` | 三列 `1fr` ⇄ 选中列 `2.4fr` + 另两列 `0.8fr` |
| `.detail` | `grid-template-rows` | `0fr` ⇄ `1fr` 折叠（内层 `overflow:hidden`），比 max-height 稳 |
| `.detail` | `opacity` | `0` ⇄ `1` |
| `.card.dimmed` | `opacity` | `1` ⇄ `0.7`（另两张让位时压一点，不做 scale） |

**曲线与时长**：

- 列宽/展开（屏上位移）：`cubic-bezier(0.77, 0, 0.175, 1)`，`320ms`
- 透明度：`ease`，`200ms`
- 不用 `ease-in`；不用 `transition: all`

**打断**：用 transition 不用 keyframes —— 连点两张卡时能从当前值直接改道，不重启。

**必须一起交付的两件事**：

- `prefers-reduced-motion: reduce` → 全部过渡设为 `none`（保留展开结果，只去掉运动）
- 单栏媒体查询（`max-width:1100px`，此时 arena 是 1 列）里把 `grid-template-columns` 的展开规则覆盖回 `1fr`，否则窄屏会硬裂成三列

## 点击命中规则（踩过的坑）

- 卡片级点击要忽略：`.row`、`button`、`input`、`a`、`.qstep`、`.del`，否则展开明细会和「点行看营养」打架
- 商品行已有的 `row.onclick` 要 `stopPropagation()`，不然点行会连带切换整卡展开
- 展开状态存 `state.expanded`（`null | 'satisfy' | 'cheap' | 'fit'`）；`render()` 重建 innerHTML 后要重新套一遍 class，否则洗牌/改人数后展开态丢失

## 涉及位置（当前文件行数会漂，按函数名找）

- `cardHTML()` —— 在 `.lines` 与 `.cfoot` 之间插入 `.detail` 结构，`.cfoot` 加「明细 ▾」按钮
- `bindCards()` —— 绑卡片点击、明细按钮、付款按钮
- `render()` —— 末尾调用 `applyExpanded()`
- CSS —— `.arena`、`.card`、`.detail` 三块，加在「洗牌手感」区前后
