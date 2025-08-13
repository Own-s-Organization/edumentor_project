document.addEventListener('DOMContentLoaded', () => {
    const sendBtn = document.getElementById('sendBtn');
    const userInput = document.getElementById('userInput');
    const chatWindow = document.querySelector('.chat-window');

    sendBtn.addEventListener('click', sendMessage);
    userInput.addEventListener('keypress', (event) => {
        if (event.key === 'Enter') {
            sendMessage();
        }
    });

    function sendMessage() {
        const userText = userInput.value.trim();
        if (userText) {
            // Create and append a new user message
            const userMessageDiv = document.createElement('div');
            userMessageDiv.className = 'message user-message';
            userMessageDiv.innerHTML = `<span class="message-text">${userText}</span>`;
            chatWindow.appendChild(userMessageDiv);

            // Scroll to the bottom
            chatWindow.scrollTop = chatWindow.scrollHeight;

            // Clear the input field
            userInput.value = '';

            // Optional: Simulate an AI response after a delay
            setTimeout(() => {
                const aiMessageDiv = document.createElement('div');
                aiMessageDiv.className = 'message ai-message';
                aiMessageDiv.innerHTML = `<span class="message-text">This is a simulated AI response to "${userText}".</span>`;
                chatWindow.appendChild(aiMessageDiv);
                chatWindow.scrollTop = chatWindow.scrollHeight;
            }, 1000);
        }
    }
});