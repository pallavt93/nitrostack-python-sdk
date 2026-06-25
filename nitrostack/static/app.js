// Global State
const appState = {
  connected: false,
  activeTab: 'canvas',
  tools: [],
  resources: [],
  templates: [],
  prompts: [],
  activeNode: null, // currently selected node for detail drawer
  ws: null
};

// DOM Elements
const elements = {
  btnConnect: document.getElementById('btn-connect'),
  connCommand: document.getElementById('conn-command'),
  connScriptSelect: document.getElementById('conn-script-select'),
  connScript: document.getElementById('conn-script'),
  statusBadge: document.getElementById('status-badge'),
  statusText: document.getElementById('status-text'),
  panelTitleText: document.getElementById('panel-title-text'),
  canvasNodes: document.getElementById('canvas-nodes'),
  canvasSvg: document.getElementById('canvas-svg'),
  detailDrawer: document.getElementById('detail-drawer'),
  drawerTitle: document.getElementById('drawer-title'),
  drawerDesc: document.getElementById('drawer-desc'),
  drawerClose: document.getElementById('drawer-close'),
  executionForm: document.getElementById('execution-form'),
  btnExecute: document.getElementById('btn-execute'),
  outputPanel: document.getElementById('output-panel'),
  chatHistory: document.getElementById('chat-history'),
  chatInput: document.getElementById('chat-input'),
  btnChatSend: document.getElementById('btn-chat-send'),
  logsTerminal: document.getElementById('logs-terminal')
};

// Init UI navigation tabs
document.querySelectorAll('.nav-item').forEach(item => {
  item.addEventListener('click', () => {
    const tabName = item.getAttribute('data-tab');
    switchTab(tabName);
  });
});

function switchTab(tabName) {
  appState.activeTab = tabName;
  
  // Update nav menu active item
  document.querySelectorAll('.nav-item').forEach(item => {
    if (item.getAttribute('data-tab') === tabName) {
      item.classList.add('active');
    } else {
      item.classList.remove('active');
    }
  });

  // Display tab content
  document.querySelectorAll('.tab-content').forEach(content => {
    if (content.id === `tab-${tabName}`) {
      content.style.display = tabName === 'chat' ? 'flex' : 'block';
    } else {
      content.style.display = 'none';
    }
  });

  // Update header title
  elements.panelTitleText.innerText = getTabTitle(tabName);
}

function getTabTitle(tab) {
  const titles = {
    canvas: 'App Canvas',
    tools: 'Tools Testing Panel',
    resources: 'Server Resources List',
    prompts: 'Prompt Templates List',
    chat: 'Interactive AI Chat',
    logs: 'RPC JSON-RPC Stream Logs'
  };
  return titles[tab] || 'Dashboard';
}

// Server Connection Handler
elements.btnConnect.addEventListener('click', async () => {
  if (appState.connected) {
    // Disconnect
    elements.btnConnect.innerText = 'Disconnecting...';
    try {
      const res = await fetch('/api/disconnect', { method: 'POST' });
      const data = await res.json();
      if (data.status === 'disconnected') {
        setConnectionState(false);
      }
    } catch (e) {
      console.error(e);
    }
  } else {
    // Connect
    elements.btnConnect.innerText = 'Connecting...';
    const body = {
      command: elements.connCommand.value.trim(),
      script_path: elements.connScript.value.trim()
    };
    try {
      const res = await fetch('/api/connect', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body)
      });
      const data = await res.json();
      if (data.status === 'connected') {
        setConnectionState(true);
      } else {
        alert('Failed to connect to MCP server: ' + data.detail);
        elements.btnConnect.innerText = 'Connect';
      }
    } catch (e) {
      alert('Error connecting: ' + e);
      elements.btnConnect.innerText = 'Connect';
    }
  }
});

function setConnectionState(connected) {
  appState.connected = connected;
  if (connected) {
    elements.statusBadge.classList.add('connected');
    elements.statusText.innerText = 'Connected';
    elements.btnConnect.innerText = 'Disconnect';
    elements.btnConnect.classList.remove('btn-primary');
    elements.btnConnect.classList.add('btn-secondary');
    
    // Connect Logs WebSocket
    connectLogsWebSocket();
    
    // Fetch and populate primitives
    loadServerData();
  } else {
    elements.statusBadge.classList.remove('connected');
    elements.statusText.innerText = 'Disconnected';
    elements.btnConnect.innerText = 'Connect';
    elements.btnConnect.classList.remove('btn-secondary');
    elements.btnConnect.classList.add('btn-primary');
    
    if (appState.ws) {
      appState.ws.close();
      appState.ws = null;
    }
    
    clearCanvas();
  }
}

// WebSocket client connection for real-time RPC logs
function connectLogsWebSocket() {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const url = `${protocol}//${window.location.host}/ws/logs`;
  appState.ws = new WebSocket(url);
  
  appState.ws.onmessage = (event) => {
    appendLog(event.data);
  };
  
  appState.ws.onclose = () => {
    appendLog('SYSTEM: WebSocket logs stream disconnected.');
  };
}

function appendLog(message) {
  const isSend = message.startsWith('--> send');
  const isRecv = message.startsWith('<-- recv');
  const isSystem = message.startsWith('SYSTEM');
  
  let className = 'system';
  if (isSend) className = 'send';
  if (isRecv) className = 'recv';
  
  const entry = document.createElement('div');
  entry.className = `log-entry ${className}`;
  entry.innerText = message;
  
  elements.logsTerminal.appendChild(entry);
  elements.logsTerminal.scrollTop = elements.logsTerminal.scrollHeight;
}

