# 上游缺陷报告：`regex()` 不支持 `\p{...}`，且失败方式是「静默吞掉调用方」

- **组件**：`makepad/libs/regex`（`regex(pattern, flags)` 内置函数）+ `platform/script/src/mod_regex.rs`
- **影响范围**：任何用内置正则做 Unicode 类匹配的 OctoSense 卡片
- **严重度**：中高（不报错到调用者能处理的位置，而是把整段脚本逻辑吞掉）
- **发现方式**：晨报卡的「真伪核验台」在结果页永久停在「正在判…」，查日志才看到

---

## 1. 症状

卡片里这段代码：

```splash
let c = w.replace(regex("\\p{P}|\\p{S}|\\s", "g"), "")
```

期望把标题里的标点、符号、空白抹掉，得到干净的指纹词。实际表现：

1. 界面上那个功能区**永远停在「正在判…」**，不动、不报错、不降级；
2. 同一函数里排在它后面的代码**一行都没执行**（包括本该发出的 `host.request`）；
3. 应用日志里只有一行：

```
[E] splash:1682972282080:4822:33 - regex compile error: expected escape character, got `p` at position 1
```

四件事同时成立才是最难排查的地方：**没有崩溃、没有 UI 反馈、没有失败回调、没有超时**。

## 2. 根因

`libs/regex/src/parse.rs` 的 `parse_char_escape()`（L354-368）只认三类：

```rust
let c = match self.peek() {
    Some('n') => '\n',
    Some('r') => '\r',
    Some('t') => '\t',
    Some(c) if !c.is_word() => c,          // \. \\ \* 这类「转义标点」
    Some(c) => return Err(...),            // \p \P \A \b 一律到这里
    None => ...
};
```

`p` 是 word 字符，既不等于 `n/r/t`，又不是「非 word 字符」，于是直接 `Err`。
**Perl 风格的 `\p{P}` / `\p{N}` / `\p{Lo}` 完全不存在**（`src/unicode.rs` 里虽然备了
`WORD` / `DIGIT` / `SPACE` 三张表，但只在 `\w` `\d` `\s` 的路径上用到，没有类名查表入口）。

`mod_regex.rs` L45-54 把这个 `Err` 转成 `script_err_invalid_args!`，也就是一个 **script trap**。
trap 会终止当前脚本调用的执行栈，而调用它的位置往往是**定时器回调 / 事件回调 / `on_render`**——
这些位置没有任何 `try` 语义，trap 之后既不冒泡到应用层，也不会被 `host.request` 的失败回调接住。
于是「抛错」在外面看起来就是「那块功能没反应」。

> 补充：`\w` `\d` `\s`（及其大写否定形式）在字符类内外都可用，且 `\w` 是**完整 Unicode 词类**
> （`WORD` 表 759 段，含 `U+4E00–U+A48C`）——中文标题用它没问题。
> 也就是说：**能用的够用，只是没人知道不能用 `\p`。**

## 3. 最小复现

```splash
fn go(){
    log("A")
    regex("\\p{P}", "g")          // 这一行 trap
    log("B")                       // 永远不会打印
}
```

日志里只会看到 `A`，加一行 `[E] ... expected escape character, got \`p\``。

## 4. 建议修法（任选，按性价比排序）

1. **让错误可达**：`\p{...}` / `\P{...}` / `\A` / `\b` 这类不支持的转义，
   在 `parse_char_escape` 里给出**明确的**错误文案，例如
   `"\\p{...} is not supported by this engine; use \\w \\d \\s or an explicit character class"`。
   现状的 `expected escape character, got \`p\`` 完全指不到问题在哪。
2. **补上类名查表**：`\p{P}` → `\p{Punctuation}`，用现成的 Unicode 表（`libs/regex/src/unicode.rs`
   已有生成脚本 `make_unicode.py`）加 `PUNCT` / `SYMBOL` / `LETTER` 三张表即可。这是最小改动、
   收益最大的一项——绝大多数 `\p{...}` 用法都是这三类。
3. **让 trap 不吞掉调用栈**：定时器 / 事件回调里 trap 时，除了日志再往应用层推一条
   `Event`（例如 `Event::ScriptTrap{line, col, msg}`）。卡片就能自己决定「降级并显示原因」，
   而不是留一块死界面。这一条对**所有**脚本 API 都成立，不只是正则。

## 5. 我们怎么绕过的

`my-entry/morning-brief/bundle/main.splash` 的 `vf_words()` 改成不依赖 `\p` 的写法：

```splash
let c = w.replace(regex("[^\\w]", "g"), "")   // 取反字符类，语义等价于「抹掉标点+符号+空白」
```

取反字符类是支持的（`parse_class` L233-235 有 `^` 分支），`\w` 又是完整 Unicode 词类，
所以中英混排一把过。另外给这段逻辑加了**看门狗**（`vf_watch()`，50 秒），
即使将来这里再出别的岔子，最坏也只是降级成「只用本机证据算分」，不会停在死界面。
