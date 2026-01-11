import streamlit as st
import pandas as pd
import google.generativeai as genai
from PIL import Image
import json
import os

# --- 設定頁面 ---
st.set_page_config(page_title="Mezastar 檔案室", layout="wide", page_icon="🗃️")

# ==========================================
# 👇👇👇 請把你的 API Key 貼在下面這行引號中 👇👇👇
# ==========================================
MY_SECRET_KEY = "AIzaSyAOLJg5mosQkA5ZwcHdwwrgGMjg59nngx8"
# ==========================================

# --- 初始化 API ---
if "AIza" in MY_SECRET_KEY:
    api_key = MY_SECRET_KEY
    st.sidebar.success("✅ API Key 已載入")
else:
    st.sidebar.warning("⚠️ 未填寫 API Key")
    api_key = st.sidebar.text_input("輸入 Google Gemini API Key", type="password")

if api_key:
    genai.configure(api_key=api_key)

# 模擬本地資料庫
if 'inventory' not in st.session_state:
    st.session_state['inventory'] = []

# --- 常數定義 ---
POKEMON_TYPES = [
    "一般", "火", "水", "草", "電", "冰", "格鬥", "毒", "地面", 
    "飛行", "超能力", "蟲", "岩石", "鬼", "龍", "惡", "鋼", "妖精", "無"
]

SPECIAL_TAGS = [
    "無", "Mega進化", "Z招式", "極巨化", "太晶化", "特別聯手對戰"
]

# --- 輔助函式：用 AI 查資料 (純文字查詢，不傳圖，速度快且省額度) ---
def query_pokemon_info(pokemon_name):
    if not api_key:
        return None
    try:
        # 使用 Flash 模型查文字非常快
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        prompt = f"""
        請根據寶可夢名稱 "{pokemon_name}"，提供其詳細資料。
        請回傳 JSON 格式，包含以下欄位：
        - type1: 主要屬性 (例如: 超能力, 冰, 火...)
        - type2: 次要屬性 (如果沒有則填 "無")
        - move1_name: 代表性的一般招式名稱
        - move1_type: 一般招式屬性
        - move2_name: 代表性的強力招式或專屬招式名稱
        - move2_type: 強力招式屬性
        
        請確保屬性名稱符合寶可夢官方中文譯名。
        """
        response = model.generate_content(prompt)
        text = response.text
        # 清理 JSON
        if "```json" in text:
            text = text.replace('```json', '').replace('```', '')
        elif "```" in text:
            text = text.replace('```', '')
        return json.loads(text)
    except Exception as e:
        st.error(f"查詢失敗: {e}")
        return None