// Fetch primitives from FastAPI backend
async function loadServerData() {
  try {
    const toolsRes = await fetch('/api/tools');
    const toolsData = await toolsRes.json();
    appState.tools = toolsData.tools || [];
    
    const resRes = await fetch('/api/resources');
    const resData = await resRes.json();
    appState.resources = resData.resources || [];
    appState.templates = resData.templates || [];
    
    const promptsRes = await fetch('/api/prompts');
    const promptsData = await promptsRes.json();
    appState.prompts = promptsData.prompts || [];
    
    renderCanvas();
    populateTabLists();
  } catch (e) {
    console.error('Error loading server primitives:', e);
  }
}

// Canvas Visualizer mapping logic
function renderCanvas() {
  clearCanvas();
  
  // Center Coordinate of Container
  const cx = elements.canvasNodes.clientWidth / 2;
  const cy = elements.canvasNodes.clientHeight / 2;
  
  // Create Center Agent Node
  createNodeElement('Agent', 'agent', 'Agent', cx, cy, { name: 'Agent', description: 'NitroStack Core Orchestrating Agent' });

  const primitives = [];
  
  // Gather node details and map colors
  appState.prompts.forEach(p => primitives.push({ name: p.name, type: 'prompt', config: p }));
  appState.tools.forEach(t => primitives.push({ name: t.name, type: 'tool', config: t }));
  appState.resources.forEach(r => primitives.push({ name: r.name, type: 'resource', config: r }));
  appState.templates.forEach(t => primitives.push({ name: t.name, type: 'resource', config: { ...t, uri: t.uriTemplate } }));
  
  if (primitives.length === 0) return;
  
  // Radius of circular node positioning
  const radius = Math.min(cx, cy) * 0.6;
  const angleStep = (2 * Math.PI) / primitives.length;
  
  primitives.forEach((p, index) => {
    const angle = index * angleStep - Math.PI / 2; // start from top
    const x = cx + radius * Math.cos(angle);
    const y = cy + radius * Math.sin(angle);
    
    const shortName = p.name.length > 18 ? p.name.substring(0, 16) + '..' : p.name;
    const nodeId = `${p.type}-${p.name.replace(/[^a-zA-Z0-9]/g, '-')}`;
    
    createNodeElement(nodeId, p.type, shortName, x, y, p.config);
    drawConnectionLine(cx, cy, x, y, nodeId, p.type);
  });
}

function createNodeElement(id, type, name, x, y, config) {
  const node = document.createElement('div');
  node.className = `node ${type}`;
  node.id = id;
  node.style.left = `${x}px`;
  node.style.top = `${y}px`;
  
  // Icon letter
  let icon = 'A';
  if (type === 'tool') icon = 'T';
  if (type === 'resource') icon = 'R';
  if (type === 'prompt') icon = 'P';
  
  node.innerHTML = `
    <div class="node-icon">${icon}</div>
    <div class="node-info">
      <div class="node-name">${name}</div>
      <div class="node-type">${type}</div>
    </div>
  `;
  
  node.addEventListener('click', () => {
    openDrawer(type, config.name || name, config);
  });
  
  elements.canvasNodes.appendChild(node);
}

function drawConnectionLine(x1, y1, x2, y2, targetNodeId, type) {
  const line = document.createElementNS('http://www.w3.org/2000/svg', 'path');
  
  // Draw direct line path
  const d = `M ${x1} ${y1} L ${x2} ${y2}`;
  line.setAttribute('d', d);
  line.setAttribute('class', `connection-line connection-line-${targetNodeId}`);
  
  // Render matching color theme
  let color = 'rgba(255,255,255,0.1)';
  if (type === 'tool') color = 'rgba(6, 182, 212, 0.2)';
  if (type === 'resource') color = 'rgba(59, 130, 246, 0.2)';
  if (type === 'prompt') color = 'rgba(234, 179, 8, 0.2)';
  
  line.setAttribute('stroke', color);
  elements.canvasSvg.appendChild(line);
}

function flashConnection(targetNodeId, type) {
  const line = document.querySelector(`.connection-line-${targetNodeId}`);
  if (line) {
    line.classList.add('active', `active-${type}`);
    setTimeout(() => {
      line.classList.remove('active', `active-${type}`);
    }, 2000);
  }
  
  const node = document.getElementById(targetNodeId);
  if (node) {
    node.style.transform = 'translate(-50%, -50%) scale(1.1)';
    setTimeout(() => {
      node.style.transform = '';
    }, 1000);
  }
}

function clearCanvas() {
  elements.canvasNodes.innerHTML = '';
  elements.canvasSvg.innerHTML = '';
}

// Populate Sidebar Detail Lists in other tabs
function populateTabLists() {
  // Tools testing list
  const toolsList = document.getElementById('tools-list-container');
  toolsList.innerHTML = appState.tools.map(t => createCardMarkup('tool', t.name, t.description)).join('');
  bindCardEvents(toolsList, 'tool', appState.tools);

  // Resources list
  const resourcesList = document.getElementById('resources-list-container');
  const items = [...appState.resources.map(r => ({ name: r.name, desc: r.description, data: r })),
                 ...appState.templates.map(t => ({ name: t.name, desc: `Template: ${t.uriTemplate}`, data: { ...t, uri: t.uriTemplate } }))];
  resourcesList.innerHTML = items.map(i => createCardMarkup('resource', i.name, i.desc)).join('');
  bindCardEvents(resourcesList, 'resource', items.map(i => i.data));

  // Prompts list
  const promptsList = document.getElementById('prompts-list-container');
  promptsList.innerHTML = appState.prompts.map(p => createCardMarkup('prompt', p.name, p.description)).join('');
  bindCardEvents(promptsList, 'prompt', appState.prompts);
}

function createCardMarkup(type, name, desc) {
  return `
    <div class="connection-panel card-${type}" style="cursor:pointer; margin-bottom:16px;">
      <div style="font-weight:600; color:var(--text-primary); margin-bottom:6px;">${name}</div>
      <div style="font-size:0.8rem; color:var(--text-secondary); line-height:1.4;">${desc || 'No description provided.'}</div>
    </div>
  `;
}

