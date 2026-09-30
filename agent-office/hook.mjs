#!/usr/bin/env node
// Claude Code hook：把事件精簡後送到 agent-office 伺服器。
// 原則：只觀察、不回傳任何內容給 Claude；伺服器沒開或逾時就安靜結束，永遠 exit 0。
// （第 2 階段才會註冊到 .claude/settings.local.json）
const clip = (s, n) => (typeof s === 'string' ? s.slice(0, n) : undefined);

let buf = '';
process.stdin.on('data', (d) => { buf += d; });
process.stdin.on('end', async () => {
  try {
    const e = JSON.parse(buf);
    const ti = e.tool_input || {};
    const slim = {
      ts: Date.now(),
      session: e.session_id,
      event: e.hook_event_name,
      tool: e.tool_name,
      agent_id: e.agent_id,
      agent_type: e.agent_type,
      prompt: clip(e.prompt, 300),
      input: {
        file_path: ti.file_path,
        command: clip(ti.command, 300),
        query: clip(ti.query, 120),
        url: clip(ti.url, 200),
        description: clip(ti.description, 120),
        subagent_type: ti.subagent_type,
      },
      // 只有 AskUserQuestion 保留回答（用來抓公司名稱與代號），其他工具的輸出一律不送
      answers: e.tool_name === 'AskUserQuestion' ? clip(JSON.stringify(e.tool_response ?? ''), 300) : undefined,
    };
    await fetch('http://127.0.0.1:5180/event', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify(slim),
      signal: AbortSignal.timeout(400),
    });
  } catch { /* 靜默 */ }
  process.exit(0);
});
setTimeout(() => process.exit(0), 1500);
