import os
import random
from flask import Flask, render_template_string, jsonify, request

app = Flask(__name__)

# 初始化 136 張麻將牌（不含花牌，確保核心邏輯單純）
SUITS = [f"{i}萬" for i in range(1, 10)] + [f"{i}筒" for i in range(1, 10)] + [f"{i}條" for i in range(1, 10)]
HONORS = ["東", "南", "西", "北", "中", "發", "白"]
FULL_DECK = (SUITS + HONORS) * 4

# 遊戲全域狀態
game_state = {
    "deck": [],
    "seats": ["玩家1(東) [下方]", "機器人1(南) [右方]", "玩家2(西) [上方]", "機器人2(北) [左方]"],
    "hands": {0: [], 1: [], 2: [], 3: []},
    "discard_pile": [],
    "current_turn": 0,
    "log": ["點擊上方按鈕開始新遊戲..."],
}

def sort_by_series_only(hand):
    """
    自訂理牌邏輯：只按照系列（萬、筒、條、字）分類，同系列內『不按數字大小』排序
    """
    def get_series_score(card):
        if "萬" in card: return 1
        if "筒" in card: return 2
        if "條" in card: return 3
        return 4 # 字牌
    
    # 根據分類分數排序，分數相同（同系列）則維持原本在清單中的相對順序
    return sorted(hand, key=get_series_score)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>16張四人座遠端麻將</title>
    <style>
        body { font-family: Arial, sans-serif; background: #133a1b; color: white; text-align: center; margin: 0; padding: 10px; }
        .container { max-width: 800px; margin: auto; }
        
        /* 四人桌棋盤式佈局 */
        .mahjong-table {
            position: relative;
            width: 100%;
            max-width: 600px;
            height: 450px;
            background: #1e562c;
            border: 8px solid #0f2e17;
            border-radius: 10px;
            margin: 15px auto;
            box-shadow: inset 0 0 20px rgba(0,0,0,0.5);
        }
        
        /* 各個方位的座位樣式 */
        .seat { position: absolute; padding: 8px; background: rgba(0,0,0,0.4); border-radius: 5px; font-size: 14px; }
        .seat-top { top: 10px; left: 50%; transform: translateX(-50%); border: 1px solid #3498db; }
        .seat-bottom { bottom: 10px; left: 50%; transform: translateX(-50%); border: 1px solid #e67e22; }
        .seat-left { left: 10px; top: 50%; transform: translateY(-50%); }
        .seat-right { right: 10px; top: 50%; transform: translateY(-50%); }
        
        /* 牌桌中央海底（丟牌區） */
        .center-pile {
            position: absolute;
            top: 22%; left: 22%; width: 56%; height: 56%;
            background: #133a1b;
            border-radius: 5px;
            padding: 5px;
            overflow-y: auto;
            font-size: 14px;
            text-align: left;
            box-sizing: border-box;
        }
        
        .card { display: inline-block; padding: 10px 6px; background: #fff; color: #000; font-weight: bold; 
                border-radius: 4px; margin: 2px; border: 2px solid #ccc; cursor: pointer; font-size: 15px; box-shadow: 0 2px 4px rgba(0,0,0,0.3); }
        .card:hover { background: #eee; }
        .disabled { pointer-events: none; opacity: 0.6; background: #ddd; }
        
        .active-turn { border: 2px solid #f1c40f; box-shadow: 0 0 10px #f1c40f; background: rgba(241,196,15,0.2); }
        .log-box { background: rgba(0,0,0,0.6); height: 100px; overflow-y: auto; text-align: left; padding: 10px; font-size: 13px; border-radius: 5px; }
        button { padding: 10px 20px; font-size: 15px; margin: 5px; cursor: pointer; border-radius: 5px; border: none; background: #e67e22; color: white; font-weight: bold; }
        button:hover { background: #d35400; }
        .role-btn { background: #3498db; }
    </style>
    <script>
        let myId = null;
        function joinGame(id) {
            myId = id;
            document.getElementById('join-zone').style.display = 'none';
            document.getElementById('game-zone').style.display = 'block';
            document.getElementById('title').innerText = "遠端麻將 - 你的身份：" + (id == 0 ? "玩家1 (下方東位)" : "玩家2 (上方西位)");
            setInterval(updateStatus, 1000);
        }
        async function updateStatus() {
            let res = await fetch('/state');
            let data = await res.json();
            
            document.getElementById('log').innerHTML = data.log.join('<br>');
            document.getElementById('pile').innerText = data.discard_pile.join(' ｜ ');
            
            // 更新四個座位的牌數與輪到誰提示
            for(let i=0; i<4; i++) {
                let seatEl = document.getElementById('seat-' + i);
                let count = data.hands[i].length;
                if(i == data.current_turn) {
                    seatEl.className = `seat ${getSeatClass(i)} active-turn`;
                } else {
                    seatEl.className = `seat ${getSeatClass(i)}`;
                }
                
                if(i === 0 || i === 2) {
                    seatEl.innerHTML = `<b>${data.seats[i]}</b><br>剩餘 ${count} 張`;
                } else {
                    seatEl.innerHTML = `🤖<br>${data.seats[i]}<br>(${count}張)`;
                }
            }
            
            // 渲染目前操作玩家的手牌
            let handZone = document.getElementById('my-hand-zone');
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
        function getSeatClass(id) {
            if(id == 0) return 'seat-bottom';
            if(id == 1) return 'seat-right';
            if(id == 2) return 'seat-top';
            if(id == 3) return 'seat-left';
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
        <h2 id="title">🀄 台灣16張：遠端四人麻將桌 🀄</h2>
        <button onclick="restartGame()">新局 / 重設16張牌局</button>
        <hr style="border: 0.5px solid #2d663b;">
        
        <div id="join-zone">
            <h3>請選擇你的位置進入牌桌：</h3>
            <button class="role-btn" onclick="joinGame(0)">我是 玩家1 (坐下方)</button>
            <button class="role-btn" onclick="joinGame(2)">我是 玩家2 (坐上方)</button>
        </div>
        
        <div id="game-zone" style="display:none;">
            <div class="mahjong-table">
                <div id="seat-2" class="seat seat-top">玩家2(西) [上方]</div>
                <div id="seat-3" class="seat seat-left">機器人2(北) [左方]</div>
                <div id="seat-1" class="seat seat-right">機器人1(南) [右方]</div>
                <div id="seat-0" class="seat seat-bottom">玩家1(東) [下方]</div>
                
                <div class="center-pile">
                    <div style="color: #f1c40f; margin-bottom: 5px; font-weight: bold; border-bottom: 1px solid #2d663b;">【海底牌桌】</div>
                    <div id="pile"></div>
                </div>
            </div>

            <h4>【你的16張手牌】(依系列分類 / 內不排數字大小。輪到你時點擊出牌)</h4>
            <div id="my-hand-zone" style="min-height: 60px; background: rgba(0,0,0,0.2); padding: 10px; border-radius: 5px;"></div>
            
            <h4>【對局日誌】</h4>
            <div id="log" class="log-box"></div>
        </div>
    </div>
</body>
</html>
"""

def bot_action():
    """機器人自動摸牌與打牌"""
    while game_state["current_turn"] in [1, 3] and len(game_state["deck"]) > 0:
        turn = game_state["current_turn"]
        drawn = game_state["deck"].pop()
        game_state["hands"][turn].append(drawn)
        
        # 機器人也使用系列理牌
        game_state["hands"][turn] = sort_by_series_only(game_state["hands"][turn])
        
        # 簡單策略：優先打出單張字牌，否則隨機打
        bot_honors = [c for c in game_state["hands"][turn] if c in HONORS]
        discarded = bot_honors[0] if bot_honors else random.choice(game_state["hands"][turn])
        
        game_state["hands"][turn].remove(discarded)
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
        
        # 打牌後重新進行系列理牌
        game_state["hands"][p_id] = sort_by_series_only(game_state["hands"][p_id])
        game_state["log"].append(f"❌ {game_state['seats'][p_id]} 打出了 【{discarded}】")
        
        game_state["current_turn"] = (game_state["current_turn"] + 1) % 4
        
        # 觸發機器人回合
        bot_action()
        
        # 輪回人類玩家時，自動幫下一個玩家摸一張牌
        if len(game_state["deck"]) > 0 and game_state["current_turn"] in [0, 2]:
            next_p = game_state["current_turn"]
            drawn = game_state["deck"].pop()
            game_state["hands"][next_p].append(drawn)
            # 摸牌後理牌
            game_state["hands"][next_p] = sort_by_series_only(game_state["hands"][next_p])
            game_state["log"].append(f"👉 {game_state['seats'][next_p]} 摸了一張牌（第 17 張）")
            
        if len(game_state["deck"]) == 0:
            game_state["log"].append("🀄 牌拿完了，本局流局！")
            
    return jsonify({"status": "success"})

@app.route('/restart')
def restart():
    game_state["deck"] = FULL_DECK.copy()
    random.shuffle(game_state["deck"])
    game_state["discard_pile"] = []
    game_state["log"] = ["台灣16張新局開始！發給每人16張底牌。由 玩家1(東) 先攻。"]
    game_state["current_turn"] = 0
    
    # 初始發 16 張牌，並依照系列理牌
    for i in range(4):
        initial_hand = [game_state["deck"].pop() for _ in range(16)]
        game_state["hands"][i] = sort_by_series_only(initial_hand)
        
    # 東家（玩家1）多摸第 17 張牌開局
    drawn = game_state["deck"].pop()
    game_state["hands"][0].append(drawn)
    game_state["hands"][0] = sort_by_series_only(game_state["hands"][0])
    game_state["log"].append("👉 玩家1(東) 摸了第 17 張開局牌")
    return jsonify({"status": "success"})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
