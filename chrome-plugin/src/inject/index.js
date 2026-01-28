// 监听来自 Overlay Script 的消息
window.addEventListener('message', function(event) {
  // 安全校验：只接受来自我们插件的消息
  if (event.source !== window || !event.data) {
    return;
  }

  if (event.data.type === 'FASTFLOW_RENDER') {
    const { nodes, edges } = event.data.payload;
    console.log('[FastFlow] 收到渲染请求:', nodes.length, '个节点');

    // 尝试劫持 ReactFlow 实例
    const success = tryInjectToReactFlow(nodes, edges);
    
    // 回复插件：渲染结果
    window.postMessage({ 
      type: 'FASTFLOW_RENDER_RESULT', 
      success: success 
    }, '*');
    return;
  }

  if (event.data.type === 'FASTFLOW_EXPORT') {
    const payload = tryExportFromReactFlow();
    if (payload) {
      window.postMessage({ 
        type: 'FASTFLOW_EXPORT_RESULT', 
        success: true,
        payload
      }, '*');
    } else {
      window.postMessage({ 
        type: 'FASTFLOW_EXPORT_RESULT', 
        success: false,
        message: '未能读取当前编排数据'
      }, '*');
    }
  }
});

function tryInjectToReactFlow(nodes, edges) {
  // 1. 查找 ReactFlow 的 DOM 容器
  // FastGPT 的画布通常包含 'react-flow' 类名
  const flowContainer = document.querySelector('.react-flow');
  if (!flowContainer) {
    console.error('[FastFlow] 未找到 .react-flow 容器');
    return false;
  }

  // 2. 获取 React 内部实例 (Key通常以 __reactFiber 开头)
  const key = Object.keys(flowContainer).find(k => k.startsWith('__reactFiber$'));
  if (!key) {
    console.error('[FastFlow] 无法获取 React Fiber 实例');
    return false;
  }

  try {
    const fiber = flowContainer[key];
    
    // 3. 顺藤摸瓜找到 Store 或 Handler
    // ReactFlow 通常会在 context 或 props 中暴露 setNodes/setEdges
    // 注意：不同版本的 ReactFlow 内部结构可能不同，这里需要一些"探索性"代码
    
    // 方案 A: 模拟 ReactFlow 的 onPaste 行为
    // 如果 FastGPT 绑定了 onPaste，我们构造一个假的 PasteEvent
    const clipboardData = new DataTransfer();
    clipboardData.setData('text/plain', JSON.stringify({ nodes, edges }));
    const pasteEvent = new ClipboardEvent('paste', {
      bubbles: true,
      cancelable: true,
      clipboardData: clipboardData
    });
    flowContainer.dispatchEvent(pasteEvent);
    console.log('[FastFlow] 已分发 Paste 事件');
    return true;

  } catch (e) {
    console.error('[FastFlow] 注入失败:', e);
    return false;
  }
}

// 从 ReactFlow 实例读取当前节点/连线
function tryExportFromReactFlow() {
  const flowContainer = document.querySelector('.react-flow');
  if (!flowContainer) {
    console.error('[FastFlow] 未找到 .react-flow 容器');
    return null;
  }

  const key = Object.keys(flowContainer).find(k => k.startsWith('__reactFiber$'));
  if (!key) {
    console.error('[FastFlow] 无法获取 React Fiber 实例');
    return null;
  }

  const store = findReactFlowStore(flowContainer[key]);
  if (!store || !store.getState) {
    console.error('[FastFlow] 未找到 ReactFlow store');
    return null;
  }

  const state = store.getState();
  const nodes = state.nodes || (state.nodeInternals ? Array.from(state.nodeInternals.values()) : []);
  const edges = state.edges || [];
  return { nodes, edges };
}

// 遍历 Fiber 树寻找 ReactFlow store
function findReactFlowStore(fiberRoot) {
  const visited = new Set();
  const stack = [fiberRoot];

  while (stack.length) {
    const fiber = stack.pop();
    if (!fiber || visited.has(fiber)) continue;
    visited.add(fiber);

    const propsValue = fiber.memoizedProps && fiber.memoizedProps.value;
    if (propsValue && typeof propsValue.getState === 'function') {
      return propsValue;
    }

    const nestedStore = propsValue && propsValue.store;
    if (nestedStore && typeof nestedStore.getState === 'function') {
      return nestedStore;
    }

    const stateNodeStore = fiber.stateNode && fiber.stateNode.store;
    if (stateNodeStore && typeof stateNodeStore.getState === 'function') {
      return stateNodeStore;
    }

    if (fiber.child) stack.push(fiber.child);
    if (fiber.sibling) stack.push(fiber.sibling);
    if (fiber.return) stack.push(fiber.return);
  }

  return null;
}