function bindCardEvents(container, type, list) {
  const cards = container.querySelectorAll(`.card-${type}`);
  cards.forEach((card, idx) => {
    card.addEventListener('click', () => {
      const config = list[idx];
      openDrawer(type, config.name, config);
    });
  });
}

// Side Drawer Execution Logic
function openDrawer(type, name, config) {
  appState.activeNode = { type, name, config };
  elements.drawerTitle.innerText = name;
  elements.drawerDesc.innerText = config.description || 'No description provided.';
  
  elements.executionForm.innerHTML = '';
  elements.outputPanel.style.display = 'none';
  
  // Dynamic form generation based on type
  if (type === 'tool') {
    elements.btnExecute.innerText = 'Execute Tool';
    generateFormFromSchema(config.inputSchema);
  } else if (type === 'resource') {
    elements.btnExecute.innerText = 'Read Resource';
    // If it's a template, generate form inputs for placeholders
    const placeholders = config.uri.match(/\{([^}]+)\}/g) || [];
    placeholders.forEach(ph => {
      const paramName = ph.replace(/[{}]/g, '');
      addFormInputField(paramName, 'string', true, `Value for path parameter {${paramName}}`);
    });
  } else if (type === 'prompt') {
    elements.btnExecute.innerText = 'Get Prompt';
    const args = config.arguments || [];
    args.forEach(arg => {
      addFormInputField(arg.name, 'string', arg.required, arg.description);
    });
  }
  
  elements.detailDrawer.classList.add('open');
}

elements.drawerClose.addEventListener('click', () => {
  elements.detailDrawer.classList.remove('open');
});

function addFormInputField(name, type, required, description) {
  const group = document.createElement('div');
  group.className = 'input-group';
  
  const reqAst = required ? '<span style="color:#ef4444">*</span>' : '';
  
  // Format description with examples for complex fields
  let descText = description || '';
  if (type === 'array') {
    descText += ' (JSON array, e.g. [{"item_name": "Spicy Tuna Roll", "quantity": 1}])';
  } else if (type === 'object') {
    descText += ' (JSON object, e.g. {"key": "value"})';
  }
  
  group.innerHTML = `
    <label class="input-label">${name} ${reqAst} <span style="font-weight:normal; font-size:0.7rem; color:var(--text-muted);">${descText}</span></label>
    <input type="text" class="input-field exec-input" data-name="${name}" data-type="${type}" data-required="${required}">
  `;
  elements.executionForm.appendChild(group);
}

function generateFormFromSchema(schema) {
  // We resolve the Pydantic properties schema
  if (!schema) return;
  
  const defs = schema.$defs || {};
  let properties = {};
  let required = [];
  
  // Pydantic wraps fields under properties.input referencing definition model
  if (schema.properties && schema.properties.input && schema.properties.input.$ref) {
    const refPath = schema.properties.input.$ref.split('/').pop();
    const model = defs[refPath] || {};
    properties = model.properties || {};
    required = model.required || [];
  } else if (schema.properties) {
    properties = schema.properties || {};
    required = schema.required || [];
  }
  
  Object.keys(properties).forEach(name => {
    const field = properties[name];
    const isRequired = required.includes(name);
    
    // Check if enum is present and render a select field
    if (field.enum) {
      const group = document.createElement('div');
      group.className = 'input-group';
      const reqAst = isRequired ? '<span style="color:#ef4444">*</span>' : '';
      
      const options = field.enum.map(opt => `<option value="${opt}">${opt}</option>`).join('');
      group.innerHTML = `
        <label class="input-label">${name} ${reqAst} <span style="font-weight:normal; font-size:0.7rem; color:var(--text-muted);">${field.description || ''}</span></label>
        <select class="input-field exec-input" data-name="${name}" data-type="string" data-required="${isRequired}" style="background-color:rgba(0,0,0,0.3); border:1px solid var(--border-color); color:var(--text-primary);">
          ${options}
        </select>
      `;
      elements.executionForm.appendChild(group);
    } else {
      addFormInputField(name, field.type || 'string', isRequired, field.description);
    }
  });
}

