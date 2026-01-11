import streamlit as st
import pandas as pd
import google.generativeai as genai
from PIL import Image
import json
import os

# --- 設定頁面 ---
st.set_page_config(page_title="Mezastar 檔案室", layout="wide", page_icon="🗃️")

# --- 設定資料庫檔案名稱 ---
DB_FILE = "mezastar_db.json"

# --- 函式：讀取與寫入資料庫 ---
def load_db():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            st.error(f"讀取資料庫失敗: {e}")
            return []
    return []

def save_db(data):
    try:
        with open(DB_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
    except Exception as e:
        st.error(f"寫入資料庫失敗: {e}")

# --- API Key 管理 ---
if "gemini_api_key" in st.secrets:
    api_key = st.secrets["gemini_api_key"]
else:
    api_key = st.sidebar.text_input("Google Gemini API Key (對戰分析用)", type="password")

if api_key:
    genai.configure(api_key=api_key)

# --- 資料庫初始化 ---
if 'inventory' not in st.session_state:
    st.session_state['inventory'] = load_db()

# --- 上傳元件重置金鑰初始化 ---
if 'uploader_key' not in st.session_state:
    st.session_state['uploader_key'] = 0

# --- 常數定義 ---
POKEMON_TYPES = [
    "一般", "火", "水", "草", "電", "冰", "格鬥", "毒", "地面", 
    "飛行", "超能力", "蟲", "岩石", "幽靈", "龍", "惡", "鋼", "妖精", "無"
]

SPECIAL_TAGS = [
    "無", "Mega進化", "Z招式", "極巨化", "太晶化", "特別聯手對戰", "雙重招式"
]

# --- 功能 1: 新增卡片 ---
def page_add_card():
    st.header("🗃️ 新增 Mezastar 卡片資料")
    
    col_preview, col_edit = st.columns([1, 2])
    
    with col_preview:
        st.subheader("1. 圖片上傳")
        
        current_key = st.session_state['uploader_key']
        
        front_file = st.file_uploader(
            "上傳【正面】(選取後立即讀取檔名)", 
            type=["jpg", "png", "jpeg"], 
            key=f"u_front_{current_key}"
        )
        
        back_file = st.file_uploader(
            "上傳【背面】", 
            type=["jpg", "png", "jpeg"], 
            key=f"u_back_{current_key}"
        )
        
        if front_file:
            st.image(Image.open(front_file), caption="正面預覽", use_container_width=True)
            
            if 'last_processed_file' not in st.session_state or st.session_state['last_processed_file'] != front_file.name:
                filename = os.path.splitext(front_file.name)[0]
                for suffix in ["_前", "_front", "正面"]:
                    if filename.endswith(suffix):
                        filename = filename.replace(suffix, "")
                        break
                
                st.session_state['card_name_input'] = filename
                st.session_state['last_processed_file'] = front_file.name
                st.rerun()

        if back_file:
            st.image(Image.open(back_file), caption="背面預覽", use_container_width=True)

    with col_edit:
        st.subheader("2. 資料編輯")
        
        with st.form("card_form", clear_on_submit=True):
            st.text_input("卡片名稱", key="card_name_input")
            st.selectbox("特殊能力", SPECIAL_TAGS, key="tag_input")
            
            st.markdown("---")
            st.markdown("**寶可夢屬性**")
            c1, c2 = st.columns(2)
            c1.selectbox("屬性 1", POKEMON_TYPES, key="t1_input")
            c2.selectbox("屬性 2", POKEMON_TYPES, index=len(POKEMON_TYPES)-1, key="t2_input")
            
            st.markdown("---")
            st.markdown("**招式資訊**")
            
            mc1_a, mc1_b = st.columns([2, 1])
            mc1_a.text_input("一般招式名稱", placeholder="例如：影子球", key="m1_name_input")
            mc1_b.selectbox("屬性", POKEMON_TYPES, key="m1_type_input")
            
            mc2_a, mc2_b = st.columns([2, 1])
            mc2_a.text_input("特殊/強力招式名稱", placeholder="例如：極巨幽魂", key="m2_name_input")
            mc2_b.selectbox("屬性", POKEMON_TYPES, key="m2_type_input")
            
            submitted = st.form_submit_button("💾 加入資料庫 (自動存檔)", type="primary")
            
            if submitted:
                name = st.session_state.get('card_name_input', '未命名')
                
                new_card = {
                    "name": name,
                    "tag": st.session_state.tag_input,
                    "type": st.session_state.t1_input,
                    "type2": st.session_state.t2_input,
                    "moves": [
                        {"name": st.session_state.m1_name_input, "type": st.session_state.m1_type_input},
                        {"name": st.session_state.m2_name_input, "type": st.session_state.m2_type_input}
                    ],
                    "power": 100
                }
                
                st.session_state['inventory'].append(new_card)
                save_db(st.session_state['inventory'])
                st.success(f"已新增並儲存：{name}")
                
                if 'last_processed_file' in st.session_state:
                    del st.session_state['last_processed_file']
                
                st.session_state['uploader_key'] += 1
                st.rerun()

    if st.session_state['inventory']:
        st.markdown("---")
        st.subheader(f"📋 目前卡匣 ({len(st.session_state['inventory'])} 張)")
        
        display_data = []
        for item in st.session_state['inventory']:
            moves_str = f"{item['moves'][0]['name']} / {item['moves'][1]['name']}"
            types_str = f"{item['type']}" + (f"/{item['type2']}" if item['type2'] != "無" else "")
            
            display_data.append({
                "名稱": item['name'],
                "屬性": types_str,
                "特殊能力": item['tag'],
                "招式": moves_str
            })
            
        st.dataframe(pd.DataFrame(display_data), use_container_width=True)
        
        json_str = json.dumps(st.session_state['inventory'], ensure_ascii=False, indent=4)
        st.download_button("⬇️ 手動下載備份 (.json)", json_str, DB_FILE)

# --- 功能 2: 對戰分析 (全新升級版) ---
TYPE_CHART = {
    "一般": {"岩石": 0.5, "幽靈": 0, "鋼": 0.5},
    "火": {"草": 2, "冰": 2, "蟲": 2, "鋼": 2, "水": 0.5, "火": 0.5, "岩石": 0.5, "龍": 0.5},
    "水": {"火": 2, "地面": 2, "岩石": 2, "水": 0.5, "草": 0.5, "龍": 0.5},
    "電": {"水": 2, "飛行": 2, "地面": 0, "電": 0.5, "草": 0.5, "龍": 0.5},
    "草": {"水": 2, "地面": 2, "岩石": 2, "火": 0.5, "草": 0.5, "毒": 0.5, "飛行": 0.5, "蟲": 0.5, "龍": 0.5, "鋼": 0.5},
    "冰": {"草": 2, "地面": 2, "飛行": 2, "龍": 2, "火": 0.5, "冰": 0.5, "鋼": 0.5, "水": 0.5},
    "格鬥": {"一般": 2, "冰": 2, "岩石": 2, "惡": 2, "鋼": 2, "幽靈": 0, "毒": 0.5, "飛行": 0.5, "超能力": 0.5, "蟲": 0.5, "妖精": 0.5},
    "毒": {"草": 2, "妖精": 2, "毒": 0.5, "地面": 0.5, "幽靈": 0.5, "岩石": 0.5, "鋼": 0},
    "地面": {"火": 2, "電": 2, "毒": 2, "岩石": 2, "鋼": 2, "飛行": 0, "草": 0.5, "蟲": 0.5},
    "飛行": {"草": 2, "格鬥": 2, "蟲": 2, "電": 0.5, "岩石": 0.5, "鋼": 0.5},
    "超能力": {"格鬥": 2, "毒": 2, "超能力": 0.5, "惡": 0, "鋼": 0.5},
    "蟲": {"草": 2, "超能力": 2, "惡": 2, "火": 0.5, "飛行": 0.5, "幽靈": 0.5, "格鬥": 0.5, "毒": 0.5, "鋼": 0.5, "妖精": 0.5},
    "岩石": {"火": 2, "冰": 2, "飛行": 2, "蟲": 2, "格鬥": 0.5, "地面": 0.5, "鋼": 0.5},
    "幽靈": {"超能力": 2, "幽靈": 2, "一般": 0, "惡": 0.5},
    "龍": {"龍": 2, "鋼": 0.5, "妖精": 0},
    "惡": {"幽靈": 2, "超能力": 2, "格鬥": 0.5, "妖精": 0.5, "惡": 0.5},
    "鋼": {"冰": 2, "岩石": 2, "妖精": 2, "火": 0.5, "水": 0.5, "電": 0.5, "鋼": 0.5},
    "妖精": {"格鬥": 2, "龍": 2, "惡": 2, "毒": 0.5, "鋼": 0.5, "火": 0.5}
}

def get_effectiveness(attacker_type, defender_type):
    """計算單一屬性攻擊對單一屬性防禦的倍率"""
    if defender_type == "無" or attacker_type == "無": return 1.0
    if attacker_type not in TYPE_CHART: return 1.0
    return TYPE_CHART[attacker_type].get(defender_type, 1.0)

def calculate_dual_effectiveness(attacker_type, def_t1, def_t2):
    """計算對雙屬性防禦的總倍率"""
    eff1 = get_effectiveness(attacker_type, def_t1)
    eff2 = get_effectiveness(attacker_type, def_t2)
    return eff1 * eff2

def page_battle():
    st.header("⚔️ 對戰分析 (3 vs 3)")
    st.info("請輸入三位對手的屬性與招式，AI 將計算攻防一體最佳陣容。")
    
    # 建立三個對手的輸入區塊
    opponents = []
    cols = st.columns(3)
    
    for i in range(3):
        with cols[i]:
            st.markdown(f"### 🥊 對手 {i+1}")
            t1 = st.selectbox(f"屬性 1", POKEMON_TYPES, index=0, key=f"op{i}_t1")
            t2 = st.selectbox(f"屬性 2", POKEMON_TYPES, index=len(POKEMON_TYPES)-1, key=f"op{i}_t2") # 預設無
            move_type = st.selectbox(f"招式屬性 (攻擊我方)", POKEMON_TYPES, index=0, key=f"op{i}_move")
            opponents.append({"t1": t1, "t2": t2, "move": move_type})

    st.markdown("---")
    
    if st.button("🚀 計算最佳攻防隊伍", type="primary"):
        if not st.session_state['inventory']:
            st.error("卡匣是空的！請先建立資料。")
            return

        recs = []
        
        # 針對每一張我的卡片進行評分
        for card in st.session_state['inventory']:
            total_offense_score = 0
            total_defense_penalty = 0
            best_move_display = ""
            
            # 1. 攻擊分數 (我打對手)
            # 我們假設這張卡片會對上這三隻對手，取平均效益或最大效益
            # 這裡採取「累積效益」，因為一場戰鬥可能會打多隻
            
            my_best_move_idx = 0
            my_best_move_power = 0
            
            # 先找出這張卡哪一招最強 (針對這三個對手的平均表現)
            for idx, move in enumerate(card['moves']):
                if not move['name']: continue
                
                move_score_sum = 0
                for opp in opponents:
                    eff = calculate_dual_effectiveness(move['type'], opp['t1'], opp['t2'])
                    move_score_sum += eff
                
                # 簡單加權：第二招通常比較痛
                base_power = 120 if idx == 1 else 100
                current_power = base_power * move_score_sum
                
                if current_power > my_best_move_power:
                    my_best_move_power = current_power
                    my_best_move_idx = idx
                    best_move_display = f"{move['name']}({move['type']})"

            # 最終攻擊分數
            total_offense_score = my_best_move_power
            
            # 2. 防禦分數 (對手打我)
            # 計算三個對手的招式打我有沒有特別痛
            # 數值越小代表防禦越好 (受傷倍率)
            defense_multipliers = []
            for opp in opponents:
                # 我方防禦屬性
                my_t1 = card['type']
                my_t2 = card.get('type2', '無')
                dmg_taken = calculate_dual_effectiveness(opp['move'], my_t1, my_t2)
                defense_multipliers.append(dmg_taken)
            
            # 取最大受傷倍率來當作風險 (避免被秒殺)
            max_risk = max(defense_multipliers)
            
            # 3. 綜合評分公式
            # 分數 = 攻擊力 / 風險係數
            # 如果風險是 4倍(極大)，分數會除以4；如果是 0.25(減傷)，分數會乘以4
            # 為了避免除以0 (免疫)，將0視為極小的數 0.1
            risk_factor = max_risk if max_risk > 0 else 0.1
            
            final_score = total_offense_score / risk_factor
            
            # 特殊能力加權
            if card['tag'] != '無': final_score *= 1.2
            
            recs.append({
                "name": card['name'],
                "tag": card['tag'],
                "move": best_move_display,
                "score": final_score,
                "risk": max_risk
            })

        # 排序
        recs.sort(key=lambda x: x['score'], reverse=True)

        # 挑選不重複 Tag 的前三名
        final_team = []
        used_tags = set()
        
        for r in recs:
            if len(final_team) >= 3: break
            if r['tag'] != '無' and r['tag'] in used_tags: continue
            final_team.append(r)
            if r['tag'] != '無': used_tags.add(r['tag'])
            
        # 補滿
        if len(final_team) < 3:
            for r in recs:
                if len(final_team) >= 3: break
                if r not in final_team: final_team.append(r)

        # 顯示結果
        st.subheader("🏆 推薦出戰陣容")
        
        cols = st.columns(3)
        for i, p in enumerate(final_team):
            with cols[i]:
                risk_text = "普通"
                if p['risk'] >= 2: risk_text = "⚠️ 危險"
                elif p['risk'] <= 0.5: risk_text = "🛡️ 堅硬"
                elif p['risk'] == 0: risk_text = "✨ 免疫"
                
                st.success(f"""
                **第 {i+1} 棒**
                
                ### {p['name']}
                
                * **能力**: {p['tag']}
                * **建議招式**: {p['move']}
                * **防禦評估**: {risk_text} (最大受傷 x{p['risk']})
                """)

# --- 主程式切換 ---
page = st.sidebar.radio("模式", ["新增卡片", "對戰分析"])

if page == "新增卡片":
    page_add_card()
else:
    page_battle()