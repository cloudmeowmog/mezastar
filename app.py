import streamlit as st
import pandas as pd
import google.generativeai as genai
from PIL import Image
import json
import os

# --- 設定頁面 ---
st.set_page_config(page_title="Mezastar 檔案室", layout="wide", page_icon="🗃️")

# --- API Key 管理 (使用 Streamlit Secrets) ---
# 方法：嘗試從 secrets.toml 讀取，若無則提供手動輸入(但不會存檔)
api_key = None

if "gemini_api_key" in st.secrets:
    api_key = st.secrets["gemini_api_key"]
    # st.sidebar.success("✅ 已從 Secrets 載入 API Key") # (選擇性開啟提示)
else:
    st.sidebar.warning("⚠️ 未偵測到 secrets.toml，請手動輸入")
    api_key = st.sidebar.text_input("Google Gemini API Key", type="password")

# 初始化 Gemini
if api_key:
    genai.configure(api_key=api_key)

# --- 資料庫初始化 ---
if 'inventory' not in st.session_state:
    st.session_state['inventory'] = []

# --- 表單資料暫存初始化 ---
if 'form_data' not in st.session_state:
    st.session_state['form_data'] = {
        "name": "", "tag": "無", 
        "type1": "一般", "type2": "無",
        "m1_n": "", "m1_t": "一般",
        "m2_n": "", "m2_t": "一般"
    }

# --- 常數定義 ---
POKEMON_TYPES = [
    "一般", "火", "水", "草", "電", "冰", "格鬥", "毒", "地面", 
    "飛行", "超能力", "蟲", "岩石", "鬼", "龍", "惡", "鋼", "妖精", "無"
]

SPECIAL_TAGS = [
    "無", "Mega進化", "Z招式", "極巨化", "太晶化", "特別聯手對戰", "雙重招式"
]

# --- 輔助函式：用 AI 查資料 ---
def query_pokemon_info(pokemon_name):
    if not api_key:
        return None
    try:
        # 使用 1.5 Flash 查詢速度快且省額度
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
        if "```json" in text:
            text = text.replace('```json', '').replace('```', '')
        elif "```" in text:
            text = text.replace('```', '')
        return json.loads(text)
    except Exception as e:
        st.error(f"查詢失敗: {e}")
        return None

