# mcd/data — MCP 真实数据存档

这里存的是**从 MCP 实际抓回来的数据**，不是编的。目的是：现在用静态文件跑 Demo，将来接真接口时只换数据源，不动上层逻辑。

## 目录

```
data/
├── raw/                        原始抓取，尽量保持接口返回原貌
│   ├── meals-1450713.txt       query-meals · 125 个 SKU 的价格表
│   ├── categories-1450713.json query-meals · 15 个分类 + 每个 SKU 的卖点标签
│   ├── nutrition.txt           list-nutrition-foods · 158 条营养数据
│   ├── coupons.json            available-coupons · 3 张可领券
│   └── stores.json             两门店差异 + 时段规则
├── build_catalog.py            把 raw 合成 catalog
├── catalog.json                结构化全量（程序读）
└── catalog.js                  window.MCD_CATALOG（页面 <script> 直接引）
```

改完 `raw/` 里的东西，跑一次 `python3 data/build_catalog.py` 就会重新生成 `catalog.json` / `catalog.js`。

## 抓取信息

| 项 | 值 |
|---|---|
| 门店 | 1450713 上海黄浦华旭国际大厦 / 1450056 上海食品一店 |
| orderType / beType | 1 / 1（到店自取） |
| 时间 | 2026-10-24 13:31–13:35 |
| 接口 | `query-meals`、`list-nutrition-foods`、`available-coupons` |

## 字段对照：哪些是接口原生，哪些是本地产物

### 顶层的原生字段（名字和接口一致，可直接换源）

| 字段 | 来自 | 说明 |
|---|---|---|
| `code` | query-meals `meals[].code` | 商品编码 |
| `name` | `meals[].name` | |
| `image` | `meals[].image` | 完整 URL |
| `currentPrice` | `meals[].currentPrice` | **字符串转成了 number**，其他完全一致 |
| `originalPrice` | `meals[].originalPrice` | 划线价 |
| `discountType` | `meals[].discountType` | `null` / `促销优惠` / `随单购麦金卡优惠` |
| `canWithOrder` | `meals[].canWithOrder` | 能否随单购麦金卡 |
| `withOrder` | `meals[].withOrder` | `{membershipCode:"106", specId:"880"}`，只有随单购商品才有 |
| `categories` | `categories[].name` | 该 SKU 所属分类，可能多个 |
| `tags` | `categories[].meals[].tags` | 卖点标签，合并去重（如 `全球爆款`、`人气`、`上新`、`100%纯牛肉`） |
| `nutrition` | list-nutrition-foods | `energyKcal`/`protein`/`fat`/`carbohydrate`/`sodium`/`calcium`/`energyKj` |

### `_d` 里的派生字段（本地算的，接口没有）

| 字段 | 含义 | 怎么来 |
|---|---|---|
| `role` | `main`/`side`/`drink`/`extra` | 分类表 + 名称关键词规则 |
| `kind` | `single`/`combo` | 名称含「套餐/件套/双人餐/拼盘/随心选」即 combo |
| `usable` | 能否进推荐池 | 食物 且 有 role 且 是单品 且 有营养 |
| `saveAmount` | 立省金额 | `originalPrice − currentPrice` |
| `saveKind` | `bare`/`conditional`/`none` | `discountType` 含「随单购」即 conditional |
| `priceIfNoCard` | 不买卡时的实付 | conditional 的话就是 `originalPrice`，因为优惠价必须买卡才生效 |
| `nutritionSource` | `api`/`estimated` | 见下方「已知局限」 |
| `nutritionPredict` | 是否估算 | |

**优惠纯度的语义**（这点容易搞反）：`随单购麦金卡优惠` 的商品，`currentPrice` 是**买卡后**的价格；不买卡按 `originalPrice` 结算。所以板烧四件套标着 ¥28 / 原价 ¥57，那 ¥29 的「立省」是有条件的。

## 数据现状

| 指标 | 数量 |
|---|---|
| 商品总数 | 125 |
| 进推荐池（`usable`） | 65（主品 18 / 小食 16 / 饮料 22 / 加餐 9） |
| 营养来自接口 | 47 |
| 营养为估算 | 18（池内）+ 50（套餐等不进池的） |
| 非食物（周边、酱料） | 7 |
| 带裸省（无条件优惠） | 42 |
| 带条件省（需买卡） | 19 |

## 已知局限（诚实清单）

1. **18 个池内商品的营养是估算的**。`list-nutrition-foods` 里没有龙焰鸡腿堡、心形薯饼、麦当劳奶昔这些新品。这些值是按「同槽位 价格→热量」最小二乘拟合推出来的，标了 `nutritionSource: "estimated"`。示例：牛肉堡单品精选 ¥14 → 228kcal（真实汉堡包 248kcal，误差可接受）；灰焰圆筒 ¥5 → 154kcal（真实圆筒 93kcal，偏高）。
2. **券的 targetCode / couponPrice 是解析出来的**。`available-coupons` 只返回标题和图片，不返回商品编码、券后价、门槛、有效期。三张券里「19.9元王牌炸鸡任选2」标了 `resolved: false` —— 标题没指明具体 SKU，也不确定 19.9 是单份还是两份合计。
3. **售罄是模拟的**。`query-meals` 没有任何库存字段。`stores[].simSoldOut` 是手写的。
4. **时段可售是规则**。夜宵下架三个冰淇淋品属于确定性规则，接口不返回时段可售性。
5. **满减没有接口**。`query-promotions` 只对企业团餐（beType=6）开放，到店/外送查不到满减规则。`calculate-price` 虽然有 `enjoyable.balance`（门槛差额）字段，实测两单都是 `discount:0` 且字段不返回。

## 三张卡的指标口径（recommend.html）

三派各比各的极端单，不是共用同一个基线：

| 派 | 主指标 | 参照单 | 算法 |
|---|---|---|---|
| 满足派 | 满足感 +x% | 最不扛饿的那一单 | 配菜三项打分 `0.65·(热量/中位) + 0.35·√(蛋白/中位)`，除以最低分配菜的得分，再 −1 |
| 省钱派 | 少花 ¥x | 最贵的那一单 | 每槽位取实付最高（含券、含门店价差）拼成整单，减去本卡实付 |
| 低卡派 | 少 x 大卡 | 最热的那一单 | 每槽位取热量最高拼成整单，减去本卡整单热量 |

三个参照单都由当前门店 + 时段的可售商品按槽位取极值拼成，必点项相同 —— 是真实能点出来的组合，不是虚构基线。
满足感只算配菜三件（必点项三张卡完全一样，算进去只会稀释差异）；省钱和低卡是整单口径，含必点项。

## 换成真接口时动哪里

只有一处：`catalog.js` 的 `window.MCD_CATALOG` 换成运行时拉取的结果。

```js
// 现在
<script src="data/catalog.js"></script>

// 将来
const raw = await callMCP('query-meals', {storeCode, orderType:1, beType:1});
window.MCD_CATALOG = adapt(raw);   // adapt() 负责补 _d 派生字段
```

`_d` 的推导逻辑（role / kind / usable / saveAmount / saveKind）需要跟着搬成一个函数，逻辑与 `build_catalog.py` 里「第三遍：派生字段」那段一一对应。
