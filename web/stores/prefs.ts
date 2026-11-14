// I18N-06-b：语言/地区偏好的前端 store。
//
// **服务端是唯一真相**（I18N-06-a：flint/profile/prefs.py）。
// 本 store 只是一份**内存缓存**：进程内共享、刷新即弃。
//
// NEVER 读写 localStorage / sessionStorage / cookie —— 存在浏览器里意味着
// 换台设备就变了：用户在手机上看到中文、在电脑上看到英文，而他从没改过设置。
// 「跨设备一致」不是附加功能，它就是「服务端为真相」的可观测形式。

export type Prefs = { lang: "zh" | "en"; region: string };

export const DEFAULT_PREFS: Prefs = { lang: "zh", region: "CN" };

type Listener = (prefs: Prefs) => void;

let current: Prefs = DEFAULT_PREFS;
const listeners = new Set<Listener>();

/** 读缓存。**未拉取前是默认值**，NEVER 是「空」——空会让界面闪一下没有语言的状态。 */
export function getPrefs(): Prefs {
  return current;
}

/** 用服务端回值刷新缓存。**只接受服务端来的值**，不接受本地推断。 */
export function hydrateFromServer(prefs: Prefs): Prefs {
  current = { ...prefs };
  for (const listener of listeners) listener(current);
  return current;
}

/**
 * 提交修改：**先写服务端，服务端回什么就是什么**。
 *
 * NEVER 先改本地再异步同步（乐观更新）——那会在请求失败时留下一个
 * 「界面已经变了、服务端没变」的状态，而用户以为已经保存。
 */
export async function savePrefs(
  patch: Partial<Prefs>,
  put: (patch: Partial<Prefs>) => Promise<Prefs>,
): Promise<Prefs> {
  const confirmed = await put(patch);
  return hydrateFromServer(confirmed);
}

export function subscribe(listener: Listener): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

/** 测试用：把缓存复位到默认值。 */
export function __resetPrefs(): void {
  current = DEFAULT_PREFS;
  listeners.clear();
}