function displayOutput(data, type) {
  // Clear panel
  elements.outputPanel.innerHTML = '';
  
  let isSuccess = true;
  let errorMsg = '';
  let displayData = data;
  
  // 1. Unpack Tool Response envelope (contains content list and isError field)
  if (data && Array.isArray(data.content) && data.isError !== undefined) {
    if (data.isError) {
      isSuccess = false;
      errorMsg = data.content[0] ? (data.content[0].text || JSON.stringify(data.content[0])) : 'Tool execution error';
    } else {
      const textVal = data.content[0] ? data.content[0].text : '';
      if (textVal) {
        try {
          displayData = JSON.parse(textVal);
        } catch (e) {
          // If not valid JSON, treat it as a raw string result
          displayData = { result: textVal };
        }
      } else {
        displayData = { result: 'Success (No output returned)' };
      }
    }
  } else {
    // Non-tool response (resources, prompts, direct errors)
    if (data.status === 'failed' || data.error) {
      isSuccess = false;
      errorMsg = data.error || data.detail || 'Execution failed';
    }
  }
  
  // Build Header
  const header = document.createElement('div');
  header.className = 'output-header';
  
  const title = document.createElement('div');
  title.style.fontWeight = '600';
  title.style.fontSize = '0.9rem';
  title.innerText = 'Response Output';
  
  const badge = document.createElement('span');
  badge.className = isSuccess ? 'badge-success' : 'badge-error';
  badge.innerText = isSuccess ? 'Success' : 'Error';
  
  header.appendChild(title);
  header.appendChild(badge);
  elements.outputPanel.appendChild(header);
  
  if (!isSuccess) {
    const errCard = document.createElement('div');
    errCard.className = 'output-card';
    errCard.style.borderColor = 'rgba(239, 68, 68, 0.3)';
    errCard.innerHTML = `
      <div style="color:#ef4444; font-weight:600; font-size:0.85rem; margin-bottom:4px;">Error Details</div>
      <div style="font-family:var(--font-mono); font-size:0.8rem; color:var(--text-secondary); line-height:1.5;">${errorMsg}</div>
    `;
    elements.outputPanel.appendChild(errCard);
  } else {
    // Determine custom formats based on displayData values
    // Case A: Standard Math/Result
    if (displayData.result !== undefined && (typeof displayData.result === 'number' || typeof displayData.result === 'string')) {
      const resCard = document.createElement('div');
      resCard.className = 'output-card';
      resCard.innerHTML = `
        <div style="font-size:0.75rem; color:var(--text-secondary); text-transform:uppercase;">Returned Result</div>
        <div class="output-result-val">${displayData.result}</div>
      `;
      elements.outputPanel.appendChild(resCard);
    }
    
    // Case B: Food Order Success Details
    else if (displayData.order && displayData.order.order_id) {
      const order = displayData.order;
      const itemsHtml = order.items.map(it => `
        <div class="menu-item-row">
          <span>${it.quantity}x ${it.item_name} ${it.notes ? `<span style="font-size:0.75rem; color:var(--text-muted);">(${it.notes})</span>` : ''}</span>
          <span style="font-weight:500;">$${it.total.toFixed(2)}</span>
        </div>
      `).join('');
      
      const orderCard = document.createElement('div');
      orderCard.className = 'output-card';
      orderCard.innerHTML = `
        <div style="font-weight:600; color:var(--color-tool); margin-bottom:8px; display:flex; justify-content:space-between;">
          <span>Order ${order.order_id}</span>
          <span style="text-transform:uppercase; font-size:0.75rem; padding:2px 6px; background:rgba(6,182,212,0.1); border-radius:4px;">${order.status}</span>
        </div>
        <div style="border-top:1px solid rgba(255,255,255,0.05); border-bottom:1px solid rgba(255,255,255,0.05); padding:8px 0; margin-bottom:8px;">
          ${itemsHtml}
        </div>
        <div class="output-grid">
          <div class="grid-item">
            <div class="grid-label">Estimated Delivery</div>
            <div class="grid-value">${order.estimated_delivery_minutes} mins</div>
          </div>
          <div class="grid-item">
            <div class="grid-label">Total Charged</div>
            <div class="grid-value" style="color:#10b981; font-weight:600;">$${order.total.toFixed(2)}</div>
          </div>
        </div>
      `;
      elements.outputPanel.appendChild(orderCard);
    }
    
    // Case C: Standard Menu Items (Food Menu or operations)
    else if (type === 'resource' && (displayData.PizzaMargherita || displayData["Pizza Margherita"] || displayData.ClassicCheeseburger || displayData["Classic Cheeseburger"])) {
      // Menu list
      const menuCard = document.createElement('div');
      menuCard.className = 'output-card';
      menuCard.innerHTML = `
        <div style="font-weight:600; color:var(--color-resource); margin-bottom:8px;">Available Restaurant Menu</div>
        <div style="display:flex; flex-direction:column; gap:4px;">
          ${Object.keys(displayData).map(name => {
            const price = displayData[name].price;
            const diets = displayData[name].diet.join(', ');
            return `
              <div class="menu-item-row">
                <div>
                  <div style="font-weight:500;">${name}</div>
                  <div style="font-size:0.7rem; color:var(--text-muted); text-transform:capitalize;">Diet: ${diets}</div>
                </div>
                <span style="font-weight:600; color:#10b981;">$${price.toFixed(2)}</span>
              </div>
            `;
          }).join('')}
        </div>
      `;
      elements.outputPanel.appendChild(menuCard);
    }
    
    // Case D: List of operations
    else if (displayData.supported_operations) {
      const opCard = document.createElement('div');
      opCard.className = 'output-card';
      opCard.innerHTML = `
        <div style="font-weight:600; color:var(--color-resource); margin-bottom:8px;">Supported Math Operations</div>
        <div style="display:flex; flex-wrap:wrap; gap:8px;">
          ${displayData.supported_operations.map(op => `
            <span style="padding:4px 10px; background:rgba(59,130,246,0.1); border:1px solid rgba(59,130,246,0.2); border-radius:6px; font-size:0.8rem; font-family:var(--font-mono); color:var(--color-resource);">${op}</span>
          `).join('')}
        </div>
      `;
      elements.outputPanel.appendChild(opCard);
    }
    
    // Case E: Prompts Response (Messages list)
    else if (displayData.messages && Array.isArray(displayData.messages)) {
      const promptCard = document.createElement('div');
      promptCard.className = 'output-card';
      const msgsHtml = displayData.messages.map(msg => `
        <div style="margin-bottom:8px; border-left:2px solid var(--color-prompt); padding-left:8px;">
          <div style="font-size:0.7rem; color:var(--text-muted); text-transform:uppercase;">[${msg.role}]</div>
          <div style="font-size:0.85rem; color:var(--text-primary); line-height:1.4;">${msg.content.text || msg.content}</div>
        </div>
      `).join('');
      promptCard.innerHTML = `
        <div style="font-weight:600; color:var(--color-prompt); margin-bottom:8px;">Generated Prompt Messages</div>
        ${msgsHtml}
      `;
      elements.outputPanel.appendChild(promptCard);
    }
    
    // Case F: Default Object View (Clean grid of key-value pairs)
    else if (typeof displayData === 'object' && displayData !== null) {
      const keys = Object.keys(displayData).filter(k => typeof displayData[k] !== 'object');
      if (keys.length > 0) {
        const gridCard = document.createElement('div');
        gridCard.className = 'output-card';
        gridCard.innerHTML = `
          <div class="output-grid">
            ${keys.map(k => `
              <div class="grid-item">
                <div class="grid-label">${k}</div>
                <div class="grid-value">${displayData[k]}</div>
              </div>
            `).join('')}
          </div>
        `;
        elements.outputPanel.appendChild(gridCard);
      }
    }
  }
  
  // 3. Add Raw JSON collapsible view
  const details = document.createElement('details');
  details.className = 'raw-json-details';
  
  const summary = document.createElement('summary');
  summary.className = 'raw-json-summary';
  summary.innerText = '▸ View Raw JSON Response';
  
  const pre = document.createElement('pre');
  pre.className = 'raw-json-pre';
  
  const code = document.createElement('code');
  code.innerText = JSON.stringify(data, null, 2);
  
  pre.appendChild(code);
  details.appendChild(summary);
  details.appendChild(pre);
  
  // Toggle icon on open
  details.addEventListener('toggle', () => {
    summary.innerText = details.open ? '▾ Hide Raw JSON Response' : '▸ View Raw JSON Response';
  });
  
  elements.outputPanel.appendChild(details);
}

