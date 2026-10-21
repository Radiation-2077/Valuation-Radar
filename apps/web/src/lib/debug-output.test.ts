import { describe, expect, it } from "vitest";

import { formatCodexJsonl } from "./debug-output";

describe("formatCodexJsonl", () => {
  it("extracts commands, outputs and model messages", () => {
    const raw = [
      JSON.stringify({
        type: "item.started",
        item: { type: "command_execution", command: "python3 scripts.py" },
      }),
      JSON.stringify({
        type: "item.completed",
        item: {
          type: "command_execution",
          exit_code: 0,
          aggregated_output: "A/H premium = 22.3%",
        },
      }),
      JSON.stringify({
        type: "item.completed",
        item: { type: "agent_message", text: "候选估值已生成" },
      }),
      JSON.stringify({
        type: "turn.completed",
        usage: { input_tokens: 100, output_tokens: 20 },
      }),
    ].join("\n");

    const readable = formatCodexJsonl(raw);
    expect(readable).toContain("[执行 Shell]\npython3 scripts.py");
    expect(readable).toContain("[Shell 退出 0]\nA/H premium = 22.3%");
    expect(readable).toContain("[模型消息]\n候选估值已生成");
    expect(readable).toContain("[回合完成] 输入 100 tokens · 输出 20 tokens");
  });

  it("ignores malformed JSONL lines", () => {
    expect(formatCodexJsonl("not-json\n\n")).toBe("");
  });
});
