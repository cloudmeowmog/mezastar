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

# --- 初始化輸入框的 Session State (避免 KeyError) ---
defaults = {
    "card_name_input": "",
    "tag_input": "無",
    "t1_input": "一般",
    "t2_input": "無",
    "m1_name_input": "",
    "m1_type_input": "一般",
    "m2_name_input": "",
    "m2_type_input": "一般",
    "save_success_msg": "" # 用來顯示存檔成功的訊息
}
for key, val in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = val

# --- 常數定義 ---
POKEMON_TYPES = [
    "一般", "火", "水", "草", "電", "冰", "格鬥", "毒", "地面", 
    "飛行", "超能力", "蟲", "岩石", "幽靈", "龍", "惡", "鋼", "妖精", "無"
]

SPECIAL_TAGS = [
    "無", "Mega進化", "Z招式", "極巨化", "太晶化", "特別聯手對戰", "雙重招式"
]

# --- 關鍵修正：存檔的回呼函式 (Callback) ---
# 這個函式會在按鈕按下的瞬間執行，早於畫面重新渲染，所以可以安全地清空欄位
def save_card_callback():
    # 1. 取得目前輸入框的值
    name = st.session_state['card_name_input']
    if not name: name = "未命名"
    
    # 2. 建立新卡片資料
    new_card = {
        "name": name,
        "tag": st.session_state['tag_input'],
        "type": st.session_state['t1_input'],
        "type2": st.session_state['t2_input'],
        "moves": [
            {"name": st.session_state['m1_name_input'], "type": st.session_state['m1_type_input']},
            {"name": st.session_state['m2_name_input'], "type": st.session_state['m2_type_input']}
        ],
        "power": 100
    }
    
    # 3. 存檔
    st.session_state['inventory'].append(new_card)
    save_db(st.session_state['inventory'])
    
    # 4. 設定成功訊息 (讓主程式顯示)
    st.session_state['save_success_msg'] = f"已新增並儲存：{name}"
    
    # 5. 清空輸入框狀態 (在 Callback 裡做是安全的)
    st.session_state['card_name_input'] = ""
    st.session_state['tag_input'] = "無"
    st.session_state['t1_input'] = "一般"
    st.session_state['t2_input'] = "無"
    st.session_state['m1_name_input'] = ""
    st.session_state['m1_type_input'] = "一般"
    st.session_state['m2_name_input'] = ""
    st.session_state['m2_type_input'] = "一般"
    
    # 6. 清除檔案處理紀錄 & 重置上傳按鈕
    if 'last_processed_file' in st.session_state:
        del st.session_state['last_processed_file']
    st.session_state['uploader_key'] += 1

# --- 功能 1: 新增卡片 ---
def page_add_card():
    st.header("🗃️ 新增 Mezastar 卡片資料")
    
    col_preview, col_edit = st.columns([1, 2])
    
    with col_preview:
        st.subheader("1. 圖片上傳")
        
        # 使用動態 Key，確保每次新增後上傳元件會重置
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
        
        # --- 自動讀取檔名邏輯 ---
        if front_file:
            st.image(Image.open(front_file), caption="正面預覽", use_container_width=True)
            
            # 檢查是否為新圖片
            if 'last_processed_file' not in st.session_state or st.session_state['last_processed_file'] != front_file.name:
                
                # 解析檔名
                filename = os.path.splitext(front_file.name)[0]
                for suffix in ["_前", "_front", "正面"]:
                    if filename.endswith(suffix):
                        filename = filename.replace(suffix, "")
                        break
                
                # 更新輸入框狀態 (這裡直接改是安全的，因為之後會 rerun)
                st.session_state['card_name_input'] = filename
                st.session_state['last_processed_file'] = front_file.name
                st.rerun()

        if back_file:
            st.image(Image.open(back_file), caption="背面預覽", use_container_width=True)

    with col_edit:
        st.subheader("2. 資料編輯")
        
        # 如果有成功訊息，顯示出來然後清空
        if st.session_state['save_success_msg']:
            st.success(st.session_state['save_success_msg'])
            st.session_state['save_success_msg'] = "" # 只顯示一次

        with st.form("card_form"):
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
            
            # 關鍵修改：使用 on_click 綁定存檔函式
            st.form_submit_button("💾 加入資料庫 (自動存檔)", type="primary", on_click=save_card_callback)

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