// Execute operations in detail drawer (tool calling / resource loading)
elements.btnExecute.addEventListener('click', async () => {
  if (!appState.activeNode) return;
  const { type, name, config } = appState.activeNode;
  
  // 1. Unpack form values
  const inputs = elements.executionForm.querySelectorAll('.exec-input');
  const args = {};
  let validationError = false;
  
  inputs.forEach(input => {
    const paramName = input.getAttribute('data-name');
    const paramType = input.getAttribute('data-type');
    const isRequired = input.getAttribute('data-required') === 'true';
    let val = input.value.trim();
    
    if (isRequired && !val) {
      input.style.borderColor = '#ef4444';
      validationError = true;
    } else {
      input.style.borderColor = '';
    }
    
    if (val) {
      if (paramType === 'number' || paramType === 'integer') {
        args[paramName] = Number(val);
      } else if (paramType === 'boolean') {
        args[paramName] = val.toLowerCase() === 'true';
      } else if (paramType === 'array' || paramType === 'object') {
        try {
          args[paramName] = JSON.parse(val);
        } catch (e) {
          args[paramName] = val;
        }
      } else {
        args[paramName] = val;
      }
    }
  });
  
  if (validationError) {
    alert('Please fill out all required parameters.');
    return;
  }
  
  elements.btnExecute.innerText = 'Loading...';
  elements.outputPanel.style.display = 'block';
  elements.outputPanel.innerText = 'Processing request...';
  
  // Flash canvas connection line if executing from canvas
  const nodeId = `${type}-${name.replace(/[^a-zA-Z0-9]/g, '-')}`;
  flashConnection(nodeId, type);
  
  try {
    let endpoint = '';
    let bodyObj = {};
    
    if (type === 'tool') {
      endpoint = '/api/call-tool';
      // Tools in NitroStack receive parameters wrapped under {"input": {...}}
      bodyObj = { name, arguments: { input: args } };
    } else if (type === 'resource') {
      endpoint = '/api/read-resource';
      // Substitute placeholders in template URI
      let finalUri = config.uri;
      Object.keys(args).forEach(k => {
        finalUri = finalUri.replace(`{${k}}`, args[k]);
      });
      bodyObj = { uri: finalUri };
    } else if (type === 'prompt') {
      endpoint = '/api/get-prompt';
      bodyObj = { name, arguments: args };
    }
    
    const res = await fetch(endpoint, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(bodyObj)
    });
    
    const data = await res.json();
    displayOutput(data, type);
  } catch (e) {
    displayOutput({ status: 'failed', error: e.toString() }, type);
  } finally {
    elements.btnExecute.innerText = type === 'tool' ? 'Execute Tool' : (type === 'resource' ? 'Read Resource' : 'Get Prompt');
  }
});

// AI Chat Interface logic
elements.btnChatSend.addEventListener('click', sendChatMessage);
elements.chatInput.addEventListener('keydown', (e) => {
  if (e.key === 'Enter') sendChatMessage();
});

async function sendChatMessage() {
  const msg = elements.chatInput.value.trim();
  if (!msg) return;
  
  if (!appState.connected) {
    alert('Please connect to the MCP server first.');
    return;
  }
  
  // 1. Append User Bubble
  appendChatBubble('user', msg);
  elements.chatInput.value = '';
  
  // Append temporary Agent thinking bubble
  const thinkingId = appendChatBubble('agent', 'Thinking...');
  
  try {
    const res = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: msg })
    });
    const data = await res.json();
    
    // Replace thinking bubble
    const thinkingBubble = document.getElementById(thinkingId);
    if (thinkingBubble) {
      thinkingBubble.innerHTML = '';
      
      const content = document.createElement('div');
      content.className = 'chat-bubble';
      content.innerText = data.response;
      thinkingBubble.appendChild(content);
      
      // If a tool was triggered, append an inline execution log card
      if (data.tool_called) {
        const toolCard = document.createElement('div');
        toolCard.className = 'chat-tool-log';
        toolCard.innerHTML = `
          <div style="color:var(--color-tool); font-weight:600; margin-bottom:4px;">⚙️ Tool Executed: ${data.tool_called}</div>
          <div style="color:var(--text-secondary); margin-bottom:2px;">Arguments: ${JSON.stringify(data.arguments.input || data.arguments)}</div>
          <div style="color:var(--text-muted);">Output: ${typeof data.output === 'object' ? JSON.stringify(data.output) : data.output}</div>
        `;
        thinkingBubble.appendChild(toolCard);
        
        // Flash connection on the visual canvas in background!
        const nodeId = `tool-${data.tool_called.replace(/[^a-zA-Z0-9]/g, '-')}`;
        flashConnection(nodeId, 'tool');
      }
    }
  } catch (e) {
    const thinkingBubble = document.getElementById(thinkingId);
    if (thinkingBubble) {
      thinkingBubble.innerHTML = `<div class="chat-bubble">Failed to get response: ${e}</div>`;
    }
  }
  
  elements.chatHistory.scrollTop = elements.chatHistory.scrollHeight;
}

