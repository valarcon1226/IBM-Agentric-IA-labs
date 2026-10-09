(function() {
    const api = document.currentScript.getAttribute('data-api');
    const title = document.currentScript.getAttribute('data-title') || 'Chat';
    let sessionId = localStorage.getItem('chat_session_id');
    if (!sessionId) {
        sessionId = Math.random().toString(36).substring(2, 15);
        localStorage.setItem('chat_session_id', sessionId);
    }

    const container = document.createElement('div');
    container.style.position = 'fixed';
    container.style.bottom = '20px';
    container.style.right = '20px';
    container.style.zIndex = '9999';
    container.style.fontFamily = 'sans-serif';

    const button = document.createElement('button');
    button.textContent = '💬';
    button.style.width = '60px';
    button.style.height = '60px';
    button.style.borderRadius = '50%';
    button.style.backgroundColor = '#000';
    button.style.color = '#fff';
    button.style.border = 'none';
    button.style.fontSize = '30px';
    button.style.cursor = 'pointer';
    button.style.boxShadow = '0 4px 6px rgba(0,0,0,0.1)';
    button.setAttribute('aria-label', 'Abrir chat');

    const panel = document.createElement('div');
    panel.style.display = 'none';
    panel.style.width = '350px';
    panel.style.height = '500px';
    panel.style.backgroundColor = '#fff';
    panel.style.border = '1px solid #ccc';
    panel.style.borderRadius = '10px';
    panel.style.boxShadow = '0 4px 6px rgba(0,0,0,0.1)';
    panel.style.flexDirection = 'column';
    panel.style.overflow = 'hidden';
    panel.style.marginBottom = '10px';
    panel.style.position = 'absolute';
    panel.style.bottom = '70px';
    panel.style.right = '0';
    
    // For mobile
    if (window.innerWidth < 400) {
        panel.style.width = '90vw';
    }

    const header = document.createElement('div');
    header.style.backgroundColor = '#000';
    header.style.color = '#fff';
    header.style.padding = '15px';
    header.style.fontWeight = 'bold';
    header.style.display = 'flex';
    header.style.justifyContent = 'space-between';
    header.textContent = title;

    const closeBtn = document.createElement('button');
    closeBtn.textContent = '✕';
    closeBtn.style.background = 'none';
    closeBtn.style.border = 'none';
    closeBtn.style.color = '#fff';
    closeBtn.style.cursor = 'pointer';
    closeBtn.setAttribute('aria-label', 'Cerrar chat');
    header.appendChild(closeBtn);

    const messages = document.createElement('div');
    messages.style.flex = '1';
    messages.style.padding = '15px';
    messages.style.overflowY = 'auto';
    messages.setAttribute('aria-live', 'polite');

    const inputArea = document.createElement('form');
    inputArea.style.display = 'flex';
    inputArea.style.borderTop = '1px solid #ccc';
    
    const input = document.createElement('input');
    input.type = 'text';
    input.style.flex = '1';
    input.style.padding = '15px';
    input.style.border = 'none';
    input.style.outline = 'none';
    input.placeholder = 'Escribe un mensaje...';
    input.setAttribute('aria-label', 'Mensaje');
    
    const sendBtn = document.createElement('button');
    sendBtn.textContent = 'Enviar';
    sendBtn.style.padding = '0 15px';
    sendBtn.style.backgroundColor = '#000';
    sendBtn.style.color = '#fff';
    sendBtn.style.border = 'none';
    sendBtn.style.cursor = 'pointer';

    inputArea.appendChild(input);
    inputArea.appendChild(sendBtn);

    panel.appendChild(header);
    panel.appendChild(messages);
    panel.appendChild(inputArea);
    container.appendChild(panel);
    container.appendChild(button);
    document.body.appendChild(container);

    function addMessage(text, isUser) {
        const msg = document.createElement('div');
        msg.textContent = text;
        msg.style.marginBottom = '10px';
        msg.style.padding = '10px';
        msg.style.borderRadius = '10px';
        msg.style.maxWidth = '80%';
        msg.style.wordBreak = 'break-word';
        if (isUser) {
            msg.style.backgroundColor = '#dcf8c6';
            msg.style.marginLeft = 'auto';
            msg.style.color = '#000';
        } else {
            msg.style.backgroundColor = '#f1f1f1';
            msg.style.color = '#000';
        }
        messages.appendChild(msg);
        messages.scrollTop = messages.scrollHeight;
        
        // Save to history
        const history = JSON.parse(localStorage.getItem('chat_history') || '[]');
        history.push({text, isUser});
        localStorage.setItem('chat_history', JSON.stringify(history));
    }
    
    // Load history
    const history = JSON.parse(localStorage.getItem('chat_history') || '[]');
    history.forEach(item => {
        const msg = document.createElement('div');
        msg.textContent = item.text;
        msg.style.marginBottom = '10px';
        msg.style.padding = '10px';
        msg.style.borderRadius = '10px';
        msg.style.maxWidth = '80%';
        msg.style.wordBreak = 'break-word';
        if (item.isUser) {
            msg.style.backgroundColor = '#dcf8c6';
            msg.style.marginLeft = 'auto';
            msg.style.color = '#000';
        } else {
            msg.style.backgroundColor = '#f1f1f1';
            msg.style.color = '#000';
        }
        messages.appendChild(msg);
    });
    messages.scrollTop = messages.scrollHeight;

    button.addEventListener('click', () => {
        panel.style.display = 'flex';
        button.style.display = 'none';
        input.focus();
    });

    inputArea.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            panel.style.display = 'none';
            button.style.display = 'block';
            button.focus();
        }
    });

    closeBtn.addEventListener('click', () => {
        panel.style.display = 'none';
        button.style.display = 'block';
        button.focus();
    });

    inputArea.addEventListener('submit', async (e) => {
        e.preventDefault();
        const text = input.value.trim();
        if (!text) return;
        addMessage(text, true);
        input.value = '';
        
        const typing = document.createElement('div');
        typing.textContent = 'Escribiendo...';
        typing.style.color = '#888';
        typing.style.fontSize = '12px';
        typing.style.marginBottom = '10px';
        messages.appendChild(typing);
        messages.scrollTop = messages.scrollHeight;

        try {
            const res = await fetch(api + '/web/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ session_id: sessionId, text: text })
            });
            messages.removeChild(typing);
            if (!res.ok) {
                const err = await res.json();
                addMessage(err.detail || 'Error de conexión', false);
            } else {
                const data = await res.json();
                data.replies.forEach(r => addMessage(r, false));
            }
        } catch (err) {
            messages.removeChild(typing);
            addMessage('Error de conexión', false);
        }
    });
})();