# --- 功能 1: 新增卡片 (檔案管理模式) ---
def page_add_card():
    st.header("🗃️ 新增 Mezastar 卡片資料")
    
    col_preview, col_edit = st.columns([1, 2])
    
    # 用 session state 來暫存表單資料，避免重新整理後消失
    if 'form_data' not in st.session_state:
        st.session_state['form_data'] = {
            "name": "", "tag": "無", 
            "type1": "一般", "type2": "無",
            "m1_n": "", "m1_t": "一般",
            "m2_n": "", "m2_t": "一般"
        }

    with col_preview:
        st.subheader("1. 圖片來源")
        uploaded_file = st.file_uploader("上傳卡片圖片 (檔名自動帶入)", type=["jpg", "png", "jpeg"])
        
        if uploaded_file:
            image = Image.open(uploaded_file)
            st.image(image, caption="卡片預覽", use_container_width=True)
            
            # --- 檔名解析邏輯 ---
            # 取得檔名 (不含副檔名)
            filename = os.path.splitext(uploaded_file.name)[0]
            # 去除 _前, _後
            if filename.endswith("_前") or filename.endswith("_後"):
                clean_name = filename.rsplit("_", 1)[0]
            else:
                clean_name = filename
            
            # 如果是新上傳的檔案，更新名稱欄位
            if st.session_state['form_data']['name'] == "":
                st.session_state['form_data']['name'] = clean_name
                st.rerun() # 重新整理以顯示名稱

    with col_edit:
        st.subheader("2. 詳細資料編輯")
        
        # 名稱欄位 (自動帶入，可修改)
        current_name = st.text_input("卡片名稱 (由檔名自動解析)", value=st.session_state['form_data']['name'], key="input_name")
        
        # --- AI 輔助查詢按鈕 ---
        if st.button("🔮 查詢屬性與招式 (自動填寫)"):
            if not current_name:
                st.warning("請先有卡片名稱才能查詢！")
            else:
                with st.spinner(f"正在查詢 '{current_name}' 的資料庫..."):
                    # 嘗試提取寶可夢純名 (去掉編號如 1-4-005_) 以便查詢精準
                    search_name = current_name.split("_")[-1] if "_" in current_name else current_name
                    
                    info = query_pokemon_info(search_name)
                    if info:
                        # 更新 Session State
                        st.session_state['form_data']['type1'] = info.get('type1', '一般')
                        st.session_state['form_data']['type2'] = info.get('type2', '無')
                        st.session_state['form_data']['m1_n'] = info.get('move1_name', '')
                        st.session_state['form_data']['m1_t'] = info.get('move1_type', '一般')
                        st.session_state['form_data']['m2_n'] = info.get('move2_name', '')
                        st.session_state['form_data']['m2_t'] = info.get('move2_type', '一般')
                        st.success("資料已自動填入！請確認並儲存。")
                        st.rerun()

        # 編輯表單
        with st.form("card_form"):
            # 特殊卡片選單
            tag_select = st.selectbox("特殊能力", SPECIAL_TAGS, index=SPECIAL_TAGS.index(st.session_state['form_data']['tag']))
            
            st.markdown("---")
            st.markdown("**寶可夢屬性**")
            c1, c2 = st.columns(2)
            # 確保屬性在清單內，否則預設為一般
            def get_idx(val): return POKEMON_TYPES.index(val) if val in POKEMON_TYPES else 0
            
            t1 = c1.selectbox("屬性 1", POKEMON_TYPES, index=get_idx(st.session_state['form_data']['type1']))
            t2 = c2.selectbox("屬性 2", POKEMON_TYPES, index=get_idx(st.session_state['form_data']['type2']))
            
            st.markdown("---")
            st.markdown("**招式資訊**")
            
            # 招式 1
            mc1_a, mc1_b = st.columns([2, 1])
            m1_name = mc1_a.text_input("一般招式名稱", value=st.session_state['form_data']['m1_n'])
            m1_type = mc1_b.selectbox("一般招式屬性", POKEMON_TYPES, key="m1t", index=get_idx(st.session_state['form_data']['m1_t']))
            
            # 招式 2
            mc2_a, mc2_b = st.columns([2, 1])
            m2_name = mc2_a.text_input("特殊/強力招式名稱", value=st.session_state['form_data']['m2_n'])
            m2_type = mc2_b.selectbox("特殊招式屬性", POKEMON_TYPES, key="m2t", index=get_idx(st.session_state['form_data']['m2_t']))
            
            submitted = st.form_submit_button("💾 儲存至卡匣資料庫", type="primary")
            
            if submitted:
                new_card = {
                    "name": current_name,
                    "tag": tag_select,
                    "type": t1, # 為了相容舊版對戰邏輯，主要屬性存為 type
                    "type2": t2,
                    "moves": [
                        {"name": m1_name, "type": m1_type},
                        {"name": m2_name, "type": m2_type}
                    ],
                    "power": 100 # 預設值，因為這次沒讀數值
                }
                st.session_state['inventory'].append(new_card)
                st.success(f"已新增：{current_name}")
                # 清空暫存
                st.session_state['form_data'] = {
                    "name": "", "tag": "無", "type1": "一般", "type2": "無",
                    "m1_n": "", "m1_t": "一般", "m2_n": "", "m2_t": "一般"
                }
                st.rerun()

    # 顯示目前清單
    st.markdown("---")
    if st.session_state['inventory']:
        st.subheader(f"目前已有 {len(st.session_state['inventory'])} 張卡片")
        df = pd.DataFrame(st.session_state['inventory'])
        # 簡單顯示表格
        display_df = df[['name', 'tag', 'type', 'type2']].copy()
        st.dataframe(display_df, use_container_width=True)
        
        # 備份下載
        json_str = json.dumps(st.session_state['inventory'], ensure_ascii=False)
        st.download_button("⬇️ 下載備份 (.json)", json_str, "mezastar_data.json")