function appendChatBubble(role, text) {
  const id = `chat-msg-${Date.now()}-${Math.floor(Math.random()*1000)}`;
  const msg = document.createElement('div');
  msg.className = `chat-message ${role}`;
  msg.id = id;
  
  msg.innerHTML = `<div class="chat-bubble">${text}</div>`;
  elements.chatHistory.appendChild(msg);
  elements.chatHistory.scrollTop = elements.chatHistory.scrollHeight;
  return id;
}

// Sync dropdown selection with hidden text input
elements.connScriptSelect.addEventListener('change', () => {
  if (elements.connScriptSelect.value === 'custom') {
    elements.connScript.style.display = 'block';
    elements.connScript.focus();
  } else {
    elements.connScript.style.display = 'none';
    elements.connScript.value = elements.connScriptSelect.value;
  }
});

// Load detected projects from backend
async function loadDetectedProjects() {
  try {
    const res = await fetch('/api/detect-projects');
    const data = await res.json();
    const select = elements.connScriptSelect;
    if (!select) return;
    
    // Clear select
    select.innerHTML = '';
    
    if (data.projects && data.projects.length > 0) {
      data.projects.forEach(project => {
        const opt = document.createElement('option');
        opt.value = project;
        opt.textContent = project;
        select.appendChild(opt);
      });
      // Add custom option
      const customOpt = document.createElement('option');
      customOpt.value = 'custom';
      customOpt.textContent = 'Custom...';
      select.appendChild(customOpt);
      
      // Select the first detected project
      select.value = data.projects[0];
      elements.connScript.value = data.projects[0];
      elements.connScript.style.display = 'none';
    } else {
      // No projects detected, fallback to Custom
      const customOpt = document.createElement('option');
      customOpt.value = 'custom';
      customOpt.textContent = 'Custom...';
      select.appendChild(customOpt);
      select.value = 'custom';
      elements.connScript.style.display = 'block';
    }
  } catch (e) {
    console.error('Failed to load detected projects:', e);
  }
}

// Check initial connection status on page load
async function checkInitialStatus() {
  try {
    const res = await fetch('/api/status');
    const data = await res.json();
    if (data.connected) {
      elements.connCommand.value = data.command;
      elements.connScript.value = data.script_path;
      
      // Sync dropdown select
      let matched = false;
      for (let i = 0; i < elements.connScriptSelect.options.length; i++) {
        if (elements.connScriptSelect.options[i].value === data.script_path) {
          elements.connScriptSelect.value = data.script_path;
          elements.connScript.style.display = 'none';
          matched = true;
          break;
        }
      }
      if (!matched) {
        elements.connScriptSelect.value = 'custom';
        elements.connScript.style.display = 'block';
      }
      
      setConnectionState(true);
    }
  } catch (e) {
    console.error('Failed to get initial status:', e);
  }
}

// File Explorer Modal Elements and State
const modalEl = document.getElementById('add-server-modal');
const btnBrowseFs = document.getElementById('btn-browse-fs');
const btnCloseModal = document.getElementById('btn-close-modal');
const modalTabs = document.querySelectorAll('.modal-tab');
const modalTabContents = document.querySelectorAll('.modal-tab-content');

const fsCurrentPath = document.getElementById('fs-current-path');
const btnFsBack = document.getElementById('btn-fs-back');
const btnFsHome = document.getElementById('btn-fs-home');
const fsFavorites = document.getElementById('fs-favorites');
const fsFileList = document.getElementById('fs-file-list');

const btnFsCreateApp = document.getElementById('btn-fs-create-app');
const btnFsOpenProject = document.getElementById('btn-fs-open-project');

const recentProjectsList = document.getElementById('recent-projects-list');

const modalOtherCommand = document.getElementById('modal-other-command');
const modalOtherScript = document.getElementById('modal-other-script');

const marketplaceList = document.getElementById('marketplace-list');

let currentExplorerPath = '';
let selectedProject = null;
let activeModalTab = 'nitro';

// Path & Basename Helpers
function getParentPath(path) {
  if (!path) return '';
  let normalized = path.replace(/\\/g, '/');
  if (normalized.endsWith('/')) {
    normalized = normalized.slice(0, -1);
  }
  const idx = normalized.lastIndexOf('/');
  if (idx === -1) return '';
  let parent = normalized.substring(0, idx);
  if (parent.length === 2 && parent[1] === ':') {
    parent += '/';
  }
  return parent;
}

function getPathBasename(path) {
  if (!path) return '';
  let normalized = path.replace(/\\/g, '/');
  if (normalized.endsWith('/')) {
    normalized = normalized.slice(0, -1);
  }
  const idx = normalized.lastIndexOf('/');
  if (idx === -1) return normalized;
  return normalized.substring(idx + 1);
}

// Caching and opening recent projects
function saveToRecent(path, command) {
  let recents = [];
  try {
    recents = JSON.parse(localStorage.getItem('recent_projects') || '[]');
  } catch (e) {
    recents = [];
  }
  
  recents = recents.filter(p => p.path !== path);
  
  const basename = getPathBasename(path);
  recents.unshift({
    path: path,
    command: command,
    name: basename,
    timestamp: Date.now()
  });
  
  if (recents.length > 10) {
    recents = recents.slice(0, 10);
  }
  
  localStorage.setItem('recent_projects', JSON.stringify(recents));
}

