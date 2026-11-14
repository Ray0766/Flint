// 主题子系统前端客户端（TS-008）：只读主题 + combo 入口 + 选主题发起分析。
// 只读消费 TS-007 端点；combo 创建/发起分析 POST。全离线测试（注入 fetchImpl）。
// hypothesis=人类判断，NEVER 参与 gate（后端 #8 保证）；前端只收集/展示。

export interface TopicEvidence {
  event: string;
  event_date: string; // ISO date（后端给），前端不解析
  citation_id: string;
}

export interface TopicWhyNow {
  claim: string;
  evidences: TopicEvidence[];
  speculative: boolean; // 后端定（evidences 空→true），前端只据实降权展示
}

export interface Topic {
  topic_id: string;
  seed_id: string;
  one_liner: string;
  target_user_tag: string;
  form_factor_tag: string;
  why_now: TopicWhyNow;
  keyword_mapping: Record<string, string[]>;
}

export interface ProjectTopics {
  project_id: string;
  chosen_topic_id: string | null;
  topics: Topic[];
}

export interface ComboResult {
  project_id: string;
  topic_ids: string[];
}

export interface TopicOpts {
  baseUrl?: string;
  fetchImpl?: typeof fetch;
}

export class TopicNotFound extends Error {}

export const COMBO_MIN = 2;
export const COMBO_MAX = 5;

// combo 选卡数硬校验（前端与后端 #2 同口径；后端仍是唯一真相）。
export function comboCountValid(count: number): boolean {
  return count >= COMBO_MIN && count <= COMBO_MAX;
}

// 从 keyword_mapping 派生展示关键词（键+值扁平去重；与后端 gate 适配器同形）。
export function topicKeywords(topic: Topic): string[] {
  const seen = new Set<string>();
  const out: string[] = [];
  for (const [key, expansions] of Object.entries(topic.keyword_mapping)) {
    for (const word of [key, ...expansions]) {
      const w = word.trim();
      if (w && !seen.has(w)) {
        seen.add(w);
        out.push(w);
      }
    }
  }
  return out;
}

export async function fetchTopic(topicId: string, opts: TopicOpts = {}): Promise<Topic> {
  const f = opts.fetchImpl ?? fetch;
  const res = await f(`${opts.baseUrl ?? ""}/topics/${encodeURIComponent(topicId)}`);
  if (res.status === 404) throw new TopicNotFound(topicId);
  if (!res.ok) throw new Error(`topic: HTTP ${res.status}`);
  return ((await res.json()) as { topic: Topic }).topic;
}

export async function fetchProjectTopics(
  projectId: string,
  opts: TopicOpts = {},
): Promise<ProjectTopics> {
  const f = opts.fetchImpl ?? fetch;
  const res = await f(
    `${opts.baseUrl ?? ""}/projects/${encodeURIComponent(projectId)}/topics`,
  );
  if (!res.ok) throw new Error(`project-topics: HTTP ${res.status}`);
  return (await res.json()) as ProjectTopics;
}

// combo 入口：选卡（2~5，允许跨簇）+ 一句话关联假设 → 建 Origin→生成→建 Project。
// 后端创建/生成编排（含真机生成，资源触点）走 demo 路由 pending 通道接线。
export async function createCombo(
  cardIds: string[],
  hypothesis: string,
  opts: TopicOpts = {},
): Promise<ComboResult> {
  if (!comboCountValid(cardIds.length)) {
    throw new Error(`combo card count ${cardIds.length} out of ${COMBO_MIN}~${COMBO_MAX}`);
  }
  if (hypothesis.trim() === "") {
    // `FIX-10`：这句话与后端**逐字相同**（`flint/api/errors.py` 从校验器身上取的那句）。
    // 两处各写一句的后果：同一件事在「还没发出去」与「发出去被拒」两种时机上
    // 说两句话，用户会以为是两个问题。
    //
    // 预检**不删**：它省的是一次注定被拒的往返。
    // 「反正后端会拒，前端别判了」的那一版，用户每打错一次都要等一个来回。
    throw new Error("hypothesis required (non-empty str)");
  }
  const f = opts.fetchImpl ?? fetch;
  const res = await f(`${opts.baseUrl ?? ""}/projects/combo`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ card_ids: cardIds, hypothesis }),
  });
  if (!res.ok) throw new Error(`combo: HTTP ${res.status}`);
  return (await res.json()) as ComboResult;
}

// 选定 Topic → chosen_topic_id → 发起 gate 分析（复用 TS-006 /analysis + topic_id）。
export async function submitTopicAnalysis(
  projectId: string,
  topicId: string,
  budgetCny: number,
  opts: TopicOpts = {},
): Promise<{ job_id: string }> {
  const f = opts.fetchImpl ?? fetch;
  const res = await f(
    `${opts.baseUrl ?? ""}/projects/${encodeURIComponent(projectId)}/analysis`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ topic_id: topicId, budget_cny: budgetCny }),
    },
  );
  if (!res.ok) throw new Error(`analysis: HTTP ${res.status}`);
  return (await res.json()) as { job_id: string };
}
