# ISSUE-03 · 能力门拒绝时同步重入 VM，回执走了和正常路径不同的投递方式

**上报对象**：`makepad`（`widgets/src/splash_host.rs` + `widgets/src/splash_policy.rs`）
**核实时的 makepad 工作副本**：`makepad/widgets/src/splash_host.rs`（能力门在 `host.request` 方法体内，约 L275-295）
**严重度**：中高（只在**被拒绝**的请求上触发，但触发时错误信息与真正原因无关，排查成本极高）
**状态**：未修复，本轮已绕过

---

## 一句话

`host.request` 的正常路径是**异步回执**：方法体只把请求和回调塞进队列，回执由另一个入口 `splash_host_respond()` 从外面重新进入 isolate 投递（`splash_host.rs` L31-33、L154-160）。但**能力门拒绝的那条分支**（`splash_policy::service_allowed` 返回 `Err`）却在方法体里**直接同步调用** `vm.call(callback, …)`。同一个「回执」在两个分支上用了两种机制，其中一种是在 VM 自己还在执行 `host.request` 调用帧时重入。观察到这种重入会以 `pop_stack_resolved on empty stack`（`platform/script/src/thread.rs:248`）报错收场——一个和「能力没被授予」毫无关系的错误。

---

## 关键源码

正常路径（`host.request` 方法体尾部）只登记回调并排队，**不调用**：

```rust
let req_id = BRIDGE.with(|b| {
    let mut b = b.borrow_mut();
    b.next_req_id += 1;
    let req_id = b.next_req_id;
    if let Some(callback) = callback {
        b.callbacks.insert((heap_key, req_id), callback);   // 只登记
    }
    ...
    b.queue.push(SplashHostRequest { ... });                 // 只排队
    req_id
});
```

另一处、另一个时机投递（L154 起）：

```rust
pub fn splash_host_respond(...) -> SplashRespondOutcome {
    let callback = BRIDGE.with(|b| b.borrow_mut().callbacks.remove(&(heap_key, req_id)));
    ...
}
```

文件头的自述也把这一点写死了（L31-33）：

> `//! ... answers via [`splash_host_respond`], which re-enters the owning isolate`

**能力门拒绝分支（同一方法体内，直接重入）**：

```rust
if let Err(reason) = crate::splash_policy::service_allowed(heap_key, &service) {
    crate::makepad_draw::log!("splash host: refused {service:?}: {reason}");
    return match callback {
        Some(callback) => {
            let obj = vm.bx.heap.new_object();
            let error = vm.bx.heap.new_string_from_str(&reason);
            let trap = vm.bx.threads.cur().trap.pass();
            vm.bx.heap.set_value(obj, id!(is_ok).into(), false.into(), trap);
            vm.bx.heap.set_value(obj, id!(data).into(), NIL, trap);
            vm.bx.heap.set_value(obj, id!(error).into(), error, trap);
            vm.call(callback.as_object().into(), &[obj.into()]);   // ← 同步重入
            (0.0f64).into()
        }
        None => script_err_invalid_args!(vm.trap(), "{}", reason),
    };
}
```

注释本身说明了设计意图，也正说明两条分支本应等价：

> `// ADR 0002 phase 2: the capability list is checked HERE, not merely reported. A refused request never reaches the host's queue; the app hears {is_ok: false, error} like any other failure, so a well-written app degrades instead of hanging.`

「the app hears … like any other failure」——但实际投递机制和 any other failure 不是同一条。

---

## 观察到的现象

当应用在宿主**没有授予**该能力时发起一个服务请求（本项目触发的是 `llm.speech`，因为商店宿主按官方规定不把 `llm` 族发给商店应用），拿到的不是干净的 `{is_ok: false, error: "…"}`，而是一条 VM 层错误：

```
pop_stack_resolved on empty stack
```

来源：`makepad/platform/script/src/thread.rs:248`

```rust
script_err_stack!(self.trap, "pop_stack_resolved on empty stack")
```

即：**回调确实跑了，但跑完之后 VM 的求值栈回到了一个不该在的状态**。

## 为什么这条分支特别容易踩

1. **这条分支恰恰是升级路径上第一个被碰到的**。开发者通常是先写 `host.request("llm.speech", …)`、本地（能力全开的开发宿主）跑得好好的，然后一放进商店宿主就撞上拒绝分支。第一次与能力门打交道，拿到的却是一条 VM 内部错误，会把人引向完全错误的方向（去查脚本语法、查栈深度、查闭包），而真正要改的只是「这个能力商店应用拿不到，请降级」。
2. **错误信息不可操作**。`pop_stack_resolved on empty stack` 里没有任何 service 名、没有 capability 名、没有 app id。真正有用的那行只在日志里（`log!("splash host: refused {service:?}: {reason}")`），而应用侧拿不到。
3. **两条分支机制不同，等于在热路径旁边留了一条没人走的路**。正常路径有队列、有 `req_id`、有 isolate 死亡清理（`b.callbacks.retain(...)`）——同步重入分支把这些保障全绕开了。

---

## 修复建议

1. **让拒绝分支走同一个投递机制**：不要 `vm.call`，而是把「拒绝」当成一次立刻可回答的请求，交给与 `splash_host_respond` 相同的路径去投递（例如在现有的 host 队列里插一个 `immediate` 结果，由下一帧的 respond 循环取出投递）。这样两条分支的回执时机、栈状态、isolate 死亡处理就完全一致了。
2. 若必须同步，**至少把 `vm.call` 换成一次受保护的调用**，并在调用前后断言/恢复求值栈深度；不要假设方法体内调用用户回调是安全的。
3. **错误文本带上上下文**：把 `service` 与 `reason` 放进 `error` 字段（现在是有的），并保证日志与应用侧看到的是**同一条**信息，便于对照。
4. **补一个回归测试**：在 `splash_host.rs` 的测试里对一个**未授予**的服务发一次 `host.request` 并带回调，断言（a）回调收到 `is_ok == false`，（b）不产生任何 VM 层 trap，（c）随后同 isolate 里再发一次正常请求仍能正常收到回执。目前这套测试里只有 `service_allowed` 的纯函数断言（`splash_policy.rs` L302-313），没有覆盖「拒绝后 VM 是否干净」。

---

## 本轮应用的绕过方式（可复核）

- 应用**刻意不声明** `llm` 能力（官方规定商店应用拿不到，见 `PUBLISHING.md` L163 / L788 与 `HOST-SERVICES.md` L18-22）。
- 语音层改成**先探测再调用**：`vc_probe()` 先问 `llm.speech`，只有宿主明确回答「可用」才继续；不可用就降级成一行状态文字（`vc_say_now()` L1475-1481）。
  注意：本地开发宿主的权限检查比正式商店宽松，只问「宿主有没有」测不出权限问题——这一点已写进项目复盘。
- 语音能力本身作为**上游生态贡献**补进宿主 shell（`my-entry/patches/host-voice.patch`：为 `card-host` 新增整套 `crates/llm-service`，含 `llm.speech / speak / speaking / listen_*`），依据是 `HOST-SERVICES.md` L22「a store app that needs something else needs **a new service in the shells (below), not a workaround in the bundle**」。
