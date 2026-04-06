let ws = new WebSocket("ws://localhost:8000/ws");

let chat = document.getElementById("chat");

ws.onmessage = (event) => {
    let msg = document.createElement("div");
    msg.textContent = event.data;
    msg.className = "bg-gray-700 p-2 rounded";
    chat.appendChild(msg);
    chat.scrollTop = chat.scrollHeight;
};

function send() {
    let input = document.getElementById("input");
    
    let userMsg = document.createElement("div");
    userMsg.textContent = "🧑 " + input.value;
    userMsg.className = "bg-blue-600 p-2 rounded";
    chat.appendChild(userMsg);

    ws.send(input.value);
    input.value = "";
}

function newChat() {
    chat.innerHTML = "";
}