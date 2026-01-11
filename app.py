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

# --- Callback: 新增卡片存檔 ---
def save_new_card_callback():
    name = st.session_state['add_name_input']
    if not name: name = "未命名"
    
    new_card = {
        "name": name,
        "tag": st.session_state['add_tag_input'],
        "type": st.session_state['add_t1_input'],
        "type2": st.session_state['add_t2_input'],
        "moves": [
            {"name": st.session_state['add_m1_name_input'], "type": st.session_state['add_m1_type_input']},
            {"name": st.session_state['add_m2_name_input'], "type": st.session_state['add_m2_type_input']}
        ],
        "power": 100
    }
    
    st.session_state['inventory'].append(new_card)
    save_db(st.session_state['inventory'])
    
    st.session_state['msg_area'] = f"✅ 已新增：{name}"
    
    # 清空新增欄位
    st.session_state['add_name_input'] = ""
    st.session_state['add_m1_name_input'] = ""
    st.session_state['add_m2_name_input'] = ""
    
    # 重置圖片上傳
    if 'last_processed_file' in st.session_state:
        del st.session_state['last_processed_file']
    st.session_state['uploader_key'] += 1

# --- Callback: 更新現有卡片 ---
def update_card_callback():
    idx = st.session_state['edit_select_index']
    
    updated_card = {
        "name": st.session_state['edit_name_input'],
        "tag": st.session_state['edit_tag_input'],
        "type": st.session_state['edit_t1_input'],
        "type2": st.session_state['edit_t2_input'],
        "moves": [
            {"name": st.session_state['edit_m1_name_input'], "type": st.session_state['edit_m1_type_input']},
            {"name": st.session_state['edit_m2_name_input'], "type": st.session_state['edit_m2_type_input']}
        ],
        "power": 100
    }
    
    st.session_state['inventory'][idx] = updated_card
    save_db(st.session_state['inventory'])
    st.session_state['msg_area'] = f"✅ 已更新：{updated_card['name']}"

# --- Callback: 刪除卡片 ---
def delete_card_callback():
    idx = st.session_state['edit_select_index']
    removed_name = st.session_state['inventory'][idx]['name']
    
    st.session_state['inventory'].pop(idx)
    save_db(st.session_state['inventory'])
    st.session_state['msg_area'] = f"🗑️ 已刪除：{removed_name}"
    # 刪除後重置選擇索引，避免 index out of range
    st.session_state['edit_select_index'] = 0