# --- 功能 1: 新增卡片 ---
def page_add_card():
    st.header("🗃️ 新增 Mezastar 卡片資料")
    
    col_preview, col_edit = st.columns([1, 2])
    
    with col_preview:
        st.subheader("1. 圖片上傳")
        
        # 分開上傳正面與背面
        front_file = st.file_uploader("上傳【正面】(將自動讀取檔名)", type=["jpg", "png", "jpeg"], key="u_front")
        back_file = st.file_uploader("上傳【背面】", type=["jpg", "png", "jpeg"], key="u_back")
        
        # 顯示預覽
        if front_file:
            st.image(Image.open(front_file), caption="正面預覽", use_container_width=True)
            
            # --- 自動讀取檔名邏輯 ---
            # 判斷是否為新上傳的檔案 (避免重複刷新)
            if 'last_uploaded_front' not in st.session_state or st.session_state['last_uploaded_front'] != front_file.name:
                filename = os.path.splitext(front_file.name)[0] # 去除副檔名
                
                # 去除 _前, _front 等常見後綴
                if filename.endswith("_前"):
                    filename = filename[:-2]
                elif filename.endswith("_front"):
                    filename = filename[:-6]
                
                # 自動填入表單並記錄狀態
                st.session_state['form_data']['name'] = filename
                st.session_state['last_uploaded_front'] = front_file.name
                st.rerun()

        if back_file:
            st.image(Image.open(back_file), caption="背面預覽", use_container_width=True)

    with col_edit:
        st.subheader("2. 資料編輯")
        
        # 名稱欄位 (會被檔名自動更新)
        current_name = st.text_input("卡片名稱", value=st.session_state['form_data']['name'], key="input_name")
        
        # 如果使用者手動修改了名稱，同步回 form_data
        if current_name != st.session_state['form_data']['name']:
            st.session_state['form_data']['name'] = current_name

        # --- AI 輔助查詢按鈕 ---
        if st.button("🔮 AI 自動查詢屬性與招式"):
            if not current_name:
                st.warning("請先有卡片名稱才能查詢！")
            elif not api_key:
                st.error("請確認 API Key 是否設定正確 (secrets.toml)")
            else:
                with st.spinner(f"正在查詢 '{current_name}' 的資料庫..."):
                    # 處理名稱，去除編號 (例如 1-4-005_白馬蕾冠王 -> 白馬蕾冠王)
                    search_name = current_name.split("_")[-1] if "_" in current_name else current_name
                    
                    info = query_pokemon_info(search_name)
                    if info:
                        st.session_state['form_data']['type1'] = info.get('type1', '一般')
                        st.session_state['form_data']['type2'] = info.get('type2', '無')
                        st.session_state['form_data']['m1_n'] = info.get('move1_name', '')
                        st.session_state['form_data']['m1_t'] = info.get('move1_type', '一般')
                        st.session_state['form_data']['m2_n'] = info.get('move2_name', '')
                        st.session_state['form_data']['m2_t'] = info.get('move2_type', '一般')
                        st.success("✨ 資料已自動填入！")
                        st.rerun()

        # 編輯表單
        with st.form("card_form"):
            # 特殊能力
            tag_select = st.selectbox("特殊能力", SPECIAL_TAGS, index=SPECIAL_TAGS.index(st.session_state['form_data']['tag']))
            
            st.markdown("---")
            c1, c2 = st.columns(2)
            
            # 屬性 Helper
            def get_idx(val): return POKEMON_TYPES.index(val) if val in POKEMON_TYPES else 0
            
            t1 = c1.selectbox("屬性 1", POKEMON_TYPES, index=get_idx(st.session_state['form_data']['type1']))
            t2 = c2.selectbox("屬性 2", POKEMON_TYPES, index=get_idx(st.session_state['form_data']['type2']))
            
            st.markdown("**招式資訊**")
            # 招式 1
            mc1_a, mc1_b = st.columns([2, 1])
            m1_name = mc1_a.text_input("一般招式名稱", value=st.session_state['form_data']['m1_n'])
            m1_type = mc1_b.selectbox("屬性", POKEMON_TYPES, key="m1t", index=get_idx(st.session_state['form_data']['m1_t']))
            
            # 招式 2
            mc2_a, mc2_b = st.columns([2, 1])
            m2_name = mc2_a.text_input("特殊/強力招式名稱", value=st.session_state['form_data']['m2_n'])
            m2_type = mc2_b.selectbox("屬性", POKEMON_TYPES, key="m2t", index=get_idx(st.session_state['form_data']['m2_t']))
            
            submitted = st.form_submit_button("💾 加入資料庫", type="primary")
            
            if submitted:
                new_card = {
                    "name": current_name,
                    "tag": tag_select,
                    "type": t1,
                    "type2": t2,
                    "moves": [
                        {"name": m1_name, "type": m1_type},
                        {"name": m2_name, "type": m2_type}
                    ],
                    "power": 100 # 預設
                }
                st.session_state['inventory'].append(new_card)
                st.success(f"已新增：{current_name}")
                # 重置表單
                st.session_state['form_data'] = {
                    "name": "", "tag": "無", "type1": "一般", "type2": "無",
                    "m1_n": "", "m1_t": "一般", "m2_n": "", "m2_t": "一般"
                }
                # 清除上傳紀錄以便下一張能觸發更新
                if 'last_uploaded_front' in st.session_state:
                    del st.session_state['last_uploaded_front']
                st.rerun()

    # 清單列表
    if st.session_state['inventory']:
        st.markdown("---")
        st.subheader("📋 目前卡匣")
        
        # 整理顯示欄位
        display_data = []
        for item in st.session_state['inventory']:
            display_data.append({
                "名稱": item['name'],
                "屬性": f"{item['type']}" + (f"/{item['type2']}" if item['type2'] != "無" else ""),
                "特殊能力": item['tag'],
                "招式1": f"{item['moves'][0]['name']}({item['moves'][0]['type']})",
                "招式2": f"{item['moves'][1]['name']}({item['moves'][1]['type']})"
            })
        st.dataframe(pd.DataFrame(display_data), use_container_width=True)
        
        # 下載
        json_str = json.dumps(st.session_state['inventory'], ensure_ascii=False)
        st.download_button("⬇️ 下載備份 (.json)", json_str, "mezastar_db.json")

