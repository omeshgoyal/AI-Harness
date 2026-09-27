// Setup Marked.js and Highlight.js
// using custom renderer below

const renderer = new marked.Renderer();
renderer.code = function(code, language) {
    const validLang = !!(language && hljs.getLanguage(language));
    const highlighted = validLang 
        ? hljs.highlight(code, { language }).value 
        : hljs.highlightAuto(code).value;
    
    const langDisplay = language ? language : 'code';
    const base64Code = btoa(unescape(encodeURIComponent(code)));
    
    return `
        <div style="position: relative; margin-bottom: 1rem;">
            <div class="code-header">
                <span>${langDisplay}</span>
                <button class="copy-btn" onclick="copyCodeFromBase64(this, '${base64Code}')">Copy</button>
            </div>
            <pre><code class="hljs ${language || ''}">${highlighted}</code></pre>
        </div>
    `;
};
marked.use({ renderer });

const chat = document.getElementById('chat');
const prompt = document.getElementById('prompt');
const sendBtn = document.getElementById('send');
const sidebar = document.getElementById('sidebar');
const sessionList = document.getElementById('session-list');
const costSpan = document.getElementById('cost');

let isWaiting = false;

function toggleSidebar() {
    sidebar.classList.toggle('hidden');
}

window.copyCodeFromBase64 = function(btn, base64) {
    const code = decodeURIComponent(escape(atob(base64)));
    navigator.clipboard.writeText(code).then(() => {
        const originalText = btn.innerText;
        btn.innerText = 'Copied!';
        setTimeout(() => btn.innerText = originalText, 2000);
    });
}

async function fetchState() {
    try {
        const res = await fetch('/api/state');
        const data = await res.json();
        if (data.error) return;
        
        renderChat(data);
        renderSessions(data.sessions || [], data.current_session);
        if (data.cost !== undefined) costSpan.innerText = data.cost.toFixed(2);
    } catch (e) {
        console.error("Failed to fetch state:", e);
    }
}

async function newSession() {
    try { await fetch('/api/session/new', { method: 'POST' }); fetchState(); } catch (e) {}
}

async function loadSession(name) {
    try {
        await fetch('/api/session/load', {
            method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({name})
        });
        fetchState();
    } catch (e) {}
}

function renderSessions(sessions, current) {
    sessionList.innerHTML = '';
    sessions.forEach(s => {
        const div = document.createElement('div');
        div.className = 'session-item' + (s === current ? ' active' : '');
        div.innerText = s;
        div.onclick = () => loadSession(s);
        sessionList.appendChild(div);
    });
}

function escapeHTML(str) {
    if (!str) return '';
    return str.replace(/[&<>'"]/g, tag => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' }[tag]));
}

function getArgs(tc) {
    try { return JSON.parse(tc.function.arguments); } catch(e) { return {}; }
}

function renderToolCallOutput(tc, toolOutputs) {
    const output = toolOutputs[tc.id];
    const argsFormatted = escapeHTML(JSON.stringify(getArgs(tc), null, 2));
    const isPending = output === undefined;
    
    let statusIcon = isPending ? '[..]' : '[✓]';
    if (output && output.toLowerCase().includes('error')) statusIcon = '[x]';
    
    const outputHtml = output ? `
        <div style="margin-top: 0.5rem; padding-top: 0.5rem; border-top: 1px solid #eaeaea;">
            <strong>Output:</strong>
            <pre style="margin: 0.5rem 0 0 0; background: #f0f0f0; max-height: 250px; overflow-y: auto;"><code>${escapeHTML(output)}</code></pre>
        </div>
    ` : (isPending ? '<div style="margin-top:0.5rem; color:#888; font-style:italic;">Running...</div>' : '');

    return `
        <div style="margin-top:0.5rem;">
            <strong>Arguments:</strong>
            <pre style="margin: 0.25rem 0 0 0; background: #f9f9f9; padding: 0.5rem; border-radius: 4px;"><code>${argsFormatted}</code></pre>
            ${outputHtml}
        </div>
    `;
}

