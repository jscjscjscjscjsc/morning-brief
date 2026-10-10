#!/usr/bin/env python3
"""Migrate morning-brief's AI layer from the `llm` family to the `model` family.

Every replacement is a literal (no regex) and is asserted to occur exactly once,
so a mismatch stops the run instead of silently corrupting the bundle.

Facts this migration is built on (verified against the OctoSense sources):
  * `llm` family  -> system apps only   (docs/HOST-SERVICES.md:66)
  * `model` family-> any admitted app   (docs/HOST-SERVICES.md:64)
  * model.complete args: {task,input,schema,class,allow_urls} and nothing else
    (apps/ai-providers/host-service/src/complete/mod.rs, Request::from_args)
  * model.complete reply: {output, meta:{class,requested,attempts,usage,budget}}
  * task <= 4096 bytes, input <= 32768 bytes
  * schema must be in the documented subset; pattern/anyOf/oneOf/type-arrays refused
"""
import sys
from pathlib import Path

TARGET = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("my-entry/morning-brief/bundle/main.splash")

EDITS = []


def rep(old, new, why):
    EDITS.append((old, new, why))


NL = "\n"

# ---------------------------------------------------------------- forecast
rep(
    '    host.request("llm.chat", {' + NL
    + '        system: "[编辑部宪法 forecast/" + charter_v("forecast") + "]' + NL
    + "你是科技晨报的主编，现在要做两件事。",
    '    host.request("model.complete", {' + NL
    + '        task: "[编辑部宪法 forecast/" + charter_v("forecast") + "]' + NL
    + "你是科技晨报的主编，现在要做两件事。",
    "forecast: service + system->task",
)
rep(
    '        prompt: "今天是 " + today_text() + "。\\n本期导语：" + intro + "\\n今日入选标题：\\n" + lines + "\\n请给出三条预测，并把本期报到的硬事实记进 claims。"' + NL
    + "        as_json: true" + NL
    + "        temperature: 0.4" + NL
    + "        max_tokens: 900" + NL
    + "        schema: fc_shape" + NL
    + '        label: "brief.forecast"' + NL,
    '        input: "今天是 " + today_text() + "。\\n本期导语：" + intro + "\\n今日入选标题：\\n" + lines + "\\n请给出三条预测，并把本期报到的硬事实记进 claims。"' + NL
    + "        schema: fc_shape" + NL
    + '        class: "strong"' + NL
    + "        allow_urls: true" + NL,
    "forecast: args",
)

# ---------------------------------------------------------------- forecast.check
rep(
    '    host.request("llm.chat", {' + NL
    + '        system: "[编辑部宪法 forecast/" + charter_v("forecast") + "]' + NL
    + "你是晨报主编，正在为自己上一期公开发表的预测对账。",
    '    host.request("model.complete", {' + NL
    + '        task: "[编辑部宪法 forecast/" + charter_v("forecast") + "]' + NL
    + "你是晨报主编，正在为自己上一期公开发表的预测对账。",
    "fc.check: service + system->task",
)
rep(
    '        prompt: "待对账的预测：\\n" + plist + "\\n今天取到的新标题：\\n" + tlist + "\\n请逐条给出 verdict（只能是 hit / miss / open）和 note。"' + NL
    + "        as_json: true" + NL
    + "        temperature: 0" + NL
    + "        max_tokens: 1200" + NL
    + "        schema: fc_check_shape" + NL
    + '        label: "brief.forecast.check"' + NL,
    '        input: "待对账的预测：\\n" + plist + "\\n今天取到的新标题：\\n" + tlist + "\\n请逐条给出 verdict（只能是 hit / miss / open）和 note。"' + NL
    + "        schema: fc_check_shape" + NL
    + '        class: "fast"' + NL
    + "        allow_urls: true" + NL,
    "fc.check: args",
)

