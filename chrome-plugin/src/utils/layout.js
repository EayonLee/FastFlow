import dagre from 'dagre';
import { Logger } from '@/utils/logger.js';

function applyDagre(graphData) {
  if (!dagre) {
    Logger.warn('Dagre not loaded, skipping layout');
    return graphData;
  }

  const g = new dagre.graphlib.Graph();
  g.setGraph({ rankdir: 'LR', nodesep: 50, ranksep: 80 });
  g.setDefaultEdgeLabel(() => ({}));

  graphData.nodes.forEach(node => {
    g.setNode(node.nodeId, { width: 250, height: 100 });
  });

  graphData.edges.forEach(edge => {
    g.setEdge(edge.source, edge.target);
  });

  dagre.layout(g);

  const nodes = graphData.nodes.map(node => {
    const pos = g.node(node.nodeId);
    return {
      ...node,
      position: {
        x: pos.x - 125,
        y: pos.y - 50
      }
    };
  });

  return { ...graphData, nodes };
}

export const Layout = {
  applyDagre
};
