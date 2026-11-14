// 薄 API 客户端总出口。lib/mock/* 保留为 story/fixture 事实源，业务屏一律走这里。
export {
  API_BASE,
  DEFAULT_API_BASE,
  USER_ID,
  FlintApiError,
  FlintNetworkError,
  apiUrl,
  requestJson,
  requestJsonOrNull,
  requestOk,
  type RequestOpts,
} from "./base";
export { fetchPlazaHot } from "./plaza";
export { fetchCategories } from "./categories";
export {
  lockTarget,
  regenerateSection,
  injectEvidence,
  fileDispute,
  type LockBody,
  type RegenerateBody,
  type InjectBody,
  type InjectResult,
  type DisputeBody,
} from "./interventions";
export { fetchVerdict, fetchJobSnapshot, jobEventsUrl, submitAnalysis } from "./gate";
export {
  fetchBlocks,
  fetchDeliverableMeta,
  renderDeliverable,
  renderUrl,
  type RenderFmt,
} from "./deliverables";
export {
  createCombo,
  fetchEvidenceCards,
  fetchProjectTopics,
  fetchTopic,
} from "./workbench";