# ---------------------------------------------------------------- factcheck
rep(
    '    host.request("llm.chat", {' + NL
    + '        system: "[编辑部宪法 factcheck/" + charter_v("factcheck") + "]' + NL,
    '    host.request("model.complete", {' + NL
    + '        task: "[编辑部宪法 factcheck/" + charter_v("factcheck") + "]' + NL,
    "factcheck: service + system->task",
)
rep(
    '        prompt: "今天是 " + today_text() + "。\\n\\n今天的候选标题（核对它们之间有没有互相矛盾的说法）：\\n" + tlist + "\\n上一期本报记下的硬事实（核对是否被今天推翻）：\\n" + clist + "\\n请给出 clashes 与 fixes 两个数组。"' + NL
    + "        as_json: true" + NL
    + "        temperature: 0" + NL
    + "        max_tokens: 1400" + NL
    + "        schema: fact_shape" + NL
    + '        label: "brief.factcheck"' + NL,
    '        input: "今天是 " + today_text() + "。\\n\\n今天的候选标题（核对它们之间有没有互相矛盾的说法）：\\n" + tlist + "\\n上一期本报记下的硬事实（核对是否被今天推翻）：\\n" + clist + "\\n请给出 clashes 与 fixes 两个数组。"' + NL
    + "        schema: fact_shape" + NL
    + '        class: "strong"' + NL
    + "        allow_urls: true" + NL,
    "factcheck: args",
)

# ---------------------------------------------------------------- agent turn
rep(
    '    let msgs = [{role: "system" content: ag_system()}]' + NL
    + "    for m in ag_msgs { msgs.push(m) }" + NL
    + '    host.request("llm.chat", {messages: msgs as_json: true temperature: 0 max_tokens: 1024 schema: ag_shape label: "brief.agent"}, fn(r){',
    "    let convo = []" + NL
    + "    for m in ag_msgs { convo.push(m) }" + NL
    + "    ag_t0 = time_now()" + NL
    + '    host.request("model.complete", {task: ag_system() input: {context: ag_context() history: convo} schema: ag_shape class: "strong" allow_urls: true}, fn(r){',
    "agent: messages -> task+input (one-shot)",
)
rep(
    '    "注意：search_archive 只查本报档案（本地），不是联网搜索。用户问的是外面的事、你不知道的事，就如实说不知道，不要编。" +' + NL
    + '    "\\n\\n" + ag_context()',
    '    "注意：search_archive 只查本报档案（本地），不是联网搜索。用户问的是外面的事、你不知道的事，就如实说不知道，不要编。"',
    "agent: split static rules out of ag_system (task must stay <=4KB)",
)

# ---------------------------------------------------------------- panel (3 roles)
rep(
    '    host.request("llm.chat", {' + NL
    + "        system: sys" + NL
    + "        prompt: body" + NL
    + "        as_json: true" + NL
    + "        temperature: 0" + NL
    + "        max_tokens: 2048" + NL
    + "        schema: role_shape" + NL
    + '        label: "brief.panel." + id' + NL,
    '    host.request("model.complete", {' + NL
    + "        task: sys" + NL
    + "        input: body" + NL
    + "        schema: role_shape" + NL
    + '        class: "fast"' + NL
    + "        allow_urls: true" + NL,
    "panel: service + args",
)

# ---------------------------------------------------------------- judge
rep(
    '    host.request("llm.chat", {' + NL
    + '        system: "[编辑部宪法 judge/" + charter_v("judge")',
    "    ai_t0 = time_now()" + NL
    + '    host.request("model.complete", {' + NL
    + '        task: "[编辑部宪法 judge/" + charter_v("judge")',
    "judge: service + system->task (+ local timer)",
)
rep(
    "        prompt: ask_text_full" + NL
    + "        as_json: true" + NL
    + "        temperature: 0" + NL
    + "        max_tokens: 2048" + NL
    + "        schema: brief_shape" + NL
    + '        label: "brief.judge"' + NL,
    "        input: ask_text_full" + NL
    + "        schema: brief_shape" + NL
    + '        class: "strong"' + NL
    + "        allow_urls: true" + NL,
    "judge: args",
)

