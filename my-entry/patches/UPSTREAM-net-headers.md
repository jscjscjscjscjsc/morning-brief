# 上游缺陷报告：`net.http_request` 拒绝「保留头」，但卡片拿不到拒绝原因

- **组件**：`makepad/platform/network/src/blocking_http.rs` + `platform/script/std/src/net.rs`
- **影响范围**：任何想在 `net.HttpRequest.headers` 里设置 `User-Agent` / `Connection` /
  `Accept-Encoding` / `Host` 的 OctoSense 卡片
- **严重度**：中（行为本身合法，坏在**不可发现 + 不可区分**）
- **发现方式**：晨报卡 11 个新闻来源同时「取不到」，两轮排查才定位

---

## 1. 结论先行

**值类型没问题，被拒是因为头的名字进了「保留头」名单。**

我们最初以为 `headers` 的值必须是字符串数组，实测**不是**——裸字符串、字符串数组都能用。
真正的原因在 `blocking_http.rs`：

```rust
// blocking_http.rs L218-222
pub fn header(mut self, name: &str, value: &str) -> Result<Request, Error> {
    validate_header_pair(name, value)?;
    if is_reserved_header(name) {
        return Err(Error::ReservedHeader);      // ← 整条请求作废
    }
    if self.headers.iter().any(|(n, _)| n.eq_ignore_ascii_case(name)) {
        return Err(Error::InvalidHeader);
    }
    ...
}
```

`is_reserved_header()`（L513-532）把下面这些名字（大小写不敏感）全部列为保留：

```
host  content-length  transfer-encoding  connection  user-agent  accept-encoding
expect  te  trailer  upgrade  keep-alive  proxy-connection
proxy-authorization  proxy-authenticate  以及任何 proxy- 前缀
```

命中之后返回 `Error::ReservedHeader`（L104 的文案是 `"reserved request header"`），
请求**根本不发出去**。

## 2. 实测（最小探针，打同一个公开接口 `hn.algolia.com`）

| headers | 结果 |
| --- | --- |
| `{}` | **HTTP 200** |
| `{"User-Agent": "Mozilla/5.0"}`（裸字符串） | **on_error** |
| `{"User-Agent": ["Mozilla/5.0"]}`（字符串数组） | **on_error** |
| `{"X-Probe": "hello"}` | **HTTP 200** |
| `{"Accept-Language": "zh-CN,zh;q=0.9"}` | **HTTP 200** |
| `{"Referer": "https://example.com/"}` | **HTTP 200** |
| `{"Cookie": "a=1"}` | **HTTP 200** |
| `{"Authorization": "Bearer nope"}` | **HTTP 200** |
| `{"Connection": "keep-alive"}` | **on_error** |
| `{"Accept-Encoding": "gzip"}` | **on_error** |
| `{"Host": "hn.algolia.com"}` | **on_error** |

**`Authorization` 能用、`Referer` 能用、`Cookie` 能用**——所以带密钥调外部 API 完全没问题。
不能用的只有上面那批「传输层」头。这一点建议写进 `docs/SCRIPT-API.md`，
否则每个做取数的卡片作者都会撞一次。

## 3. 真正的问题：拒绝不可发现、不可区分

行为合法，但以卡片的视角看，有三处硬伤：

1. **不知道有哪些名字是保留的。**
   错误文案只有 `"reserved request header"`，**不带是哪个头**。
   探针里 11 个请求，日志只告诉我们「失败了」，不告诉我们「因为 User-Agent」。
   我们为这个花了两轮，第一轮还错误地把原因归到「值必须是数组」上。

2. **`on_error` 里拿不到可区分的错误。**
   卡片侧的 `on_error` 收到的是一个不透明的错误值，无法与「DNS 失败 / 超时 / TLS 失败」区分。
   本卡的做法是 `on_error: |_| p.resolve(nil)`——于是「请求头写错」和「网络断了」
   在界面上长得一模一样，都是「这次没取到」。

3. **整条请求作废，而不是忽略那一个头。**
   `User-Agent` 被拒 → 11 个来源全部失败。而 `User-Agent` 恰恰是**最没必要设**的那个
   （宿主已经硬编码 `makepad-network/1.0`，见 L24 / L1468-1469），
   但卡片作者出于「不带 UA 会被风控」的常识往往会去设它。

## 4. 建议修法（按性价比排序）

1. **错误里带上头名**：`Error::ReservedHeader` 改成携带名字，文案变
   `reserved request header: user-agent (the network backend sets this itself)`。
   一行改动，直接把排查时间从两轮降到两轮之内的第一条日志。
   顺便给个正例：`user-agent is set to "makepad-network/1.0" by the backend`。
2. **给一个可查询的名单**：导出 `net.RESERVED_HEADERS`（数组）或
   `net.is_reserved_header(name) -> bool`。卡片就能在**计划页**提前告诉用户
   「这几个头会被宿主接管」，而不是等到失败。
3. **默认忽略而不是失败**：保留头由宿主接管，卡片给的同类头**丢弃并 warning**，
   请求照发。想「失败」的可以加个显式开关（`strict_headers: true`）。
   这一条会改变语义，建议和 1、2 一起，至少先把 1 做了。
4. **补文档**：`docs/SCRIPT-API.md` 的 `net.http_request` 一节列出保留头清单，
   并明确「值可以是字符串，也可以是字符串数组（多值头）」。

## 5. 我们怎么绕过的

`my-entry/morning-brief/bundle/main.splash` 的 `fetch()` 改成**一个自定义头都不带**：

```splash
fn fetch(url){
    // 不带任何自定义请求头：User-Agent / Accept-Encoding 等是宿主保留头，
    // 带上会让整条请求被拒（返回 on_error，且错误信息里看不出是哪个头）。
    fetch_h(url, {})
}
```

好消息是这几个口都不挑 UA：实测 B站热门、抖音热榜在空 UA 下同样 200，
所以「不带请求头」不是妥协，而是这台平台上最可靠的取数形态。
另外把「哪些来源取到、哪些没取到」全部落到界面上（`失败来源：…`），
这样即便再遇到同类拒绝，也不会只剩一块静默的空白。
