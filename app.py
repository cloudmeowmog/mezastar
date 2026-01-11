import streamlit as st
import pandas as pd
import google.generativeai as genai
from PIL import Image
import json
import os

# --- 設定頁面 ---
st.set_page_config(page_title="Mezastar 檔案室", layout="wide", page_icon="🗃️")

# --- API Key 管理 (為了對戰分析保留) ---
if "gemini_api_key" in st.secrets:
    api_key = st.secrets["gemini_api_key"]
else:
    api_key = st.sidebar.text_input("Google Gemini API Key (對戰分析用)", type="password")

if api_key:
    genai.configure(api_key=api_key)

# --- 資料庫初始化 ---
if 'inventory' not in st.session_state:
    st.session_state['inventory'] = []

# --- 上傳元件重置金鑰初始化 (解決第二張圖讀不到的問題) ---
if 'uploader_key' not in st.session_state:
    st.session_state['uploader_key'] = 0

# --- 常數定義 ---
POKEMON_TYPES = [
    "一般", "火", "水", "草", "電", "冰", "格鬥", "毒", "地面", 
    "飛行", "超能力", "蟲", "岩石", "鬼", "龍", "惡", "鋼", "妖精", "無"
]

SPECIAL_TAGS = [
    "無", "Mega進化", "Z招式", "極巨化", "太晶化", "特別聯手對戰", "雙重招式"
]

# --- 功能 1: 新增卡片 (修復版) ---
def page_add_card():
    st.header("🗃️ 新增 Mezastar 卡片資料")
    
    col_preview, col_edit = st.columns([1, 2])
    
    with col_preview:
        st.subheader("1. 圖片上傳")
        
        # 使用動態 Key，每次 uploader_key 改變時，這裡的元件就會被強制重置
        current_key = st.session_state['uploader_key']
        
        front_file = st.file_uploader(
            "上傳【正面】(自動帶入檔名)", 
            type=["jpg", "png", "jpeg"], 
            key=f"u_front_{current_key}" # <--- 關鍵修改：綁定動態 ID
        )
        
        back_file = st.file_uploader(
            "上傳【背面】", 
            type=["jpg", "png", "jpeg"], 
            key=f"u_back_{current_key}" # <--- 關鍵修改：綁定動態 ID
        )
        
        # --- 自動讀取檔名邏輯 ---
        if front_file:
            st.image(Image.open(front_file), caption="正面預覽", use_container_width=True)
            
            # 檢查這個檔案是否已經處理過名稱
            # 我們用檔案名稱來判斷 (如果使用者換了圖片，名稱會變，就會觸發)
            if 'last_processed_file' not in st.session_state or st.session_state['last_processed_file'] != front_file.name:
                
                # 解析檔名
                filename = os.path.splitext(front_file.name)[0]
                for suffix in ["_前", "_front", "正面"]:
                    if filename.endswith(suffix):
                        filename = filename.replace(suffix, "")
                        break
                
                # 更新輸入框
                st.session_state['card_name_input'] = filename
                
                # 標記此檔案已處理，避免無限迴圈
                st.session_state['last_processed_file'] = front_file.name
                
                # 強制刷新頁面以顯示新名稱
                st.rerun()

        if back_file:
            st.image(Image.open(back_file), caption="背面預覽", use_container_width=True)

    with col_edit:
        st.subheader("2. 資料編輯")
        
        with st.form("card_form", clear_on_submit=True):
            # 卡片名稱
            st.text_input("卡片名稱", key="card_name_input")
            
            # 特殊能力
            st.selectbox("特殊能力", SPECIAL_TAGS, key="tag_input")
            
            st.markdown("---")
            st.markdown("**寶可夢屬性**")
            c1, c2 = st.columns(2)
            c1.selectbox("屬性 1", POKEMON_TYPES, key="t1_input")
            c2.selectbox("屬性 2", POKEMON_TYPES, index=len(POKEMON_TYPES)-1, key="t2_input")
            
            st.markdown("---")
            st.markdown("**招式資訊**")
            
            # 招式 1
            mc1_a, mc1_b = st.columns([2, 1])
            mc1_a.text_input("一般招式名稱", placeholder="例如：電光一閃", key="m1_name_input")
            mc1_b.selectbox("屬性", POKEMON_TYPES, key="m1_type_input")
            
            # 招式 2
            mc2_a, mc2_b = st.columns([2, 1])
            mc2_a.text_input("特殊/強力招式名稱", placeholder="例如：千萬伏特", key="m2_name_input")
            mc2_b.selectbox("屬性", POKEMON_TYPES, key="m2_type_input")
            
            submitted = st.form_submit_button("💾 加入資料庫", type="primary")
            
            if submitted:
                # 取得資料
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
                st.success(f"已新增：{name}")
                
                # --- 關鍵修復步驟 ---
                # 1. 清除「上一個處理過的檔案」紀錄
                if 'last_processed_file' in st.session_state:
                    del st.session_state['last_processed_file']
                
                # 2. 增加 uploader_key，這會強制讓左邊的上傳按鈕「完全重置」變回空白
                st.session_state['uploader_key'] += 1
                
                # 3. 重新整理頁面
                st.rerun()

    # 清單列表
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
        
        json_str = json.dumps(st.session_state['inventory'], ensure_ascii=False)
        st.download_button("⬇️ 下載資料庫備份 (.json)", json_str, "mezastar_db.json")

