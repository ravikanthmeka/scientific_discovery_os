document.addEventListener('DOMContentLoaded', () => {
    const domainTags = document.querySelectorAll('.tag');
    const startBtn = document.getElementById('start-btn');
    const queryInput = document.getElementById('mission-query');
    const artifactContainer = document.getElementById('artifact-container');
    
    let currentDomain = 'Nuclear';
    let socket = null;

    // Domain selection
    domainTags.forEach(tag => {
        tag.addEventListener('click', () => {
            domainTags.forEach(t => t.classList.remove('active'));
            tag.classList.add('active');
            currentDomain = tag.getAttribute('data-domain');
            
            // Auto-fill query based on domain
            const queries = {
                'Nuclear': 'Design a safer fusion reactor containment field',
                'Quantum': 'Discover a new quantum error correction code',
                'Materials': 'Discover room-temperature superconductors',
                'Biology': 'Synthesize a protein to bind with microplastics',
                'Climate': 'Model optimal carbon capture array placement',
                'Mathematics': 'Find novel patterns in prime distribution',
                'Healthcare': 'Personalized mRNA vaccine sequence generation',
                'Energy': 'Optimize solid-state battery electrolyte',
                'Other': 'Explore novel cross-domain discovery patterns'
            };
            queryInput.value = queries[currentDomain];
        });
    });

    const addArtifact = (agentName, content) => {
        if (!content) return;
        const emptyText = document.querySelector('.empty-text');
        if (emptyText) emptyText.remove();

        const card = document.createElement('div');
        card.className = 'artifact-card';
        card.innerHTML = `
            <h4>${agentName} Artifact</h4>
            <p>${content}</p>
        `;
        artifactContainer.appendChild(card);
        artifactContainer.scrollTop = artifactContainer.scrollHeight;
    };

    const resetUI = () => {
        artifactContainer.innerHTML = '<p class="empty-text">No artifacts generated yet.</p>';
        document.querySelectorAll('.agent-node').forEach(node => {
            node.classList.remove('active', 'completed');
            node.querySelector('.status').textContent = 'Idle';
            node.querySelector('.log-output').textContent = 'Waiting...';
        });
        document.querySelectorAll('.connector').forEach(c => c.classList.remove('active'));
    };

    const handleMessage = (data) => {
        const { agent_id, status, log, artifact, agent_name } = data;
        
        if (agent_id === "SYSTEM") {
            if (status === "Completed") {
                startBtn.disabled = false;
                startBtn.textContent = 'Start New Discovery';
                addArtifact('SYSTEM', log);
                if (socket) socket.close();
            } else if (status === "Error") {
                startBtn.disabled = false;
                startBtn.textContent = 'Start New Discovery';
                addArtifact('SYSTEM ERROR', log);
                if (socket) socket.close();
            }
            return;
        }

        const node = document.getElementById(`agent-${agent_id}`);
        if (!node) return;

        const logOutput = node.querySelector('.log-output');
        const statusLabel = node.querySelector('.status');
        const nameLabel = node.querySelector('h3');

        if (status === "Processing") {
            node.classList.add('active');
            statusLabel.textContent = 'Processing';
            logOutput.textContent = log;
            if (agent_name) nameLabel.textContent = agent_name;
        } else if (status === "Completed") {
            node.classList.remove('active');
            node.classList.add('completed');
            statusLabel.textContent = 'Completed';
            logOutput.textContent = log;
            addArtifact(nameLabel.textContent, artifact);
            
            // Try to activate the connector to the next node
            const pipelineNodes = Array.from(document.querySelectorAll('.agent-node'));
            const currentIndex = pipelineNodes.indexOf(node);
            if (currentIndex !== -1 && currentIndex < pipelineNodes.length - 1) {
                const connectors = document.querySelectorAll('.connector');
                if (connectors[currentIndex]) {
                    connectors[currentIndex].classList.add('active');
                }
            }
        }
    };

    const runSimulation = () => {
        startBtn.disabled = true;
        startBtn.textContent = 'Mission in Progress...';
        resetUI();

        // Connect to FastAPI Backend
        socket = new WebSocket('ws://localhost:8000/ws/discovery');

        socket.onopen = () => {
            console.log("Connected to Scientific Discovery OS Backend");
            socket.send(JSON.stringify({
                domain: currentDomain,
                query: queryInput.value
            }));
        };

        socket.onmessage = (event) => {
            const data = JSON.parse(event.data);
            handleMessage(data);
        };

        socket.onerror = (error) => {
            console.error("WebSocket Error: ", error);
            startBtn.disabled = false;
            startBtn.textContent = 'Start New Discovery';
            addArtifact('SYSTEM ERROR', 'Failed to connect to backend server. Make sure FastAPI is running on port 8000.');
        };

        socket.onclose = () => {
            console.log("Disconnected from Backend");
        };
    };

    startBtn.addEventListener('click', runSimulation);
});