# ---------------------------------------------------------------- one-question ask
rep(
    '    host.request("llm.chat", {' + NL
    + '        system: "你是科技新闻主编。',
    '    host.request("model.complete", {' + NL
    + '        task: "你是科技新闻主编。',
    "ask: service + system->task",
)
rep(
    "        prompt: body" + NL
    + "        as_json: true" + NL
    + "        temperature: 0" + NL
    + "        max_tokens: 512" + NL
    + "        schema: aq_shape" + NL
    + '        label: "brief.ask"' + NL,
    "        input: body" + NL
    + "        schema: aq_shape" + NL
    + '        class: "fast"' + NL
    + "        allow_urls: true" + NL,
    "ask: args",
)

# ---------------------------------------------------------------- interview draft
rep(
    '    host.request("llm.chat", {' + NL
    + '        system: "[编辑部宪法 interview/" + charter_v("interview") + "]' + NL,
    '    host.request("model.complete", {' + NL
    + '        task: "[编辑部宪法 interview/" + charter_v("interview") + "]' + NL,
    "interview: service + system->task",
)
rep(
    "        prompt: body" + NL
    + "        as_json: true" + NL
    + "        temperature: 0" + NL
    + "        max_tokens: 1024" + NL
    + "        schema: iv_shape" + NL
    + '        label: "brief.interview"' + NL,
    "        input: body" + NL
    + "        schema: iv_shape" + NL
    + '        class: "strong"' + NL
    + "        allow_urls: true" + NL,
    "interview: args",
)

# ---------------------------------------------------------------- front-page cover
rep(
    '    host.request("llm.chat", {' + NL
    + '        system: "[编辑部宪法 cover/" + charter_v("cover") + "]' + NL,
    '    host.request("model.complete", {' + NL
    + '        task: "[编辑部宪法 cover/" + charter_v("cover") + "]' + NL,
    "cover: service + system->task",
)
rep(
    '        prompt: "今天是 " + today_text() + "。\\n本期晨报导语：" + intro + "\\n今日入选标题（按重要性排序）：\\n" + lines + "\\n请为这一期设计头版：headline 写一句英文大标题，概括今天最重要的主题；image 写一句英文画面描述，用来画头版主图。"' + NL
    + "        as_json: true" + NL
    + "        temperature: 0" + NL
    + "        max_tokens: 1024" + NL
    + "        schema: cover_shape" + NL
    + '        label: "brief.cover"' + NL,
    '        input: "今天是 " + today_text() + "。\\n本期晨报导语：" + intro + "\\n今日入选标题（按重要性排序）：\\n" + lines + "\\n请为这一期设计头版：headline 写一句英文大标题，概括今天最重要的主题；image 写一句英文画面描述，用来画头版主图。"' + NL
    + "        schema: cover_shape" + NL
    + '        class: "strong"' + NL
    + "        allow_urls: true" + NL,
    "cover: args",
)

# ---------------------------------------------------------------- response fields
rep('        item.model = r.data.model' + NL, '        item.model = "AI"' + NL, "panel row: model id is never visible to an app")
rep(
    "        item.ms = r.data.elapsed_ms" + NL,
    "        item.ms = (time_now() - t0) * 1000" + NL,
    "panel row: local timing (host reports none)",
)
rep(
    '        ag_note = "主编 · " + seconds_text(r.data.elapsed_ms) + " · " + ag_model_text()',
    '        ag_note = "主编 · " + seconds_text((time_now() - ag_t0) * 1000) + " · " + ag_model_text()',
    "agent note: local timing",
)
rep(
    "            ai_model = r.data.model" + NL
    + "            ai_ms = r.data.elapsed_ms" + NL
    + "            ai_tokens = r.data.usage.total_tokens" + NL
    + '            if r.data.reasoning != "" { ai_think = r.data.reasoning }' + NL,
    '            ai_model = "AI 主编"' + NL
    + "            ai_ms = (time_now() - ai_t0) * 1000" + NL
    + "            ai_tokens = model_tokens(r.data)" + NL
    + '            ai_think = ""' + NL,
    "judge: model id hidden, local timing, token usage from meta",
)

