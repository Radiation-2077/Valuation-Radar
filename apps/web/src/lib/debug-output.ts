interface CodexItem {
  type?: string;
  command?: string;
  aggregated_output?: string;
  exit_code?: number | null;
  text?: string;
  message?: string;
}

interface CodexEvent {
  type?: string;
  item?: CodexItem;
  error?: string;
  usage?: {
    input_tokens?: number;
    output_tokens?: number;
  };
}

const MAX_BLOCK_CHARS = 4_000;

export function formatCodexJsonl(raw: string): string {
  const output: string[] = [];
  for (const line of raw.split(/\r?\n/)) {
    if (!line.trim()) continue;
    let event: CodexEvent;
    try {
      event = JSON.parse(line) as CodexEvent;
    } catch {
      continue;
    }
    if (event.type === "item.started" && event.item?.type === "command_execution") {
      output.push(`[执行 Shell]\n${truncate(event.item.command ?? "")}`);
      continue;
    }
    if (event.type === "item.completed" && event.item?.type === "command_execution") {
      const exitCode = event.item.exit_code ?? "?";
      const body = truncate(event.item.aggregated_output?.trim() ?? "无输出");
      output.push(`[Shell 退出 ${exitCode}]\n${body}`);
      continue;
    }
    if (event.type === "item.completed" && event.item?.type === "agent_message") {
      output.push(`[模型消息]\n${truncate(event.item.text ?? event.item.message ?? "")}`);
      continue;
    }
    if (event.type === "turn.completed") {
      const input = event.usage?.input_tokens ?? "?";
      const outputTokens = event.usage?.output_tokens ?? "?";
      output.push(`[回合完成] 输入 ${input} tokens · 输出 ${outputTokens} tokens`);
      continue;
    }
    if (event.type === "turn.failed" || event.error) {
      output.push(`[执行失败]\n${truncate(event.error ?? "未知错误")}`);
    }
  }
  return output.join("\n\n");
}

function truncate(value: string): string {
  if (value.length <= MAX_BLOCK_CHARS) return value;
  return `${value.slice(0, MAX_BLOCK_CHARS)}\n…（内容过长，请切换到原始 JSONL）`;
}
