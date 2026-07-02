import os
import random
from flask import Flask, render_template_string, jsonify, request

app = Flask(__name__)

# 初始化 136 張麻將牌
SUITS = [f"{i}萬" for i in range(1, 10)] + [f"{i}筒" for i in range(1, 10)] + [f"{i}條" for i in range(1, 10)]
HONORS = ["東", "南", "西", "北", "中", "發", "白"]
FULL_DECK = (SUITS + HONORS) * 4

# 遊戲全域狀態
game_state = {
    "deck": [],
    "seats": ["玩家1(東)", "機器人1(南)", "玩家2(西)", "機器人2(北)"],
    "hands": {0: [], 1: [], 2: [], 3: []},
    "discard_pile": [],
    "current_turn": 0,
    "drawn_card": None,
    "log": ["點擊上方按鈕開始新遊戲..."],
}

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>遠端連線麻將</title>
    <style>
        body { font-family: Arial, sans-serif; background: #1a4221; color: white; text-align: center; margin: 0; padding: 10px; }
        .container { max-width: 600px; margin: auto; }
        .card { display: inline-block; padding: 12px 8px; background: #fff; color: #000; font-weight: bold; 
                border-radius: 4px; margin: 3px; border: 2px solid #ccc; cursor: pointer; font-size: 16px; box-shadow: 0 2px 4px rgba(0,0,0,0.2); }
        .card:hover { background: #eee; }
        .disabled { pointer-events: none; opacity: 0.5; background: #ddd; }
        .pile { background: #0f2e17; min-height: 80px; padding: 10px; margin: 10px 0; border-radius: 5px; border: 1px solid #2d663b; word-break: break-all; }
        .log-box { background: rgba(0,0,0,0.6); height: 120px; overflow-y: auto; text-align: left; padding: 10px; font-size: 14px; border-radius: 5px; }
        button { padding: 12px 24px; font-size: 16px; margin: 8px; cursor: pointer; border-radius: 5px; border: none; background: #e67e22; color: white; font-weight: bold; }
        button:hover { background: #d35400; }
        .role-btn { background: #3498db; }
        .role-btn:hover { background: #2980b9; }
    </style>
    <script>
        let myId = null;
        function joinGame(id) {
            myId = id;
            document.getElementById('join-zone').style.display = 'none';
            document.getElementById('game-zone').style.display = 'block';
            document.getElementById('title').innerText = "你的身份：" + (id == 0 ? "玩家1(東位)" : "玩家2(西位)");
            setInterval(updateStatus, 1000); // 每秒自動更新畫面
        }
        async function updateStatus() {
            let res = await fetch('/state');
            let data = await res.json();
            
            document.getElementById('log').innerHTML = data.log.join('<br>');
            document.getElementById('turn-info').innerText = "目前輪到：" + data.seats[data.current_turn];
            document.getElementById('pile').innerText = data.discard_pile.join(' ｜ ');
            
            let handZone = document.getElementById('hand');
            handZone.innerHTML = "";
            let myHand = data.hands[myId] || [];
            let isMyTurn = (data.current_turn == myId);
            
            myHand.forEach((card, index) => {
                let btn = document.createElement('div');
                btn.className = "card" + (isMyTurn ? "" : " disabled");
                btn.innerText = card;
                btn.onclick = () => discard(index);
                handZone.appendChild(btn);
            });
        }
        async function discard(index) {
            await fetch('/discard?player_id=' + myId + '&index=' + index);
            updateStatus();
        }
        async function restartGame() {
            await fetch('/restart');
        }
    </script>
</head>
<body>
    <div class="container">
        <h2 id="title">🀄 遠端連線麻將 🀄</h2>
        <button onclick="restartGame()">新局 / 重設遊戲</button>
        <hr style="border: 0.5px solid #2d663b;">
        <div id="join-zone">
            <h3>請選擇你的位置：</h3>
            <button class="role-btn" onclick="joinGame(0)">我是 玩家1 (電腦端)</button>
            <button class="role-btn" onclick="joinGame(2)">我是 玩家2 (遠端朋友平板)</button>
        </div>
        
        <div id="game-zone" style="display:none;">
            <h3 id="turn-info" style="color: #f1c40f;">-</h3>
            <h4>【海底牌】</h4>
            <div id="pile" class="pile"></div>
            <h4>【你的手牌】(輪到你時點擊即可出牌)</h4>
            <div id="hand"></div>
            <h4>【對局日誌】</h4>
            <div id="log" class="log-box"></div>
        </div>
    </div>
</body>
</html>
"""

def bot_action():
    """機器人自動摸牌與打牌邏輯"""
    while game_state["current_turn"] in [1, 3] and len(game_state["deck"]) > 0:
        turn = game_state["current_turn"]
        drawn = game_state["deck"].pop()
        game_state["hands"][turn].append(drawn)
        
        bot_honors = [c for c in game_state["hands"][turn] if c in HONORS]
        discarded = bot_honors[0] if bot_honors else random.choice(game_state["hands"][turn])
        
        game_state["hands"][turn].remove(discarded)
        game_state["hands"][turn].sort()
        game_state["discard_pile"].append(discarded)
        
        game_state["log"].append(f"🤖 {game_state['seats'][turn]} 摸牌後，打出了 【{discarded}】")
        game_state["current_turn"] = (game_state["current_turn"] + 1) % 4

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/state')
def get_state():
    return jsonify(game_state)

@app.route('/discard')
def discard():
    p_id = int(request.args.get('player_id'))
    idx = int(request.args.get('index'))
    
    if game_state["current_turn"] == p_id and len(game_state["deck"]) > 0:
        discarded = game_state["hands"][p_id].pop(idx)
        game_state["discard_pile"].append(discarded)
        game_state["hands"][p_id].sort()
        game_state["log"].append(f"❌ {game_state['seats'][p_id]} 打出了 【{discarded}】")
        
        game_state["current_turn"] = (game_state["current_turn"] + 1) % 4
        
        # 觸發機器人
        bot_action()
        
        # 輪回人類玩家時，幫他摸一張牌
        if len(game_state["deck"]) > 0 and game_state["current_turn"] in [0, 2]:
            next_p = game_state["current_turn"]
            drawn = game_state["deck"].pop()
            game_state["hands"][next_p].append(drawn)
            game_state["log"].append(f"👉 {game_state['seats'][next_p]} 摸了一張牌")
            
        if len(game_state["deck"]) == 0:
            game_state["log"].append("🀄 牌拿完了，本局流局！")
            
    return jsonify({"status": "success"})

@app.route('/restart')
def restart():
    game_state["deck"] = FULL_DECK.copy()
    random.shuffle(game_state["deck"])
    game_state["discard_pile"] = []
    game_state["log"] = ["新對局開始！由 玩家1(東) 先攻。"]
    game_state["current_turn"] = 0
    
    for i in range(4):
        game_state["hands"][i] = sorted([game_state["deck"].pop() for _ in range(13)])
        
    drawn = game_state["deck"].pop()
    game_state["hands"][0].append(drawn)
    game_state["log"].append("👉 玩家1(東) 摸了一張牌")
    return jsonify({"status": "success"})

if __name__ == "__main__":
    # 讀取雲端平台指定的 Port
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
