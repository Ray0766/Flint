// FAV-05（前端半）：批量选择 + 批量动作。
//
// 后端是**单事务**（flint/fav/batch.py：全成或全不成 + 报错清单），
// 所以界面 NEVER 在请求返回前就把选中项标成「已入台」——
// 乐观更新会在整体回滚时留下一屏假的成功态。
//
// 失败时把**清单原样摊开**：哪条、为什么。只说「操作失败」等于让用户重试到猜出来为止。

import type { JSX } from "react";
import { useState } from "react";

export type BatchFailure = { favorite_id: string; reason: string };
export type BatchResult =
  | { ok: true; affected: string[] }
  | { ok: false; failures: BatchFailure[] };

export type LibraryBatchProps = {
  favoriteIds: string[];
  /** 提交批量动作；实现由上层注入（NEVER 在组件里发请求） */
  submit: (ids: string[]) => Promise<BatchResult>;
};

export function LibraryBatch({ favoriteIds, submit }: LibraryBatchProps): JSX.Element {
  const [selected, setSelected] = useState<string[]>([]);
  const [result, setResult] = useState<BatchResult | null>(null);
  const [pending, setPending] = useState(false);

  const toggle = (id: string) =>
    setSelected((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]));

  return (
    <div data-testid="library-batch">
      {favoriteIds.map((id) => (
        <label key={id}>
          <input
            type="checkbox"
            data-testid={`batch-select-${id}`}
            checked={selected.includes(id)}
            onChange={() => toggle(id)}
          />
        </label>
      ))}
      <button
        type="button"
        data-testid="batch-submit"
        disabled={selected.length === 0 || pending}
        onClick={() => {
          setPending(true);
          void submit(selected)
            .then(setResult)
            .finally(() => setPending(false));
        }}
      />
      {result?.ok === true ? (
        <span data-testid="batch-ok" data-affected={result.affected.length} />
      ) : null}
      {result?.ok === false ? (
        <ul data-testid="batch-failures">
          {result.failures.map((f) => (
            <li key={f.favorite_id} data-testid={`batch-failure-${f.favorite_id}`}>
              {f.reason}
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}