function openSelectedProject() {
  if (!selectedProject) return;
  
  const path = selectedProject.path;
  const command = selectedProject.command;
  
  // Update script select dropdown
  let found = false;
  for (let i = 0; i < elements.connScriptSelect.options.length; i++) {
    if (elements.connScriptSelect.options[i].value === path) {
      elements.connScriptSelect.value = path;
      found = true;
      break;
    }
  }
  
  if (!found) {
    const opt = document.createElement('option');
    opt.value = path;
    opt.textContent = path;
    elements.connScriptSelect.insertBefore(opt, elements.connScriptSelect.firstChild);
    elements.connScriptSelect.value = path;
  }
  
  elements.connCommand.value = command;
  elements.connScript.value = path;
  elements.connScript.style.display = 'none';
  
  saveToRecent(path, command);
  modalEl.style.display = 'none';
}

// Render recent projects list
function renderRecentProjects() {
  recentProjectsList.innerHTML = '';
  let recents = [];
  try {
    recents = JSON.parse(localStorage.getItem('recent_projects') || '[]');
  } catch (e) {
    recents = [];
  }
  
  if (recents.length === 0) {
    recentProjectsList.innerHTML = `<p style="color:var(--text-secondary); text-align:center; padding:32px;">No recently opened projects.</p>`;
    return;
  }
  
  recents.forEach(p => {
    const fileItem = document.createElement('div');
    fileItem.className = 'file-item';
    
    const fileIcon = document.createElement('div');
    fileIcon.className = 'file-icon';
    fileIcon.innerHTML = '📁';
    
    const nameContainer = document.createElement('div');
    nameContainer.className = 'file-name-container';
    
    const fileName = document.createElement('div');
    fileName.className = 'file-name';
    fileName.innerText = p.name;
    
    const badge = document.createElement('span');
    badge.className = 'nitro-project-badge';
    badge.innerText = 'Recent';
    fileName.appendChild(badge);
    
    const fileDetails = document.createElement('div');
    fileDetails.className = 'file-details';
    fileDetails.innerText = p.path;
    
    nameContainer.appendChild(fileName);
    nameContainer.appendChild(fileDetails);
    
    fileItem.appendChild(fileIcon);
    fileItem.appendChild(nameContainer);
    
    fileItem.addEventListener('click', () => {
      recentProjectsList.querySelectorAll('.file-item').forEach(el => el.classList.remove('selected'));
      fileItem.classList.add('selected');
      
      selectedProject = {
        path: p.path,
        command: p.command,
        is_nitro: true
      };
      btnFsOpenProject.removeAttribute('disabled');
    });
    
    fileItem.addEventListener('dblclick', () => {
      selectedProject = {
        path: p.path,
        command: p.command,
        is_nitro: true
      };
      openSelectedProject();
    });
    
    recentProjectsList.appendChild(fileItem);
  });
}

