import os
import random
from flask import Flask, render_template_string, jsonify, request

app = Flask(__name__)

# 初始化 136 張麻將牌
SUITS = [f"{i}萬" for i in range(1, 10)] + [f"{i}筒" for i in range(1, 10)] + [f"{i}條" for i in range(1, 10)]
HONORS = ["東", "南", "西", "北", "中", "發", "白"]
FULL_DECK = (SUITS + HONORS) * 4

game_state = {
    "deck": [],
    "seats": ["玩家1(東)", "機器人1(南)", "玩家2(西)", "機器人2(北)"],
    "hands": {0: [], 1: [], 2: [], 3: []},
    "discard_pile": [],
    "current_turn": 0,
    "log": ["點擊上方按鈕開始新遊戲..."],
}

def sort_by_series_only(hand):
    """自訂理牌：按萬筒條字分類，內部維持摸牌順序不排大小"""
    def get_series_score(card):
        if "萬" in card: return 1
        if "筒" in card: return 2
        if "條" in card: return 3
        return 4
    return sorted(hand, key=get_series_score)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>3D擬真四人連線麻將桌</title>
    <style>
        body { font-family: 'PingFang TC', sans-serif; background: #0b1d12; color: white; text-align: center; margin: 0; padding: 10px; }
        .container { max-width: 900px; margin: auto; }
        
        /* 擬真綠色麻將桌主體 */
        .mahjong-table {
            position: relative;
            width: 100%;
            max-width: 650px;
            height: 650px;
            background: #174a26;
            border: 16px solid #2d1a0d; /* 木質邊框 */
            border-radius: 20px;
            margin: 20px auto;
            box-shadow: 0 10px 30px rgba(0,0,0,0.8), inset 0 0 40px rgba(0,0,0,0.6);
            overflow: hidden;
        }
        
        /* 牌桌中心：正方形海底丟牌區 */
        .table-center {
            position: absolute;
            top: 25%; left: 25%; width: 50%; height: 50%;
            background: #11361c;
            border: 4px solid #0b2212;
            border-radius: 8px;
            box-shadow: inset 0 0 15px rgba(0,0,0,0.5);
            padding: 10px;
            box-sizing: border-box;
            display: flex;
            flex-direction: column;
        }
        .center-title { font-size: 12px; color: #8ba894; font-weight: bold; border-bottom: 1px solid #1a4d2b; padding-bottom: 3px; }
        .discard-grid { flex: 1; padding-top: 5px; display: flex; flex-wrap: wrap; align-content: flex-start; gap: 4px; overflow-y: auto; }
        
        /* 經典麻將造型 */
        .mj-card {
            display: inline-block; width: 26px; height: 36px; background: #fdfdfd; color: #000; 
            font-weight: bold; text-align: center; line-height: 34px; font-size: 14px;
            border-radius: 4px; border-bottom: 3px solid #148037; border-right: 1px solid #ccc;
            box-shadow: 1px 2px 3px rgba(0,0,0,0.4); box-sizing: border-box;
        }
        .mj-card.suit-man { color: #cc0000; }
        .mj-card.suit-tong { color: #0066cc; }
        .mj-card.suit-tiao { color: #009933; }
        .mj-card.suit-zi { color: #cc6600; }
        
        /* 他人蓋著的牌（背面） */
        .mj-back {
            display: inline-block; background: #158f3b; border: 2px solid #fff;
            border-radius: 3px; box-shadow: 0 2px 4px rgba(0,0,0,0.4); box-sizing: border-box;
        }
        
        /* 四個座位的絕對定位與旋轉，達成圍桌感 */
        .player-zone { position: absolute; display: flex; justify-content: center; align-items: center; }
        
        /* 下方：我自己（玩家1） */
        .zone-bottom { bottom: 15px; left: 0; width: 100%; flex-direction: column; }
        .zone-bottom .hand-cards { display: flex; justify-content: center; width: 90%; flex-wrap: wrap; }
        .zone-bottom .mj-card { width: 32px; height: 44px; line-height: 42px; font-size: 18px; margin: 2px; cursor: pointer; transition: transform 0.1s; }
        .zone-bottom .mj-card:hover { transform: translateY(-8px); background: #fffdf0; }
        .zone-bottom .mj-card.disabled { pointer-events: none; opacity: 0.7; transform: none; background: #e0e0e0; }

        /* 上方：對家（玩家2） */
        .zone-top { top: 15px; left: 0; width: 100%; flex-direction: column-reverse; }
        .zone-top .mj-back { width: 22px; height: 30px; margin: 1px; }
        
        /* 左方：上家 */
        .zone-left { left: 15px; top: 0; height: 100%; flex-direction: row; }
        .zone-left .hand-cards { display: flex; flex-direction: column; }
        .zone-left .mj-back { width: 30px; height: 22px; margin: 1px; }

        /* 右方：下家 */
        .zone-right { right: 15px; top: 0; height: 100%; flex-direction: row-reverse; }
        .zone-right .hand-cards { display: flex; flex-direction: column; }
        .zone-right .mj-back { width: 30px; height: 22px; margin: 1px; }
        
        /* 玩家標籤與發光回合提示 */
        .player-tag { background: rgba(0,0,0,0.7); padding: 4px 10px; border-radius: 12px; font-size: 12px; color: #ccc; margin: 5px; border: 1px solid #444; }
        .active-turn .player-tag { border-color: #f1c40f; color: #f1c40f; box-shadow: 0 0 10px #f1c40f; background: rgba(241,196,15,0.2); }
        
        .log-box { background: rgba(0,0,0,0.6); height: 120px; overflow-y: auto; text-align: left; padding: 10px; font-size: 13px; border-radius: 5px; border: 1px solid #222; }
        button { padding: 12px 24px; font-size: 15px; margin: 5px; cursor: pointer; border-radius: 5px; border: none; background: #e67e22; color: white; font-weight: bold; box-shadow: 0 3px 6px rgba(0,0,0,0.3); }
        button:hover { background: #d35400; }
        .role-btn { background: #3498db; }
    </style>
    <script>
        let myId = null;
        function joinGame(id) {
            myId = id;
            document.getElementById('join-zone').style.display = 'none';
            document.getElementById('game-zone').style.display = 'block';
            setInterval(updateStatus, 1000);
        }
        
        function getCardClass(card) {
            if(card.includes("萬")) return "mj-card suit-man";
            if(card.includes("筒")) return "mj-card suit-tong";
            if(card.includes("條")) return "mj-card suit-tiao";
            return "mj-card suit-zi";
        }

        async function updateStatus() {
            let res = await fetch('/state');
            let data = await res.json();
            
            document.getElementById('log').innerHTML = data.log.join('<br>');
            
            // 渲染中央海底牌
            let grid = document.getElementById('discard-grid');
            grid.innerHTML = "";
            data.discard_pile.forEach(card => {
                let div = document.createElement('div');
                div.className = getCardClass(card);
                div.innerText = card;
                grid.appendChild(div);
            });
            
            // 根據你是玩家1(0)還是玩家2(2)，來決定誰坐下面，誰坐上面（視角對調）
            let mapping = {};
            if (myId == 0) {
                mapping = { 0: 'bottom', 1: 'right', 2: 'top', 3: 'left' };
                document.getElementById('identity-title').innerText = "🀄 你的位置：下方【東家】";
            } else {
                mapping = { 2: 'bottom', 3: 'right', 0: 'top', 1: 'left' };
                document.getElementById('identity-title').innerText = "🀄 你的位置：下方【西家】";
            }
            
            // 更新四個方位的UI
            for(let i=0; i<4; i++) {
                let pos = mapping[i];
                let zone = document.getElementById('zone-' + pos);
                let tag = document.getElementById('tag-' + pos);
                let cardsDiv = document.getElementById('cards-' + pos);
                
                // 標題與牌數說明
                let roleName = (i == myId) ? "【你自己】" : data.seats[i];
                tag.innerText = roleName + ` (${data.hands[i].length}張)`;
                
                // 當前輪到提示
                if(i == data.current_turn) {
                    zone.className = `player-zone zone-${pos} active-turn`;
                } else {
                    zone.className = `player-zone zone-${pos}`;
                }
                
                // 渲染手牌
                cardsDiv.innerHTML = "";
                if(pos === 'bottom') {
                    // 最下方是自己的手牌：明牌顯示
                    let isMyTurn = (data.current_turn == myId);
                    data.hands[myId].forEach((card, index) => {
                        let btn = document.createElement('div');
                        btn.className = getCardClass(card) + (isMyTurn ? "" : " disabled");
                        btn.innerText = card;
                        btn.onclick = () => discard(index);
                        cardsDiv.appendChild(btn);
                    });
                } else {
                    // 其他三家圍桌：暗牌（顯示牌背）
                    let count = data.hands[i].length;
                    for(let c=0; c<count; c++) {
                        let back = document.createElement('div');
                        back.className = "mj-back";
                        cardsDiv.appendChild(back);
                    }
                }
            }
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
        <h2>🀄 正宗台灣16張：3D擬真四人麻將桌 🀄</h2>
        <button onclick="restartGame()">重新洗牌 / 開新局</button>
        <h3 id="identity-title" style="color: #f1c40f;"></h3>
        
        <div id="join-zone">
            <h3 style="background: rgba(255,255,255,0.1); padding: 15px; border-radius: 8px;">請選擇一個位置入座開打：</h3>
            <button class="role-btn" onclick="joinGame(0)">我是 玩家1 (東家)</button>
            <button class="role-btn" onclick="joinGame(2)">我是 玩家2 (西家)</button>
        </div>
        
        <div id="game-zone" style="display:none;">
            <div class="mahjong-table">
                
                <div id="zone-top" class="player-zone zone-top">
                    <div id="tag-top" class="player-tag"></div>
                    <div id="cards-top" class="hand-cards"></div>
                </div>
                
                <div id="zone-left" class="player-zone zone-left">
                    <div id="tag-left" class="player-tag"></div>
                    <div id="cards-left" class="hand-cards"></div>
                </div>
                
                <div id="zone-right" class="player-zone zone-right">
                    <div id="cards-right" class="hand-cards"></div>
                    <div id="tag-right" class="player-tag"></div>
                </div>
                
                <div class="table-center">
                    <div class="center-title">【 海 底 丟 牌 桌 】</div>
                    <div id="discard-grid" class="discard-grid"></div>
                </div>
                
                <div id="zone-bottom" class="player-zone zone-bottom">
                    <div id="cards-bottom" class="hand-cards"></div>
                    <div id="tag-bottom" class="player-tag"></div>
                </div>
                
            </div>
            
            <h4>【對局日誌】</h4>
            <div id="log" class="log-box"></div>
        </div>
    </div>
</body>
</html><html>
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