function renderChat(data) {
    chat.innerHTML = '';
    if (!data.messages) return;

    const toolOutputs = {};
    data.messages.forEach(msg => {
        if (msg.role === 'tool') toolOutputs[msg.tool_call_id] = msg.content;
    });

    // Group into turns
    let turns = [];
    let currentTurn = [];
    data.messages.forEach(msg => {
        if (msg.role === 'system') return;
        if (msg.role === 'user') {
            if (currentTurn.length > 0) turns.push(currentTurn);
            turns.push([msg]);
            currentTurn = [];
        } else {
            currentTurn.push(msg);
        }
    });
    if (currentTurn.length > 0) turns.push(currentTurn);

    turns.forEach(turn => {
        if (turn[0].role === 'user') {
            chat.innerHTML += `
                <div class="message user">
                    <div class="avatar">U</div>
                    <div class="content">${escapeHTML(turn[0].content).replace(/\n/g, '<br>')}</div>
                </div>
            `;
            return;
        }

        // It's an assistant turn
        let lastMsg = turn[turn.length - 1];
        let finalText = "";
        
        if (lastMsg.role === 'assistant' && (!lastMsg.tool_calls || lastMsg.tool_calls.length === 0)) {
            finalText = lastMsg.content || "";
            turn.pop();
        }

        let workItems = [];
        turn.forEach(msg => {
            if (msg.role === 'assistant') {
                if (msg.content) {
                    workItems.push({ type: 'thought', content: msg.content });
                }
                if (msg.tool_calls) {
                    msg.tool_calls.forEach(tc => {
                        let name = tc.function.name;
                        if (name === 'bash') {
                            let lastItem = workItems[workItems.length - 1];
                            if (lastItem && lastItem.type === 'commands') {
                                lastItem.calls.push(tc);
                            } else {
                                workItems.push({ type: 'commands', calls: [tc] });
                            }
                        } else if (name === 'write_file' || name === 'str_replace') {
                            workItems.push({ type: 'edit', call: tc });
                        } else {
                            workItems.push({ type: 'other', call: tc });
                        }
                    });
                }
            }
        });

        let workHtml = "";
        if (workItems.length > 0) {
            let innerHtml = "";
            let anyPending = false;

            workItems.forEach(item => {
                if (item.type === 'thought') {
                try {
                    innerHtml += `
                        <details class="tool-call-details sub-detail">
                            <summary>Thought process</summary>
                            <div class="tool-call-content">${marked.parse(item.content)}</div>
                        </details>
                    `;
                } catch(e) { console.error("Marked error:", e); }
                } else if (item.type === 'commands') {
                    let cmdListHtml = item.calls.map(tc => {
                        if (toolOutputs[tc.id] === undefined) anyPending = true;
                        let args = getArgs(tc);
                        return `
                            <details style="margin-bottom: 0.5rem;">
                                <summary style="cursor: pointer; font-size: 13px; font-family: monospace;">$ ${escapeHTML(args.command)}</summary>
                                ${renderToolCallOutput(tc, toolOutputs)}
                            </details>
                        `;
                    }).join('');
                    innerHtml += `
                        <details class="tool-call-details sub-detail">
                            <summary>Ran ${item.calls.length} command${item.calls.length > 1 ? 's' : ''}</summary>
                            <div class="tool-call-content">${cmdListHtml}</div>
                        </details>
                    `;
                } else if (item.type === 'edit') {
                    if (toolOutputs[item.call.id] === undefined) anyPending = true;
                    let args = getArgs(item.call);
                    let filename = args.path ? args.path.split('/').pop() : 'file';
                    innerHtml += `
                        <details class="tool-call-details sub-detail">
                            <summary>Edited ${escapeHTML(filename)}</summary>
                            <div class="tool-call-content">
                                ${renderToolCallOutput(item.call, toolOutputs)}
                            </div>
                        </details>
                    `;
                } else if (item.type === 'other') {
                    if (toolOutputs[item.call.id] === undefined) anyPending = true;
                    innerHtml += `
                        <details class="tool-call-details sub-detail">
                            <summary>Used ${item.call.function.name}</summary>
                            <div class="tool-call-content">
                                ${renderToolCallOutput(item.call, toolOutputs)}
                            </div>
                        </details>
                    `;
                }
            });

            let mainTitle = anyPending ? "Working..." : "Agent Work";
            workHtml = `
                <details class="master-work-details">
                    <summary>${mainTitle}</summary>
                    <div class="master-work-content">
                        ${innerHtml}
                    </div>
                </details>
            `;
        }

        let finalHtml = "";
        try {
            finalHtml = finalText ? marked.parse(finalText) : "";
        } catch(e) { console.error("Marked error on final:", e); finalHtml = escapeHTML(finalText); }
        
        if (workHtml || finalHtml) {
            chat.innerHTML += `
                <div class="message assistant">
                    <div class="avatar">✦</div>
                    <div class="content">
                        ${workHtml}
                        ${finalHtml}
                    </div>
                </div>
            `;
        }
    });
    
    if(data.pending_permission && data.permission_data) {
        const perm = data.permission_data;
        chat.innerHTML += `
            <div class="message assistant" id="permission-block">
                <div class="avatar">!</div>
                <div class="content">
                    <div class="permission-box">
                        <strong>Approval required</strong>
                        <div style="margin: 0.5rem 0; font-family: ui-monospace, monospace; font-size: 13px;">${escapeHTML(perm.func_name)}</div>
                        <details style="margin-bottom: 1rem;">
                            <summary style="cursor: pointer; font-size: 12px; color: #666;">View Arguments</summary>
                            <pre style="margin-top: 0.5rem; background: #f9f9f9; padding: 0.5rem; border-radius: 4px; font-size: 11px;">${escapeHTML(JSON.stringify(perm.args, null, 2))}</pre>
                        </details>
                        <div class="permission-actions">
                            <button class="btn btn-allow" onclick="sendPermission(true, this)">Allow</button>
                            <button class="btn btn-deny" onclick="sendPermission(false, this)">Reject</button>
                        </div>
                    </div>
                </div>
            </div>
        `;
    } else if (isWaiting) {
        chat.innerHTML += `
            <div class="message assistant">
                <div class="avatar">✦</div>
                <div class="content"><span style="color:#888; font-style:italic">Thinking...</span></div>
            </div>
        `;
    }
    
    const scrollContainer = document.getElementById('scroll-container');
    scrollContainer.scrollTo(0, scrollContainer.scrollHeight);
}