// Fetch and render directory explorer path
async function updateExplorer(path) {
  fsFileList.innerHTML = `<p style="color:var(--text-secondary); text-align:center; padding:32px;">Loading directory contents...</p>`;
  
  try {
    const url = `/api/fs/list` + (path ? `?path=${encodeURIComponent(path)}` : '');
    const res = await fetch(url);
    if (!res.ok) {
      const errorData = await res.json();
      fsFileList.innerHTML = `<p style="color:#ef4444; text-align:center; padding:32px;">Error: ${errorData.error || 'Failed to load directory'}</p>`;
      return;
    }
    
    const data = await res.json();
    currentExplorerPath = data.current_path;
    fsCurrentPath.value = currentExplorerPath.replace(/\//g, '\\');
    
    // Render quick favorite folder buttons
    fsFavorites.innerHTML = '';
    if (data.favorites) {
      Object.keys(data.favorites).forEach(name => {
        const btn = document.createElement('button');
        btn.className = 'fav-btn';
        btn.innerText = name;
        btn.addEventListener('click', () => {
          updateExplorer(data.favorites[name]);
        });
        fsFavorites.appendChild(btn);
      });
    }
    
    // Render folder items list
    fsFileList.innerHTML = '';
    if (!data.items || data.items.length === 0) {
      fsFileList.innerHTML = `<p style="color:var(--text-muted); text-align:center; padding:32px;">Empty directory</p>`;
      return;
    }
    
    data.items.forEach(item => {
      const fileItem = document.createElement('div');
      fileItem.className = 'file-item';
      if (item.is_nitro) {
        fileItem.classList.add('nitro-project-item');
      }
      
      const fileIcon = document.createElement('div');
      fileIcon.className = 'file-icon';
      fileIcon.innerHTML = item.is_dir ? '📁' : '📄';
      
      const nameContainer = document.createElement('div');
      nameContainer.className = 'file-name-container';
      
      const fileName = document.createElement('div');
      fileName.className = 'file-name';
      fileName.innerText = item.name;
      
      if (item.is_nitro) {
        const badge = document.createElement('span');
        badge.className = 'nitro-project-badge';
        badge.innerText = 'Nitro';
        fileName.appendChild(badge);
      }
      
      const fileDetails = document.createElement('div');
      fileDetails.className = 'file-details';
      fileDetails.innerText = item.is_dir ? 'Folder' : 'Python File';
      
      nameContainer.appendChild(fileName);
      nameContainer.appendChild(fileDetails);
      
      fileItem.appendChild(fileIcon);
      fileItem.appendChild(nameContainer);
      
      if (item.is_dir) {
        const chevron = document.createElement('span');
        chevron.style.color = 'var(--text-muted)';
        chevron.innerHTML = '&#10095;';
        fileItem.appendChild(chevron);
      }
      
      fileItem.addEventListener('click', () => {
        fsFileList.querySelectorAll('.file-item').forEach(el => el.classList.remove('selected'));
        fileItem.classList.add('selected');
        
        if (item.is_nitro) {
          selectedProject = {
            path: item.path,
            command: 'python',
            is_nitro: true
          };
          btnFsOpenProject.removeAttribute('disabled');
        } else {
          selectedProject = null;
          btnFsOpenProject.setAttribute('disabled', 'true');
        }
      });
      
      fileItem.addEventListener('dblclick', () => {
        if (item.is_dir) {
          updateExplorer(item.path);
        } else if (item.is_nitro) {
          selectedProject = {
            path: item.path,
            command: 'python',
            is_nitro: true
          };
          openSelectedProject();
        }
      });
      
      fsFileList.appendChild(fileItem);
    });
    
  } catch (e) {
    fsFileList.innerHTML = `<p style="color:#ef4444; text-align:center; padding:32px;">Error listing files: ${e}</p>`;
  }
}

// Validate custom path inputs on the Other Project tab
function validateOtherProjectInputs() {
  const path = modalOtherScript.value.trim();
  const command = modalOtherCommand.value.trim() || 'python';
  if (path) {
    selectedProject = {
      path: path,
      command: command,
      is_nitro: false
    };
    btnFsOpenProject.removeAttribute('disabled');
  } else {
    selectedProject = null;
    btnFsOpenProject.setAttribute('disabled', 'true');
  }
}

// Tab Switching Handler
function switchModalTab(tabName) {
  activeModalTab = tabName;
  
  modalTabs.forEach(t => {
    if (t.getAttribute('data-modal-tab') === tabName) {
      t.classList.add('active');
    } else {
      t.classList.remove('active');
    }
  });
  
  modalTabContents.forEach(content => {
    if (content.id === `modal-tab-${tabName}`) {
      content.style.display = 'flex';
    } else {
      content.style.display = 'none';
    }
  });
  
  selectedProject = null;
  btnFsOpenProject.setAttribute('disabled', 'true');
  
  if (tabName === 'recent') {
    renderRecentProjects();
  } else if (tabName === 'other') {
    validateOtherProjectInputs();
  } else if (tabName === 'marketplace') {
    marketplaceList.querySelectorAll('.file-item').forEach(el => el.classList.remove('selected'));
  } else if (tabName === 'nitro') {
    if (!currentExplorerPath) {
      updateExplorer('');
    }
  }
}

// Bind modal tab click listeners
modalTabs.forEach(tab => {
  tab.addEventListener('click', () => {
    switchModalTab(tab.getAttribute('data-modal-tab'));
  });
});

// Path navigation buttons
btnFsBack.addEventListener('click', () => {
  if (activeModalTab !== 'nitro') return;
  const parent = getParentPath(currentExplorerPath);
  if (parent && parent !== currentExplorerPath) {
    updateExplorer(parent);
  }
});

btnFsHome.addEventListener('click', () => {
  if (activeModalTab !== 'nitro') return;
  updateExplorer('');
});

// Modal Visibility Handlers
btnBrowseFs.addEventListener('click', () => {
  modalEl.style.display = 'flex';
  switchModalTab('nitro');
});

btnCloseModal.addEventListener('click', () => {
  modalEl.style.display = 'none';
});

modalEl.addEventListener('click', (e) => {
  if (e.target === modalEl) {
    modalEl.style.display = 'none';
  }
});

// Action Buttons
btnFsOpenProject.addEventListener('click', () => {
  if (activeModalTab === 'other') {
    const path = modalOtherScript.value.trim();
    const command = modalOtherCommand.value.trim() || 'python';
    if (path) {
      selectedProject = {
        path: path,
        command: command,
        is_nitro: false
      };
      openSelectedProject();
    }
  } else {
    openSelectedProject();
  }
});

btnFsCreateApp.addEventListener('click', async () => {
  const name = prompt('Enter the name of the new NitroStack project:');
  if (!name) return;
  
  const cleanName = name.trim();
  if (!cleanName) return;
  
  const parentPath = currentExplorerPath || '';
  btnFsCreateApp.innerText = 'Creating...';
  btnFsCreateApp.setAttribute('disabled', 'true');
  
  try {
    const res = await fetch('/api/fs/create', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ parent_path: parentPath, name: cleanName })
    });
    
    const data = await res.json();
    if (data.status === 'success') {
      alert(`Successfully scaffolded NitroStack project: ${cleanName}`);
      await updateExplorer(parentPath);
    } else {
      alert(`Failed to create project: ${data.error || 'Unknown error'}`);
    }
  } catch (e) {
    alert(`Error calling project creation API: ${e}`);
  } finally {
    btnFsCreateApp.innerText = '+ Create App';
    btnFsCreateApp.removeAttribute('disabled');
  }
});

// Other project inputs
modalOtherScript.addEventListener('input', validateOtherProjectInputs);
modalOtherCommand.addEventListener('input', validateOtherProjectInputs);

// Bind Marketplace items
const marketplaceItems = marketplaceList.querySelectorAll('.file-item');
marketplaceItems.forEach(item => {
  const cmd = item.getAttribute('data-market-cmd') || 'python';
  const script = item.getAttribute('data-market-script');
  
  item.addEventListener('click', () => {
    marketplaceList.querySelectorAll('.file-item').forEach(el => el.classList.remove('selected'));
    item.classList.add('selected');
    
    selectedProject = {
      path: script,
      command: cmd,
      is_nitro: true
    };
    btnFsOpenProject.removeAttribute('disabled');
  });
  
  item.addEventListener('dblclick', () => {
    selectedProject = {
      path: script,
      command: cmd,
      is_nitro: true
    };
    openSelectedProject();
  });
  
  const loadLabel = item.querySelector('span');
  if (loadLabel) {
    loadLabel.addEventListener('click', (e) => {
      e.stopPropagation();
      selectedProject = {
        path: script,
        command: cmd,
        is_nitro: true
      };
      openSelectedProject();
    });
  }
});

async function initDashboard() {
  await loadDetectedProjects();
  await checkInitialStatus();
}

initDashboard();
