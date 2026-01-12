import streamlit as st
import pandas as pd
import google.generativeai as genai
from PIL import Image
import json
import os

# --- 設定頁面 ---
st.set_page_config(page_title="Mezastar 檔案室", layout="wide", page_icon="🗃️")

# --- 設定資料與圖片路徑 ---
DB_FILE = "mezastar_db.json"
IMG_DIR = "cardinfo"

# 確保圖片目錄存在
if not os.path.exists(IMG_DIR):
    os.makedirs(IMG_DIR)

# --- Helper: 排序資料庫 ---
def sort_inventory(data):
    """依照名稱 (name) 對資料庫進行 A-Z 排序"""
    if data:
        data.sort(key=lambda x: x['name'])
    return data

# --- 函式：讀取與寫入資料庫 ---
def load_db():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return sort_inventory(data)
        except Exception as e:
            st.error(f"讀取資料庫失敗: {e}")
            return []
    return []

def save_db(data):
    try:
        sort_inventory(data)
        with open(DB_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        st.toast("✅ 資料庫已自動存檔！", icon="💾")
    except Exception as e:
        st.error(f"寫入資料庫失敗: {e}")

# --- Helper: 儲存圖片到 cardinfo ---
def save_card_images(name):
    """從 Session State 的上傳元件中讀取圖片並存檔"""
    current_key = st.session_state['uploader_key']
    
    # 取得正面圖片物件
    front_file = st.session_state.get(f"u_front_{current_key}")
    if front_file:
        try:
            img = Image.open(front_file)
            save_path = os.path.join(IMG_DIR, f"{name}_前.png")
            img.save(save_path, "PNG")
        except Exception as e:
            st.error(f"正面圖片存檔失敗: {e}")

    # 取得背面圖片物件
    back_file = st.session_state.get(f"u_back_{current_key}")
    if back_file:
        try:
            img = Image.open(back_file)
            save_path = os.path.join(IMG_DIR, f"{name}_後.png")
            img.save(save_path, "PNG")
        except Exception as e:
            st.error(f"背面圖片存檔失敗: {e}")

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

# --- 初始化輸入框的 Session State ---
defaults = {
    "add_name_input": "",
    "add_attack_input": 100,
    "add_sp_attack_input": 100,
    "add_tag_input": "無",
    "add_t1_input": "一般",
    "add_t2_input": "無",
    "add_m1_name_input": "",
    "add_m1_type_input": "一般",
    "add_m1_cat_input": "攻擊",
    "add_m2_name_input": "",
    "add_m2_type_input": "一般",
    "add_m2_cat_input": "攻擊",
    "msg_area": "",
    "edit_select_index": 0,
    "edit_name_input": "",
    "edit_attack_input": 100,
    "edit_sp_attack_input": 100,
    "edit_tag_input": "無",
    "edit_t1_input": "一般",
    "edit_t2_input": "無",
    "edit_m1_name_input": "",
    "edit_m1_type_input": "一般",
    "edit_m1_cat_input": "攻擊",
    "edit_m2_name_input": "",
    "edit_m2_type_input": "一般",
    "edit_m2_cat_input": "攻擊",
    "manage_sub_mode": "➕ 新增卡片" 
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

MOVE_CATEGORIES = ["攻擊", "特攻"]

# --- 同步編輯欄位的 Helper Function ---
def fill_edit_fields():
    if not st.session_state['inventory']: return
    
    idx = st.session_state.get('edit_select_index', 0)
    if idx >= len(st.session_state['inventory']): idx = 0
    
    c = st.session_state['inventory'][idx]
    
    st.session_state['edit_name_input'] = c['name']
    st.session_state['edit_attack_input'] = c.get('attack', 100)
    st.session_state['edit_sp_attack_input'] = c.get('sp_attack', 100)
    st.session_state['edit_tag_input'] = c['tag']
    st.session_state['edit_t1_input'] = c['type']
    st.session_state['edit_t2_input'] = c.get('type2', '無')
    
    m1 = c['moves'][0]
    st.session_state['edit_m1_name_input'] = m1['name']
    st.session_state['edit_m1_type_input'] = m1['type']
    st.session_state['edit_m1_cat_input'] = m1.get('category', '攻擊')
    
    m2 = c['moves'][1]
    st.session_state['edit_m2_name_input'] = m2['name']
    st.session_state['edit_m2_type_input'] = m2['type']
    st.session_state['edit_m2_cat_input'] = m2.get('category', '攻擊')

# --- Callbacks: 資料庫管理 ---
def save_new_card_callback():
    name = st.session_state['add_name_input']
    if not name: name = "未命名"
    
    new_card = {
        "name": name,
        "attack": st.session_state['add_attack_input'],
        "sp_attack": st.session_state['add_sp_attack_input'],
        "tag": st.session_state['add_tag_input'],
        "type": st.session_state['add_t1_input'],
        "type2": st.session_state['add_t2_input'],
        "moves": [
            {
                "name": st.session_state['add_m1_name_input'], 
                "type": st.session_state['add_m1_type_input'],
                "category": st.session_state['add_m1_cat_input']
            },
            {
                "name": st.session_state['add_m2_name_input'], 
                "type": st.session_state['add_m2_type_input'],
                "category": st.session_state['add_m2_cat_input']
            }
        ]
    }
    
    # 儲存圖片到 cardinfo (新增功能)
    save_card_images(name)
    
    st.session_state['inventory'].append(new_card)
    sort_inventory(st.session_state['inventory'])
    save_db(st.session_state['inventory'])
    
    st.session_state['msg_area'] = f"✅ 已新增並存檔：{name}"
    
    # 清空欄位
    st.session_state['add_name_input'] = ""
    st.session_state['add_attack_input'] = 100
    st.session_state['add_sp_attack_input'] = 100
    st.session_state['add_m1_name_input'] = ""
    st.session_state['add_m2_name_input'] = ""
    
    if 'last_processed_file' in st.session_state:
        del st.session_state['last_processed_file']
    st.session_state['uploader_key'] += 1
    
    st.session_state['manage_sub_mode'] = "➕ 新增卡片"

def update_card_callback():
    idx = st.session_state['edit_select_index']
    updated_card = {
        "name": st.session_state['edit_name_input'],
        "attack": st.session_state['edit_attack_input'],
        "sp_attack": st.session_state['edit_sp_attack_input'],
        "tag": st.session_state['edit_tag_input'],
        "type": st.session_state['edit_t1_input'],
        "type2": st.session_state['edit_t2_input'],
        "moves": [
            {
                "name": st.session_state['edit_m1_name_input'], 
                "type": st.session_state['edit_m1_type_input'],
                "category": st.session_state['edit_m1_cat_input']
            },
            {
                "name": st.session_state['edit_m2_name_input'], 
                "type": st.session_state['edit_m2_type_input'],
                "category": st.session_state['edit_m2_cat_input']
            }
        ]
    }
    st.session_state['inventory'][idx] = updated_card
    sort_inventory(st.session_state['inventory'])
    save_db(st.session_state['inventory'])
    
    st.session_state['msg_area'] = f"✅ 已更新並存檔：{updated_card['name']}"
    
    st.session_state['edit_select_index'] = 0
    fill_edit_fields()

def delete_card_callback():
    idx = st.session_state['edit_select_index']
    if idx < len(st.session_state['inventory']):
        removed_name = st.session_state['inventory'][idx]['name']
        st.session_state['inventory'].pop(idx)
        save_db(st.session_state['inventory'])
        st.session_state['msg_area'] = f"🗑️ 已刪除並存檔：{removed_name}"
        
        # 選擇性功能：刪除資料時，是否要一併刪除圖片？
        # 目前為求安全，保留圖片不刪除
        
        st.session_state['edit_select_index'] = 0
        fill_edit_fields()

# --- 功能 1: 卡片資料庫管理 ---
def page_manage_cards():
    st.header("🗃️ 卡片資料庫管理")
    
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 💾 資料庫狀態")
    if st.sidebar.button("手動強制存檔", type="secondary"):
        save_db(st.session_state['inventory'])
    
    if 'msg_area' in st.session_state and st.session_state['msg_area']:
        st.success(st.session_state['msg_area'])
        st.session_state['msg_area'] = "" 

    sub_mode = st.radio(
        "功能切換", 
        ["➕ 新增卡片", "✏️ 編輯與刪除"], 
        horizontal=True,
        key="manage_sub_mode"
    )

    st.markdown("---")

    if sub_mode == "➕ 新增卡片":
        col_preview, col_edit = st.columns([1, 2])
        with col_preview:
            st.subheader("圖片上傳")
            current_key = st.session_state['uploader_key']
            front_file = st.file_uploader("上傳【正面】(自動帶入檔名)", type=["jpg", "png", "jpeg"], key=f"u_front_{current_key}")
            back_file = st.file_uploader("上傳【背面】", type=["jpg", "png", "jpeg"], key=f"u_back_{current_key}")
            
            if front_file:
                st.image(Image.open(front_file), caption="正面預覽", use_container_width=True)
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
                
                c_stat1, c_stat2 = st.columns(2)
                c_stat1.number_input("⚔️ 攻擊數值", min_value=0, step=1, key="add_attack_input")
                c_stat2.number_input("✨ 特攻數值", min_value=0, step=1, key="add_sp_attack_input")
                
                st.selectbox("特殊能力", SPECIAL_TAGS, key="add_tag_input")
                
                c1, c2 = st.columns(2)
                c1.selectbox("屬性 1", POKEMON_TYPES, key="add_t1_input")
                c2.selectbox("屬性 2", POKEMON_TYPES, index=len(POKEMON_TYPES)-1, key="add_t2_input")
                
                st.markdown("**招式資訊**")
                
                st.markdown("---")
                mc1_a, mc1_b, mc1_c = st.columns([2, 1, 1])
                mc1_a.text_input("一般招式", placeholder="例如：影子球", key="add_m1_name_input")
                mc1_b.selectbox("屬性", POKEMON_TYPES, key="add_m1_type_input")
                mc1_c.selectbox("分類", MOVE_CATEGORIES, key="add_m1_cat_input")
                
                mc2_a, mc2_b, mc2_c = st.columns([2, 1, 1])
                mc2_a.text_input("強力招式", placeholder="例如：極巨幽魂", key="add_m2_name_input")
                mc2_b.selectbox("屬性", POKEMON_TYPES, key="add_m2_type_input")
                mc2_c.selectbox("分類", MOVE_CATEGORIES, key="add_m2_cat_input")
                
                st.form_submit_button("💾 新增至資料庫", type="primary", on_click=save_new_card_callback)

    elif sub_mode == "✏️ 編輯與刪除":
        if not st.session_state['inventory']:
            st.info("資料庫目前是空的。")
        else:
            st.subheader("🔍 選擇要管理的卡片")
            sort_inventory(st.session_state['inventory'])
            card_options = [f"{i+1}. {c['name']} ({c['tag']})" for i, c in enumerate(st.session_state['inventory'])]
            
            selected_idx = st.selectbox(
                "請選擇卡片 (已依名稱排序)", 
                range(len(st.session_state['inventory'])), 
                format_func=lambda x: card_options[x], 
                key="edit_select_index",
                on_change=fill_edit_fields
            )
            
            if st.session_state['edit_name_input'] == "" and st.session_state['inventory']:
                 fill_edit_fields()

            st.markdown("---")
            col_form, col_action = st.columns([3, 1])
            with col_form:
                st.subheader("編輯卡片資訊")
                with st.form("edit_form"):
                    st.text_input("卡片名稱", key="edit_name_input")
                    
                    ec_s1, ec_s2 = st.columns(2)
                    ec_s1.number_input("攻擊數值", min_value=0, step=1, key="edit_attack_input")
                    ec_s2.number_input("特攻數值", min_value=0, step=1, key="edit_sp_attack_input")

                    st.selectbox("特殊能力", SPECIAL_TAGS, key="edit_tag_input")
                    
                    ec1, ec2 = st.columns(2)
                    ec1.selectbox("屬性 1", POKEMON_TYPES, key="edit_t1_input")
                    ec2.selectbox("屬性 2", POKEMON_TYPES, key="edit_t2_input")
                    
                    st.markdown("**招式資訊**")
                    em1_a, em1_b, em1_c = st.columns([2, 1, 1])
                    em1_a.text_input("一般招式", key="edit_m1_name_input")
                    em1_b.selectbox("屬性", POKEMON_TYPES, key="edit_m1_type_input")
                    em1_c.selectbox("分類", MOVE_CATEGORIES, key="edit_m1_cat_input")
                    
                    em2_a, em2_b, em2_c = st.columns([2, 1, 1])
                    em2_a.text_input("強力招式", key="edit_m2_name_input")
                    em2_b.selectbox("屬性", POKEMON_TYPES, key="edit_m2_type_input")
                    em2_c.selectbox("分類", MOVE_CATEGORIES, key="edit_m2_cat_input")
                    
                    st.form_submit_button("✅ 更新資料 (並存檔)", type="primary", on_click=update_card_callback)
            
            with col_action:
                st.subheader("危險區域")
                st.button("🗑️ 刪除此卡片", type="secondary", on_click=delete_card_callback)
                
                # --- 新增功能：顯示卡片圖片 ---
                st.markdown("---")
                st.markdown("###### 🖼️ 卡片影像確認")
                
                # 取得目前編輯的卡片名稱
                current_card_name = st.session_state['edit_name_input']
                # 如果名稱為空（可能剛刪除完），則不顯示
                if current_card_name:
                    f_path = os.path.join(IMG_DIR, f"{current_card_name}_前.png")
                    b_path = os.path.join(IMG_DIR, f"{current_card_name}_後.png")
                    
                    if os.path.exists(f_path):
                        st.image(f_path, caption=f"{current_card_name}_正面", use_container_width=True)
                    else:
                        st.caption(f"⚠️ 無正面影像 ({f_path})")
                        
                    if os.path.exists(b_path):
                        st.image(b_path, caption=f"{current_card_name}_背面", use_container_width=True)
                    else:
                        st.caption(f"⚠️ 無背面影像")

    if st.session_state['inventory']:
        st.markdown("---")
        with st.expander("檢視完整資料庫清單", expanded=True):
            sort_inventory(st.session_state['inventory'])
            display_data = []
            for item in st.session_state['inventory']:
                m1 = item['moves'][0]
                m2 = item['moves'][1]
                moves_str = f"{m1['name']}({m1.get('category','攻擊')}) / {m2['name']}({m2.get('category','攻擊')})"
                types_str = f"{item['type']}" + (f"/{item['type2']}" if item['type2'] != "無" else "")
                display_data.append({
                    "名稱": item['name'],
                    "攻擊/特攻": f"{item.get('attack',100)} / {item.get('sp_attack',100)}",
                    "屬性": types_str,
                    "特殊能力": item['tag'],
                    "招式": moves_str
                })
            
            df = pd.DataFrame(display_data)
            df.index = range(1, len(df) + 1)
            st.dataframe(df, use_container_width=True)
            
            json_str = json.dumps(st.session_state['inventory'], ensure_ascii=False, indent=4)
            st.download_button("⬇️ 下載 JSON 備份檔", json_str, DB_FILE)

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
    st.info("AI 將計算最佳 AOE 火力。若特殊能力重複，較弱的寶可夢將自動改用一般招式出戰。")
    
    opponents = []
    cols = st.columns(3)
    
    for i in range(3):
        with cols[i]:
            st.markdown(f"### 🥊 對手 {i+1}")
            t1 = st.selectbox(f"屬性 1", POKEMON_TYPES, index=0, key=f"op{i}_t1")
            t2 = st.selectbox(f"屬性 2", POKEMON_TYPES, index=len(POKEMON_TYPES)-1, key=f"op{i}_t2")
            move_type = st.selectbox(f"**招式屬性 (攻擊我方)**", POKEMON_TYPES, index=0, key=f"op{i}_move")
            opponents.append({"t1": t1, "t2": t2, "move": move_type})

    st.markdown("---")
    
    if st.button("🚀 計算最佳攻防隊伍", type="primary"):
        if not st.session_state['inventory']:
            st.error("卡匣是空的！請先建立資料。")
            return

        candidates = []
        
        for card in st.session_state['inventory']:
            
            risk_factors = []
            for opp in opponents:
                my_t1 = card['type']
                my_t2 = card.get('type2', '無')
                dmg_taken = calculate_dual_effectiveness(opp['move'], my_t1, my_t2)
                risk_factors.append(dmg_taken)
            max_risk = max(risk_factors)
            safe_risk = max_risk if max_risk > 0 else 0.1
            
            stat_atk = card.get('attack', 100)
            stat_sp_atk = card.get('sp_attack', 100)
            
            # --- 方案 A: 全力模式 (Special) ---
            max_aoe_special = 0
            best_move_special = ""
            
            for idx, move in enumerate(card['moves']):
                if not move['name']: continue
                eff_sum = 0
                for opp in opponents:
                    eff_sum += calculate_dual_effectiveness(move['type'], opp['t1'], opp['t2'])
                
                cat = move.get('category', '攻擊')
                base_stat = stat_atk if cat == '攻擊' else stat_sp_atk
                
                power_mult = 1.2 if idx == 1 else 1.0
                total = base_stat * power_mult * eff_sum
                
                if total > max_aoe_special:
                    max_aoe_special = total
                    best_move_special = f"{move['name']}({move['type']}/{cat})"
            
            score_special = max_aoe_special / safe_risk
            tag_name = card['tag']
            if tag_name != '無':
                score_special *= 1.2
            
            best_move_display_special = best_move_special
            
            candidates.append({
                "name": card['name'],
                "use_tag": tag_name, 
                "score": score_special,
                "move": best_move_display_special,
                "aoe_dmg": max_aoe_special * (1.2 if tag_name != '無' else 1.0),
                "risk": max_risk,
                "mode": "special"
            })
            
            # --- 方案 B: 保留模式 (Normal) ---
            if tag_name != '無':
                max_aoe_normal = 0
                best_move_normal = ""
                
                for idx, move in enumerate(card['moves']):
                    if not move['name']: continue
                    eff_sum = 0
                    for opp in opponents:
                        eff_sum += calculate_dual_effectiveness(move['type'], opp['t1'], opp['t2'])
                    
                    cat = move.get('category', '攻擊')
                    base_stat = stat_atk if cat == '攻擊' else stat_sp_atk
                    
                    power_mult = 1.2 if idx == 1 else 1.0
                    total = base_stat * power_mult * eff_sum
                    
                    if total > max_aoe_normal:
                        max_aoe_normal = total
                        best_move_normal = f"{move['name']}({move['type']}/{cat})"
                
                score_normal = max_aoe_normal / safe_risk
                
                candidates.append({
                    "name": card['name'],
                    "use_tag": "無", 
                    "score": score_normal, 
                    "move": best_move_normal,
                    "aoe_dmg": max_aoe_normal,
                    "risk": max_risk,
                    "mode": "normal"
                })

        # 排序
        candidates.sort(key=lambda x: x['score'], reverse=True)

        # 挑選隊伍
        final_team = []
        used_names = set()
        used_tags = set()
        
        for cand in candidates:
            if len(final_team) >= 3: break
            
            if cand['name'] in used_names:
                continue
            
            tag = cand['use_tag']
            if tag != '無' and tag in used_tags:
                continue
            
            final_team.append(cand)
            used_names.add(cand['name'])
            if tag != '無':
                used_tags.add(tag)

        # 顯示結果
        st.subheader("🏆 推薦出戰陣容")
        if len(final_team) < 3:
            st.warning("庫存寶可夢不足 3 隻，僅列出可用名單。")
            
        cols = st.columns(3)
        for i, p in enumerate(final_team):
            with cols[i]:
                risk_text = "普通"
                if p['risk'] >= 2: risk_text = "⚠️ 危險"
                elif p['risk'] <= 0.5: risk_text = "🛡️ 堅硬"
                elif p['risk'] == 0: risk_text = "✨ 免疫"
                
                tag_display = p['use_tag']
                if p['mode'] == 'normal' and tag_display == '無':
                     tag_display = "一般招式 (保留特殊能力)"
                
                st.success(f"""
                **第 {i+1} 棒**
                ### {p['name']}
                * **模式**: {tag_display}
                * **建議**: {p['move']}
                * **AOE 火力**: {int(p['aoe_dmg'])}
                * **防禦**: {risk_text} (受傷x{p['risk']})
                """)

# --- 主程式切換 ---
page = st.sidebar.radio("模式", ["卡片資料庫管理", "對戰分析"])

if page == "卡片資料庫管理":
    page_manage_cards()
else:
    page_battle()