async function sendPermission(allow, btn) {
    if (isWaiting) return;
    btn.innerHTML = 'Executing...';
    btn.disabled = true;
    isWaiting = true;
    try {
        await fetch('/api/permission', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({allow})
        });
    } catch(e) {}
    isWaiting = false;
    fetchState();
}

async function sendMessage() {
    const text = prompt.value.trim();
    if(!text || isWaiting) return;
    prompt.value = '';
    prompt.style.height = 'auto';
    isWaiting = true;
    
    chat.innerHTML += `
        <div class="message user">
            <div class="avatar">U</div>
            <div class="content">${escapeHTML(text).replace(/\n/g, '<br>')}</div>
        </div>
        <div class="message assistant">
            <div class="avatar">✦</div>
            <div class="content"><span style="color:#888; font-style:italic">Thinking...</span></div>
        </div>
    `;
    const scrollContainer = document.getElementById('scroll-container');
    scrollContainer.scrollTo(0, scrollContainer.scrollHeight);
    
    try {
        await fetch('/api/chat', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({text})
        });
        await fetch('/api/session/save', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({name: text.substring(0, 20)})
        });
    } catch(e) {}
    isWaiting = false;
    fetchState();
}

sendBtn.addEventListener('click', sendMessage);
prompt.addEventListener('keydown', e => {
    if(e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
    }
});

prompt.addEventListener('input', function() {
    this.style.height = 'auto';
    this.style.height = (this.scrollHeight) + 'px';
});

fetchState();