# --- 功能 2: 對戰分析 ---
TYPE_CHART = {"一般": {"岩石": 0.5, "鬼": 0, "鋼": 0.5}, "火": {"草": 2, "冰": 2, "蟲": 2, "鋼": 2, "水": 0.5, "火": 0.5}, "水": {"火": 2, "地面": 2, "岩石": 2, "水": 0.5, "草": 0.5}, "電": {"水": 2, "飛行": 2, "地面": 0, "電": 0.5}, "草": {"水": 2, "地面": 2, "岩石": 2, "火": 0.5, "草": 0.5}, "冰": {"草": 2, "地面": 2, "飛行": 2, "龍": 2, "火": 0.5, "冰": 0.5}, "格鬥": {"一般": 2, "冰": 2, "岩石": 2, "惡": 2, "鋼": 2, "鬼": 0}, "毒": {"草": 2, "妖精": 2, "毒": 0.5, "地面": 0.5}, "地面": {"火": 2, "電": 2, "毒": 2, "岩石": 2, "鋼": 2, "飛行": 0}, "飛行": {"草": 2, "格鬥": 2, "蟲": 2, "電": 0.5, "岩石": 0.5}, "超能力": {"格鬥": 2, "毒": 2, "超能力": 0.5, "惡": 0}, "蟲": {"草": 2, "超能力": 2, "惡": 2, "火": 0.5, "飛行": 0.5}, "岩石": {"火": 2, "冰": 2, "飛行": 2, "蟲": 2, "格鬥": 0.5, "地面": 0.5}, "鬼": {"超能力": 2, "鬼": 2, "一般": 0, "惡": 0.5}, "龍": {"龍": 2, "鋼": 0.5, "妖精": 0}, "惡": {"鬼": 2, "超能力": 2, "格鬥": 0.5, "妖精": 0.5}, "鋼": {"冰": 2, "岩石": 2, "妖精": 2, "火": 0.5, "水": 0.5}, "妖精": {"格鬥": 2, "龍": 2, "惡": 2, "毒": 0.5, "鋼": 0.5}}

def get_effectiveness(attacker_type, defender_type):
    if attacker_type not in TYPE_CHART: return 1.0
    return TYPE_CHART[attacker_type].get(defender_type, 1.0)

def page_battle():
    st.header("⚔️ 對戰分析")
    opponent = st.selectbox("選擇對手屬性", POKEMON_TYPES[:-1])
    
    if st.button("計算推薦隊伍"):
        if not st.session_state['inventory']:
            st.error("目前沒有卡片資料！")
            return
            
        recs = []
        for card in st.session_state['inventory']:
            best_move_score = 0
            best_move_str = ""
            
            for idx, m in enumerate(card['moves']):
                eff = get_effectiveness(m['type'], opponent)
                # 假設第二招威力略高
                power = 120 if idx == 1 else 100
                score = power * eff
                if score > best_move_score:
                    best_move_score = score
                    best_move_str = f"{m['name']}({m['type']})"
            
            # 特殊能力加權
            if card['tag'] != '無': best_move_score *= 1.2
            
            recs.append({
                "name": card['name'],
                "tag": card['tag'],
                "best_move": best_move_str,
                "score": best_move_score
            })
            
        recs.sort(key=lambda x: x['score'], reverse=True)
        
        # 簡單過濾重複tag
        final_team = []
        used_tags = set()
        
        for r in recs:
            if len(final_team) >= 3: break
            if r['tag'] != '無' and r['tag'] in used_tags: continue
            final_team.append(r)
            if r['tag'] != '無': used_tags.add(r['tag'])
            
        # 若不滿3隻則補滿
        if len(final_team) < 3:
            for r in recs:
                if len(final_team) >= 3: break
                if r not in final_team: final_team.append(r)
        
        for i, p in enumerate(final_team):
            st.success(f"第 {i+1} 棒: {p['name']} | {p['tag']} | 建議: {p['best_move']}")

# --- 主程式切換 ---
page = st.sidebar.radio("功能模式", ["新增卡片", "對戰分析"])

if page == "新增卡片":
    page_add_card()
else:
    page_battle()