# --- 功能 2: 對戰分析 ---
TYPE_CHART = {"一般": {"岩石": 0.5, "鬼": 0, "鋼": 0.5}, "火": {"草": 2, "冰": 2, "蟲": 2, "鋼": 2, "水": 0.5, "火": 0.5}, "水": {"火": 2, "地面": 2, "岩石": 2, "水": 0.5, "草": 0.5}, "電": {"水": 2, "飛行": 2, "地面": 0, "電": 0.5}, "草": {"水": 2, "地面": 2, "岩石": 2, "火": 0.5, "草": 0.5}, "冰": {"草": 2, "地面": 2, "飛行": 2, "龍": 2, "火": 0.5, "冰": 0.5}, "格鬥": {"一般": 2, "冰": 2, "岩石": 2, "惡": 2, "鋼": 2, "鬼": 0}, "毒": {"草": 2, "妖精": 2, "毒": 0.5, "地面": 0.5}, "地面": {"火": 2, "電": 2, "毒": 2, "岩石": 2, "鋼": 2, "飛行": 0}, "飛行": {"草": 2, "格鬥": 2, "蟲": 2, "電": 0.5, "岩石": 0.5}, "超能力": {"格鬥": 2, "毒": 2, "超能力": 0.5, "惡": 0}, "蟲": {"草": 2, "超能力": 2, "惡": 2, "火": 0.5, "飛行": 0.5}, "岩石": {"火": 2, "冰": 2, "飛行": 2, "蟲": 2, "格鬥": 0.5, "地面": 0.5}, "鬼": {"超能力": 2, "鬼": 2, "一般": 0, "惡": 0.5}, "龍": {"龍": 2, "鋼": 0.5, "妖精": 0}, "惡": {"鬼": 2, "超能力": 2, "格鬥": 0.5, "妖精": 0.5}, "鋼": {"冰": 2, "岩石": 2, "妖精": 2, "火": 0.5, "水": 0.5}, "妖精": {"格鬥": 2, "龍": 2, "惡": 2, "毒": 0.5, "鋼": 0.5}}

def get_effectiveness(attacker_type, defender_type):
    if attacker_type not in TYPE_CHART: return 1.0
    return TYPE_CHART[attacker_type].get(defender_type, 1.0)

def page_battle():
    st.header("⚔️ 對戰分析")
    st.info("這裡使用 AI 辨識對手畫面，若 API 故障請手動選擇屬性。")
    
    col_op, col_rec = st.columns(2)
    opponent_type = "一般"
    
    with col_op:
        st.subheader("1. 對手資訊")
        tab_cam, tab_man = st.tabs(["📸 拍照辨識", "✍️ 手動選擇"])
        
        with tab_man:
            opponent_type = st.selectbox("選擇對手屬性", POKEMON_TYPES[:-1])
            
        with tab_cam:
            battle_file = st.file_uploader("上傳對戰畫面", type=["jpg", "png"])
            if battle_file:
                img = Image.open(battle_file)
                st.image(img, width=200)
                if st.button("辨識對手屬性"):
                    if not api_key:
                        st.error("請先設定 API Key 才能使用辨識功能")
                    else:
                        with st.spinner("AI 正在觀察..."):
                            try:
                                model = genai.GenerativeModel('gemini-1.5-flash')
                                prompt = "辨識畫面中對手的主要屬性(例如'火'或'水')，只回傳屬性名稱純文字。"
                                res = model.generate_content([prompt, img])
                                detected = res.text.strip().replace("屬性", "")
                                if detected in TYPE_CHART:
                                    st.session_state['detected_opp'] = detected
                                    st.success(f"偵測到：{detected}")
                                    st.rerun()
                                else:
                                    st.warning(f"偵測不明：{detected}")
                            except Exception as e:
                                st.error(f"辨識失敗: {e}")
            
            if 'detected_opp' in st.session_state:
                opponent_type = st.session_state['detected_opp']
                st.write(f"目前鎖定對手：**{opponent_type}**")

    with col_rec:
        st.subheader("2. 推薦隊伍")
        if st.button("計算最佳組合"):
            if not st.session_state['inventory']:
                st.error("卡匣是空的！請先去【新增卡片】建立資料。")
            else:
                recs = []
                for card in st.session_state['inventory']:
                    best_score = 0
                    best_move = ""
                    
                    for idx, m in enumerate(card['moves']):
                        if not m['name']: continue
                        eff = get_effectiveness(m['type'], opponent_type)
                        base = 120 if idx == 1 else 100
                        score = base * eff
                        
                        if score > best_score:
                            best_score = score
                            best_move = f"{m['name']}({m['type']})"
                    
                    if card['tag'] != '無': best_score *= 1.2
                    
                    recs.append({
                        "name": card['name'],
                        "tag": card['tag'],
                        "move": best_move,
                        "score": best_score
                    })
                
                recs.sort(key=lambda x: x['score'], reverse=True)
                
                for i, p in enumerate(recs[:3]):
                    st.success(f"第 {i+1} 名: **{p['name']}** ({p['tag']}) | 建議: {p['move']}")

# --- 主程式切換 ---
page = st.sidebar.radio("模式", ["新增卡片", "對戰分析"])

if page == "新增卡片":
    page_add_card()
else:
    page_battle()