import type { 
  LineageRawNode, 
  LineageRawEdge, 
  LineageTreeNode, 
  LineageCanvasNode 
} from '../types/navigation';

/**
 * Chuyển danh sách nodes phẳng có parent_id thành cấu trúc cây n-ary cho Tree View
 */
export function buildLineageTree(nodes: LineageRawNode[]): LineageTreeNode[] {
  const nodeMap = new Map<string, LineageTreeNode>();
  const roots: LineageTreeNode[] = [];

  // Tạo map clone với children rỗng
  nodes.forEach(node => {
    nodeMap.set(node.id, { ...node, children: [] });
  });

  // Gắn con vào cha
  nodes.forEach(node => {
    const current = nodeMap.get(node.id)!;
    if (node.parent_id === null || !nodeMap.has(node.parent_id)) {
      roots.push(current);
    } else {
      const parent = nodeMap.get(node.parent_id);
      if (parent) {
        parent.children.push(current);
      } else {
        roots.push(current);
      }
    }
  });

  return roots;
}

/**
 * Tính toán tự động tọa độ Layout X, Y theo cấu trúc phân tầng (Rank / Layered DAG) cho Canvas View
 */
export function computeCanvasLayout(
  nodes: LineageRawNode[],
  edges: LineageRawEdge[]
): {
  canvasNodes: LineageCanvasNode[];
  canvasEdges: { sourceNode: LineageCanvasNode; targetNode: LineageCanvasNode }[];
  width: number;
  height: number;
} {
  const NODE_WIDTH = 220;
  const NODE_HEIGHT = 80;
  const GAP_X = 140;
  const GAP_Y = 50;

  // 1. Phân tầng node (Topological / Level Calculation)
  // Tính bậc vào (in-degree)
  const inDegree = new Map<string, number>();
  const outgoing = new Map<string, string[]>();

  nodes.forEach(n => {
    inDegree.set(n.id, 0);
    outgoing.set(n.id, []);
  });

  edges.forEach(e => {
    inDegree.set(e.target, (inDegree.get(e.target) || 0) + 1);
    outgoing.get(e.source)?.push(e.target);
  });

  // BFS gán level
  const levels = new Map<string, number>();
  const queue: string[] = [];

  nodes.forEach(n => {
    if ((inDegree.get(n.id) || 0) === 0) {
      levels.set(n.id, 0);
      queue.push(n.id);
    }
  });

  while (queue.length > 0) {
    const currId = queue.shift()!;
    const currLevel = levels.get(currId) || 0;
    const children = outgoing.get(currId) || [];

    children.forEach(childId => {
      const existingLevel = levels.get(childId) ?? -1;
      if (currLevel + 1 > existingLevel) {
        levels.set(childId, currLevel + 1);
        queue.push(childId);
      }
    });
  }

  // Nhóm node theo level
  const levelGroups = new Map<number, LineageRawNode[]>();
  nodes.forEach(n => {
    const lvl = levels.get(n.id) || 0;
    if (!levelGroups.has(lvl)) {
      levelGroups.set(lvl, []);
    }
    levelGroups.get(lvl)!.push(n);
  });

  // 2. Tính tọa độ X, Y cho từng node
  const canvasNodeMap = new Map<string, LineageCanvasNode>();
  let maxLevel = 0;
  let maxNodesInLevel = 0;

  const PADDING_LEFT = 40;
  const PADDING_TOP = 60;

  levelGroups.forEach((groupNodes, lvl) => {
    if (lvl > maxLevel) maxLevel = lvl;
    if (groupNodes.length > maxNodesInLevel) maxNodesInLevel = groupNodes.length;

    groupNodes.forEach((node, indexInLevel) => {
      const x = PADDING_LEFT + lvl * (NODE_WIDTH + GAP_X);
      const y = PADDING_TOP + indexInLevel * (NODE_HEIGHT + GAP_Y);

      const canvasNode: LineageCanvasNode = {
        ...node,
        x,
        y,
        width: NODE_WIDTH,
        height: NODE_HEIGHT,
        level: lvl
      };

      canvasNodeMap.set(node.id, canvasNode);
    });
  });

  const canvasNodes = Array.from(canvasNodeMap.values());

  // 3. Kết nối Edges với tọa độ thực tế của Source và Target
  const canvasEdges = edges
    .map(e => {
      const sourceNode = canvasNodeMap.get(e.source);
      const targetNode = canvasNodeMap.get(e.target);
      if (sourceNode && targetNode) {
        return { sourceNode, targetNode };
      }
      return null;
    })
    .filter((e): e is { sourceNode: LineageCanvasNode; targetNode: LineageCanvasNode } => e !== null);

  const totalWidth = PADDING_LEFT * 2 + (maxLevel + 1) * NODE_WIDTH + maxLevel * GAP_X + 100;
  const totalHeight = PADDING_TOP * 2 + maxNodesInLevel * NODE_HEIGHT + (maxNodesInLevel - 1) * GAP_Y + 100;

  return {
    canvasNodes,
    canvasEdges,
    width: Math.max(700, totalWidth),
    height: Math.max(450, totalHeight)
  };
}