# --- 功能 1: 卡片資料庫管理 (新增/編輯/刪除) ---
def page_manage_cards():
    st.header("🗃️ 卡片資料庫管理")
    
    # 顯示全域訊息區 (用於顯示新增/修改/刪除的結果)
    if 'msg_area' in st.session_state and st.session_state['msg_area']:
        st.success(st.session_state['msg_area'])
        st.session_state['msg_area'] = "" # 顯示一次後清空

    # 使用 Tabs 分頁
    tab_add, tab_edit = st.tabs(["➕ 新增卡片", "✏️ 編輯與刪除"])

    # === Tab 1: 新增卡片 ===
    with tab_add:
        col_preview, col_edit = st.columns([1, 2])
        
        with col_preview:
            st.subheader("圖片上傳")
            current_key = st.session_state['uploader_key']
            
            front_file = st.file_uploader("上傳【正面】(自動帶入檔名)", type=["jpg", "png", "jpeg"], key=f"u_front_{current_key}")
            back_file = st.file_uploader("上傳【背面】", type=["jpg", "png", "jpeg"], key=f"u_back_{current_key}")
            
            if front_file:
                st.image(Image.open(front_file), caption="正面預覽", use_container_width=True)
                # 自動讀取檔名邏輯
                if 'last_processed_file' not in st.session_state or st.session_state['last_processed_file'] != front_file.name:
                    filename = os.path.splitext(front_file.name)[0]
                    for suffix in ["_前", "_front", "正面"]:
                        if filename.endswith(suffix):
                            filename = filename.replace(suffix, "")
                            break
                    st.session_state['add_name_input'] = filename
                    st.session_state['last_processed_file'] = front_file.name
                    st.rerun()

            if back_file:
                st.image(Image.open(back_file), caption="背面預覽", use_container_width=True)

        with col_edit:
            st.subheader("填寫資料")
            with st.form("add_form"):
                st.text_input("卡片名稱", key="add_name_input")
                st.selectbox("特殊能力", SPECIAL_TAGS, key="add_tag_input")
                
                c1, c2 = st.columns(2)
                c1.selectbox("屬性 1", POKEMON_TYPES, key="add_t1_input")
                c2.selectbox("屬性 2", POKEMON_TYPES, index=len(POKEMON_TYPES)-1, key="add_t2_input")
                
                st.markdown("**招式資訊**")
                mc1_a, mc1_b = st.columns([2, 1])
                mc1_a.text_input("一般招式", placeholder="例如：影子球", key="add_m1_name_input")
                mc1_b.selectbox("屬性", POKEMON_TYPES, key="add_m1_type_input")
                
                mc2_a, mc2_b = st.columns([2, 1])
                mc2_a.text_input("強力招式", placeholder="例如：極巨幽魂", key="add_m2_name_input")
                mc2_b.selectbox("屬性", POKEMON_TYPES, key="add_m2_type_input")
                
                st.form_submit_button("💾 新增至資料庫", type="primary", on_click=save_new_card_callback)

    # === Tab 2: 編輯與刪除 ===
    with tab_edit:
        if not st.session_state['inventory']:
            st.info("資料庫目前是空的，請先到「新增卡片」分頁加入資料。")
        else:
            st.subheader("🔍 選擇要管理的卡片")
            
            # 建立選單選項 (顯示名稱)
            card_options = [f"{i+1}. {c['name']} ({c['tag']})" for i, c in enumerate(st.session_state['inventory'])]
            
            # 選擇器：回傳 Index
            selected_idx = st.selectbox(
                "請選擇卡片", 
                range(len(st.session_state['inventory'])), 
                format_func=lambda x: card_options[x],
                key="edit_select_index"
            )
            
            # 取得該卡片目前資料
            card_data = st.session_state['inventory'][selected_idx]
            
            st.markdown("---")
            col_form, col_action = st.columns([3, 1])
            
            with col_form:
                st.subheader(f"編輯：{card_data['name']}")
                with st.form("edit_form"):
                    # 預填資料
                    st.text_input("卡片名稱", value=card_data['name'], key="edit_name_input")
                    
                    # 處理 index 預設值 (避免資料庫的值不在選單中報錯)
                    try:
                        tag_idx = SPECIAL_TAGS.index(card_data['tag'])
                    except: tag_idx = 0
                    st.selectbox("特殊能力", SPECIAL_TAGS, index=tag_idx, key="edit_tag_input")
                    
                    ec1, ec2 = st.columns(2)
                    try: t1_idx = POKEMON_TYPES.index(card_data['type'])
                    except: t1_idx = 0
                    ec1.selectbox("屬性 1", POKEMON_TYPES, index=t1_idx, key="edit_t1_input")
                    
                    try: t2_idx = POKEMON_TYPES.index(card_data.get('type2', '無'))
                    except: t2_idx = len(POKEMON_TYPES)-1
                    ec2.selectbox("屬性 2", POKEMON_TYPES, index=t2_idx, key="edit_t2_input")
                    
                    st.markdown("**招式資訊**")
                    em1_a, em1_b = st.columns([2, 1])
                    em1_a.text_input("一般招式", value=card_data['moves'][0]['name'], key="edit_m1_name_input")
                    try: m1t_idx = POKEMON_TYPES.index(card_data['moves'][0]['type'])
                    except: m1t_idx = 0
                    em1_b.selectbox("屬性", POKEMON_TYPES, index=m1t_idx, key="edit_m1_type_input")
                    
                    em2_a, em2_b = st.columns([2, 1])
                    em2_a.text_input("強力招式", value=card_data['moves'][1]['name'], key="edit_m2_name_input")
                    try: m2t_idx = POKEMON_TYPES.index(card_data['moves'][1]['type'])
                    except: m2t_idx = 0
                    em2_b.selectbox("屬性", POKEMON_TYPES, index=m2t_idx, key="edit_m2_type_input")
                    
                    st.form_submit_button("✅ 更新資料", type="primary", on_click=update_card_callback)
            
            with col_action:
                st.subheader("危險區域")
                st.warning("刪除後無法復原")
                st.button("🗑️ 刪除此卡片", type="secondary", on_click=delete_card_callback)

    # 顯示簡易清單 (放在底部供參考)
    if st.session_state['inventory']:
        st.markdown("---")
        with st.expander("檢視完整資料庫清單"):
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
            st.download_button("⬇️ 下載備份 (.json)", json_str, DB_FILE)


# --- 功能 2: 對戰分析 (維持不變) ---
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
page = st.sidebar.radio("模式", ["卡片資料庫管理", "對戰分析"])

if page == "卡片資料庫管理":
    page_manage_cards()
else:
    page_battle()