# --- 功能 2: 對戰分析 (維持原樣，但適配新資料結構) ---
# 簡化版屬性表 (僅供範例，實際可擴充)
TYPE_CHART = {"一般": {"岩石": 0.5, "鬼": 0, "鋼": 0.5}, "火": {"草": 2, "冰": 2, "蟲": 2, "鋼": 2, "水": 0.5, "火": 0.5}, "水": {"火": 2, "地面": 2, "岩石": 2, "水": 0.5, "草": 0.5}, "電": {"水": 2, "飛行": 2, "地面": 0, "電": 0.5}, "草": {"水": 2, "地面": 2, "岩石": 2, "火": 0.5, "草": 0.5}, "冰": {"草": 2, "地面": 2, "飛行": 2, "龍": 2, "火": 0.5, "冰": 0.5}, "格鬥": {"一般": 2, "冰": 2, "岩石": 2, "惡": 2, "鋼": 2, "鬼": 0}, "毒": {"草": 2, "妖精": 2, "毒": 0.5, "地面": 0.5}, "地面": {"火": 2, "電": 2, "毒": 2, "岩石": 2, "鋼": 2, "飛行": 0}, "飛行": {"草": 2, "格鬥": 2, "蟲": 2, "電": 0.5, "岩石": 0.5}, "超能力": {"格鬥": 2, "毒": 2, "超能力": 0.5, "惡": 0}, "蟲": {"草": 2, "超能力": 2, "惡": 2, "火": 0.5, "飛行": 0.5}, "岩石": {"火": 2, "冰": 2, "飛行": 2, "蟲": 2, "格鬥": 0.5, "地面": 0.5}, "鬼": {"超能力": 2, "鬼": 2, "一般": 0, "惡": 0.5}, "龍": {"龍": 2, "鋼": 0.5, "妖精": 0}, "惡": {"鬼": 2, "超能力": 2, "格鬥": 0.5, "妖精": 0.5}, "鋼": {"冰": 2, "岩石": 2, "妖精": 2, "火": 0.5, "水": 0.5}, "妖精": {"格鬥": 2, "龍": 2, "惡": 2, "毒": 0.5, "鋼": 0.5}}

def get_effectiveness(attacker_type, defender_type):
    if attacker_type not in TYPE_CHART: return 1.0
    return TYPE_CHART[attacker_type].get(defender_type, 1.0)

def page_battle():
    st.header("⚔️ 對戰分析")
    opponent = st.selectbox("選擇對手屬性", POKEMON_TYPES[:-1]) # 去掉'無'
    
    if st.button("計算最佳隊伍"):
        if not st.session_state['inventory']:
            st.error("卡匣是空的！")
            return
            
        recs = []
        for card in st.session_state['inventory']:
            # 簡單邏輯：檢查 招式1 和 招式2 哪個打對手比較痛
            # 如果有新結構 moves，取出來算
            best_move_score = 0
            best_move_name = ""
            
            moves = card.get('moves', [])
            # 相容舊資料
            if not moves: 
                moves = [{"name": "普通攻擊", "type": card['type']}]
            
            for m in moves:
                eff = get_effectiveness(m['type'], opponent)
                # 假設 特殊招式 (index 1) 威力比較大
                base_pow = 120 if moves.index(m) == 1 else 100
                score = base_pow * eff
                if score > best_move_score:
                    best_move_score = score
                    best_move_name = f"{m['name']}({m['type']})"
            
            # 特殊能力加權
            if card['tag'] != '無': best_move_score *= 1.2
            
            recs.append({
                "name": card['name'],
                "tag": card['tag'],
                "best_move": best_move_name,
                "score": best_move_score
            })
            
        # 排序
        recs.sort(key=lambda x: x['score'], reverse=True)
        
        # 挑選不重複Tag (簡單版)
        final = []
        tags = set()
        for r in recs:
            if len(final)>=3: break
            if r['tag']!='無' and r['tag'] in tags: continue
            final.append(r)
            if r['tag']!='無': tags.add(r['tag'])
            
        # 補滿
        if len(final)<3:
            for r in recs:
                if len(final)>=3: break
                if r not in final: final.append(r)
                
        for i, p in enumerate(final):
            st.success(f"第 {i+1} 棒: {p['name']} | {p['tag']} | 建議招式: {p['best_move']}")

# --- 主程式 ---
page = st.sidebar.radio("模式", ["新增卡片", "對戰分析"])

if page == "新增卡片":
    page_add_card()
else:
    page_battle()