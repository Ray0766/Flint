// GRAPH-11：力导向**一次性**布局（F12，手写、零依赖）。
//
// 持续 rAF 模拟的力导向图会一直微微地动：用户想点的节点会在指尖底下漂走，
// 而且每一帧都在烧电。摆位置是**一次**动作，摆完就停——不是一个永远在跑的动画。
// 所以本模块是一个**纯函数**：给节点与边，返回位置和它跑了多少轮。
// 它不排帧、不设定时器、不持有状态；要重排就再调一次。
//
// ## 确定性
//
// 初值按下标排在一个圆环上，NEVER 用随机数：随机初值会让同一张图每次打开都换个样子，
// 用户会以为数据变了。同样的输入两次跑出逐字相同的位置（有测试）。
//
// ## 收敛即停（靠冷却，不是靠运气）
//
// 只按「最大位移 < 阈值」停是停不下来的：斥力与引力会把节点推成一个来回摆的极限环，
// 每轮位移都不小——初版就是这么写的，12 个节点跑满 300 轮也没停。
// 加上**冷却**（单步位移上限逐轮线性降到 0，200 轮走完）之后终止就有了保证：
// 位移被压到阈值以下，布局稳在那一刻的形状上。
//
// 冷却在 200 轮走完、上限 300 轮，两者留出差额是有意的：这样「跑满 300 轮」
// 就仍然是一个**真的异常信号**（converged=false），而不是每次都必然发生的常态。
//
// ## 锁定节点不动
//
// 用户手动摆过的位置（GRAPH-04 落盘的那些）传进 pinned，自动布局 NEVER 挪它们——
// 挪走等于把用户的摆放当成噪声。

export const LAYOUT_MAX_ITERATIONS = 300;
const COOLING_ITERATIONS = 200;     // 单步位移上限降到 0 所用的轮数
const CONVERGENCE_EPSILON = 0.01;   // 一轮里最大位移小于它就算稳住了
const IDEAL_EDGE_LENGTH = 120;      // 相连节点的目标距离（像素）
const REPULSION = 40000;            // 斥力系数：让不相连的节点散开
const ATTRACTION = 0.02;            // 引力系数：让相连的节点靠拢
const RING_RADIUS = 200;            // 初值圆环半径
const STEP_LIMIT = 20;              // 单轮单节点位移上限，防一步跳飞

export type LayoutNode = { nodeId: string };
export type LayoutEdge = { fromNodeId: string; toNodeId: string };
export type Point = { x: number; y: number };

export type LayoutOptions = {
  /** 用户摆过的位置：这些节点原地不动 */
  pinned?: Record<string, Point>;
};

export type LayoutResult = {
  positions: Record<string, Point>;
  iterations: number;
  converged: boolean;
};

export function layoutGraph(
  nodes: LayoutNode[],
  edges: LayoutEdge[],
  options: LayoutOptions = {},
): LayoutResult {
  const pinned = options.pinned ?? {};
  const positions: Record<string, Point> = {};
  const count = nodes.length;

  nodes.forEach((node, index) => {
    const fixed = pinned[node.nodeId];
    if (fixed !== undefined) {
      positions[node.nodeId] = { ...fixed };
      return;
    }
    const angle = (2 * Math.PI * index) / Math.max(count, 1);   // 确定性初值
    positions[node.nodeId] = {
      x: RING_RADIUS * Math.cos(angle),
      y: RING_RADIUS * Math.sin(angle),
    };
  });

  // 悬空边跳过：端点不在节点表里就当它不存在，NEVER 让布局崩掉
  const live = edges.filter(
    (e) => positions[e.fromNodeId] !== undefined && positions[e.toNodeId] !== undefined,
  );

  let iterations = 0;
  let converged = false;
  while (iterations < LAYOUT_MAX_ITERATIONS) {
    iterations += 1;
    const force: Record<string, Point> = {};
    for (const node of nodes) force[node.nodeId] = { x: 0, y: 0 };

    for (let i = 0; i < count; i += 1) {
      for (let j = i + 1; j < count; j += 1) {
        const a = nodes[i].nodeId;
        const b = nodes[j].nodeId;
        const dx = positions[a].x - positions[b].x;
        const dy = positions[a].y - positions[b].y;
        const distance = Math.hypot(dx, dy) || 0.01;    // 重合时给一个最小值，防除零
        const push = REPULSION / (distance * distance);
        force[a].x += (dx / distance) * push;
        force[a].y += (dy / distance) * push;
        force[b].x -= (dx / distance) * push;
        force[b].y -= (dy / distance) * push;
      }
    }

    for (const edge of live) {
      const dx = positions[edge.toNodeId].x - positions[edge.fromNodeId].x;
      const dy = positions[edge.toNodeId].y - positions[edge.fromNodeId].y;
      const distance = Math.hypot(dx, dy) || 0.01;
      const pull = (distance - IDEAL_EDGE_LENGTH) * ATTRACTION;
      force[edge.fromNodeId].x += (dx / distance) * pull * distance;
      force[edge.fromNodeId].y += (dy / distance) * pull * distance;
      force[edge.toNodeId].x -= (dx / distance) * pull * distance;
      force[edge.toNodeId].y -= (dy / distance) * pull * distance;
    }

    let maxShift = 0;
    for (const node of nodes) {
      if (pinned[node.nodeId] !== undefined) continue;      // 锁定的不动
      const f = force[node.nodeId];
      const magnitude = Math.hypot(f.x, f.y) || 0.01;
      const temperature =
        STEP_LIMIT * Math.max(0, 1 - iterations / COOLING_ITERATIONS);
      const step = Math.min(magnitude, temperature);
      const dx = (f.x / magnitude) * step;
      const dy = (f.y / magnitude) * step;
      positions[node.nodeId].x += dx;
      positions[node.nodeId].y += dy;
      maxShift = Math.max(maxShift, Math.hypot(dx, dy));
    }

    if (maxShift < CONVERGENCE_EPSILON) {
      converged = true;
      break;                                               // 稳住了就停
    }
  }

  return { positions, iterations, converged };
}