# ---------------------------------------------------------------- capability probe
rep(
    '    host.request("llm.status", {}, fn(r){' + NL
    + "        if r.is_ok && r.data.ready {" + NL
    + "            ai_ready = 1" + NL
    + "            ai_model = r.data.model" + NL
    + "        } else {" + NL
    + "            ai_ready = 0" + NL
    + "        }" + NL
    + "        sync_ui()" + NL
    + "    })",
    '    host.request("model.complete", {' + NL
    + '        task: "这是一次可用性探测。只回答一个 JSON 对象，ok 为 true。"' + NL
    + '        input: "probe"' + NL
    + '        schema: {type: "object" required: ["ok"] properties: {ok: {type: "boolean"}}}' + NL
    + '        class: "fast"' + NL
    + "    }, fn(r){" + NL
    + "        if r.is_ok && r.data != nil && r.data.output != nil {" + NL
    + "            ai_ready = 1" + NL
    + '            ai_model = "AI 主编"' + NL
    + "        } else {" + NL
    + "            ai_ready = 0" + NL
    + "        }" + NL
    + "        sync_ui()" + NL
    + "    })",
    "probe: llm.status -> model.complete (a real call proves a provider answers)",
)

# ---------------------------------------------------------------- honesty in copy
rep(
    '    if ai_ready == 0 { return "没接上 AI（这台机器没有配置模型钥匙）。仍可按主题筛选。" }',
    '    if ai_ready == 0 { return "没接上 AI 模型服务（本机没有可用的 AI 供应商配置）。仍可按主题筛选。" }',
    "copy: the app can only report the model service, not a 'key'",
)
rep(
    '    if ai_on { return "AI 主编 · " + ai_model + " · 用时 " + seconds_text(ai_ms) + " · " + ai_tokens + " tokens" }',
    '    if ai_on { return "AI 主编 · 用时 " + seconds_text(ai_ms) + " · " + ai_tokens + " tokens" }',
    "copy: avoid the doubled label now that no model id is reported",
)

# ---------------------------------------------------------------- new globals/helpers
rep(
    "let ai_ms = 0" + NL + "let ai_t0 = 0" + NL,
    "let ai_ms = 0" + NL + "let ai_t0 = 0" + NL + "let ag_t0 = 0" + NL,
    "declare the agent's local timer",
)
rep(
    "fn seconds_text(ms){",
    "// model.complete answers {output, meta:{class,requested,attempts,usage,budget}}." + NL
    + "// The app never sees the provider or the model id, so the token count comes from" + NL
    + "// meta.usage and nothing else is reported." + NL
    + "fn model_tokens(reply){" + NL
    + "    if reply == nil { return 0 }" + NL
    + "    let meta = reply.meta" + NL
    + "    if meta == nil { return 0 }" + NL
    + "    let usage = meta.usage" + NL
    + "    if usage == nil { return 0 }" + NL
    + "    let n = 0" + NL
    + "    if usage.input_tokens != nil { n = n + usage.input_tokens }" + NL
    + "    if usage.output_tokens != nil { n = n + usage.output_tokens }" + NL
    + "    n" + NL
    + "}" + NL
    + NL
    + "fn seconds_text(ms){",
    "add model_tokens helper",
)


def main():
    text = TARGET.read_text(encoding="utf-8")
    before = text
    for i, (old, new, why) in enumerate(EDITS, 1):
        n = text.count(old)
        if n != 1:
            print(f"STOP: edit #{i} ({why}) matched {n} times, expected 1")
            return 1
        text = text.replace(old, new)
    TARGET.write_text(text, encoding="utf-8")
    print(f"applied {len(EDITS)} edits, {len(before)} -> {len(text)} bytes")

    print(NL + "--- verification (all must be 0 except model.complete/r.data.output) ---")
    for probe in [
        "llm.chat", "llm.status", "r.data.data", "r.data.text",
        "r.data.elapsed_ms", "r.data.model", "r.data.usage", "r.data.reasoning",
        "temperature:", "max_tokens:", "as_json:", 'label: "brief', "messages:",
    ]:
        print(f"  {probe:20s}: {text.count(probe)}")
    for probe in ["model.complete", "r.data.output", "allow_urls", "class:"]:
        print(f"  {probe:20s}: {text.count(probe)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