# --- 功能 2: 對戰分析 ---
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
    if defender_type == "無" or attacker_type == "無": return 1.0
    if attacker_type not in TYPE_CHART: return 1.0
    return TYPE_CHART[attacker_type].get(defender_type, 1.0)

def calculate_dual_effectiveness(attacker_type, def_t1, def_t2):
    eff1 = get_effectiveness(attacker_type, def_t1)
    eff2 = get_effectiveness(attacker_type, def_t2)
    return eff1 * eff2

def page_battle():
    st.header("⚔️ 對戰分析 (3 vs 3)")
    st.info("請輸入三位對手的屬性與招式，AI 將計算攻防一體最佳陣容。")
    
    opponents = []
    cols = st.columns(3)
    
    for i in range(3):
        with cols[i]:
            st.markdown(f"### 🥊 對手 {i+1}")
            t1 = st.selectbox(f"屬性 1", POKEMON_TYPES, index=0, key=f"op{i}_t1")
            t2 = st.selectbox(f"屬性 2", POKEMON_TYPES, index=len(POKEMON_TYPES)-1, key=f"op{i}_t2")
            move_type = st.selectbox(f"招式屬性 (攻擊我方)", POKEMON_TYPES, index=0, key=f"op{i}_move")
            opponents.append({"t1": t1, "t2": t2, "move": move_type})

    st.markdown("---")
    
    if st.button("🚀 計算最佳攻防隊伍", type="primary"):
        if not st.session_state['inventory']:
            st.error("卡匣是空的！請先建立資料。")
            return

        recs = []
        for card in st.session_state['inventory']:
            total_offense_score = 0
            best_move_display = ""
            
            my_best_move_idx = 0
            my_best_move_power = 0
            
            for idx, move in enumerate(card['moves']):
                if not move['name']: continue
                
                move_score_sum = 0
                for opp in opponents:
                    eff = calculate_dual_effectiveness(move['type'], opp['t1'], opp['t2'])
                    move_score_sum += eff
                
                base_power = 120 if idx == 1 else 100
                current_power = base_power * move_score_sum
                
                if current_power > my_best_move_power:
                    my_best_move_power = current_power
                    my_best_move_idx = idx
                    best_move_display = f"{move['name']}({move['type']})"

            total_offense_score = my_best_move_power
            
            defense_multipliers = []
            for opp in opponents:
                my_t1 = card['type']
                my_t2 = card.get('type2', '無')
                dmg_taken = calculate_dual_effectiveness(opp['move'], my_t1, my_t2)
                defense_multipliers.append(dmg_taken)
            
            max_risk = max(defense_multipliers)
            risk_factor = max_risk if max_risk > 0 else 0.1
            final_score = total_offense_score / risk_factor
            
            if card['tag'] != '無': final_score *= 1.2
            
            recs.append({
                "name": card['name'],
                "tag": card['tag'],
                "move": best_move_display,
                "score": final_score,
                "risk": max_risk
            })

        recs.sort(key=lambda x: x['score'], reverse=True)

        final_team = []
        used_tags = set()
        
        for r in recs:
            if len(final_team) >= 3: break
            if r['tag'] != '無' and r['tag'] in used_tags: continue
            final_team.append(r)
            if r['tag'] != '無': used_tags.add(r['tag'])
            
        if len(final_team) < 3:
            for r in recs:
                if len(final_team) >= 3: break
                if r not in final_team: final_team.append(r)

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