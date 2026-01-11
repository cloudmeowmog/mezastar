import streamlit as st
import pandas as pd
import google.generativeai as genai
from PIL import Image
import json

# --- 設定頁面 ---
st.set_page_config(page_title="Mezastar 攻略輔助", layout="wide", page_icon="🎮")

# ==========================================
# 👇👇👇 請把你的 API Key 貼在下面這行引號中 👇👇👇
# ==========================================
MY_SECRET_KEY = "AIzaSyAOLJg5mosQkA5ZwcHdwwrgGMjg59nngx8" 
# ==========================================

# --- 初始化 API ---
# 如果你有填寫上面的 Key，就用上面的；如果沒填，就讓使用者在網頁側邊欄輸入
if "AIza" in MY_SECRET_KEY:
    api_key = MY_SECRET_KEY
    st.sidebar.success("✅ 已載入程式碼中的 API Key")
else:
    st.sidebar.warning("⚠️ 程式碼中未填寫 API Key")
    api_key = st.sidebar.text_input("請輸入 Google Gemini API Key", type="password")

if api_key:
    genai.configure(api_key=api_key)

# 模擬本地資料庫 (使用 Session State 暫存)
if 'inventory' not in st.session_state:
    st.session_state['inventory'] = []

# --- 核心資料：屬性相剋表 (簡化版) ---
TYPE_CHART = {
    "一般": {"岩石": 0.5, "鬼": 0, "鋼": 0.5},
    "火": {"火": 0.5, "水": 0.5, "草": 2, "冰": 2, "蟲": 2, "岩石": 0.5, "龍": 0.5, "鋼": 2},
    "水": {"火": 2, "水": 0.5, "草": 0.5, "地面": 2, "岩石": 2, "龍": 0.5},
    "電": {"水": 2, "電": 0.5, "草": 0.5, "地面": 0, "飛行": 2, "龍": 0.5},
    "草": {"火": 0.5, "水": 2, "草": 0.5, "毒": 0.5, "地面": 2, "飛行": 0.5, "蟲": 0.5, "岩石": 2, "龍": 0.5, "鋼": 0.5},
    "冰": {"火": 0.5, "水": 0.5, "草": 2, "冰": 0.5, "地面": 2, "飛行": 2, "龍": 2, "鋼": 0.5},
    "格鬥": {"一般": 2, "冰": 2, "毒": 0.5, "飛行": 0.5, "超能力": 0.5, "蟲": 0.5, "岩石": 2, "鬼": 0, "惡": 2, "鋼": 2, "妖精": 0.5},
    "毒": {"草": 2, "毒": 0.5, "地面": 0.5, "岩石": 0.5, "鬼": 0.5, "鋼": 0, "妖精": 2},
    "地面": {"火": 2, "電": 2, "草": 0.5, "毒": 2, "飛行": 0, "蟲": 0.5, "岩石": 2, "鋼": 2},
    "飛行": {"電": 0.5, "草": 2, "格鬥": 2, "蟲": 2, "岩石": 0.5, "鋼": 0.5},
    "超能力": {"格鬥": 2, "毒": 2, "超能力": 0.5, "鋼": 0.5, "惡": 0},
    "蟲": {"火": 0.5, "草": 2, "格鬥": 0.5, "毒": 0.5, "飛行": 0.5, "超能力": 2, "鬼": 0.5, "惡": 2, "鋼": 0.5, "妖精": 0.5},
    "岩石": {"火": 2, "冰": 2, "格鬥": 0.5, "地面": 0.5, "飛行": 2, "蟲": 2, "鋼": 0.5},
    "鬼": {"一般": 0, "超能力": 2, "鬼": 2, "惡": 0.5},
    "龍": {"龍": 2, "鋼": 0.5, "妖精": 0},
    "惡": {"格鬥": 0.5, "超能力": 2, "鬼": 2, "惡": 0.5, "妖精": 0.5},
    "鋼": {"火": 0.5, "水": 0.5, "電": 0.5, "冰": 2, "岩石": 2, "鋼": 0.5, "妖精": 2},
    "妖精": {"火": 0.5, "格鬥": 2, "毒": 0.5, "龍": 2, "惡": 2, "鋼": 0.5}
}

# --- 輔助函式：AI 視覺辨識 ---
def analyze_image_with_ai(image, prompt):
    if not api_key:
        st.error("❌ 請先設定 API Key")
        return None
    try:
        # 使用 Flash 模型速度較快
        model = genai.GenerativeModel('gemini-1.5-flash')
        response = model.generate_content([prompt, image])
        
        # 嘗試清理並回傳 JSON
        text = response.text
        if "```json" in text:
            text = text.replace('```json', '').replace('```', '')
        elif "```" in text:
            text = text.replace('```', '')
            
        return json.loads(text)
    except Exception as e:
        st.error(f"AI 辨識失敗: {e}")
        return None

# --- 功能 1: 卡片管理 ---
def page_inventory():
    st.header("🗂️ 我的卡匣管理")
    
    col1, col2 = st.columns([1, 2])
    
    with col1:
        uploaded_file = st.file_uploader("上傳 Mezastar 卡片照片", type=["jpg", "png", "jpeg"])
        if uploaded_file is not None:
            image = Image.open(uploaded_file)
            st.image(image, caption="預覽圖片", use_container_width=True)
            
            if st.button("🔍 AI 辨識並加入資料庫"):
                if not api_key:
                    st.error("請先填寫 API Key")
                else:
                    with st.spinner("AI 正在分析卡片資訊..."):
                        prompt = """
                        請辨識這張 Pokemon Mezastar 卡片的以下資訊，並以 JSON 格式回傳，不要有其他文字。
                        請務必精準辨識數字與文字。
                        欄位包含：
                        - name (寶可夢名稱, string)
                        - type (屬性, 例如: 火, 水, 草, 電, 龍..., string)
                        - power (數值/攻擊力, int, 如果找不到就填 0)
                        - tag (特殊能力, string, 只能是以下其中之一: 'Mega進化', 'Z招式', '極巨化', '雙重招式', '太晶化', '無')
                        
                        JSON 範例: {"name": "皮卡丘", "type": "電", "power": 100, "tag": "Z招式"}
                        """
                        data = analyze_image_with_ai(image, prompt)
                        
                        if data:
                            st.success(f"成功辨識！加入: {data['name']}")
                            st.session_state['inventory'].append(data)
    
    with col2:
        st.subheader("目前卡匣清單")
        # 顯示目前資料庫
        if st.session_state['inventory']:
            df = pd.DataFrame(st.session_state['inventory'])
            # 讓使用者可以在表格上直接編輯修正 AI 的錯誤
            edited_df = st.data_editor(df, num_rows="dynamic", use_container_width=True)
            st.session_state['inventory'] = edited_df.to_dict('records')
            
            # 下載備份功能
            json_str = json.dumps(st.session_state['inventory'], ensure_ascii=False)
            st.download_button("⬇️ 下載卡匣備份 (.json)", json_str, "my_mezastar.json")
        else:
            st.info("目前沒有資料，請從左側上傳卡片。")

# --- 功能 2: 對戰分析 ---
def get_effectiveness(attacker_type, defender_type):
    if attacker_type not in TYPE_CHART: return 1.0
    return TYPE_CHART[attacker_type].get(defender_type, 1.0)

def page_battle():
    st.header("⚔️ 對戰分析與推薦")
    
    col1, col2 = st.columns(2)
    opponent_type = "一般" # 預設
    
    with col1:
        st.subheader("1. 取得對手資訊")
        tab_cam, tab_manual = st.tabs(["📸 拍照辨識", "✍️ 手動輸入"])
        
        with tab_manual:
            opponent_type = st.selectbox("選擇對手屬性", list(TYPE_CHART.keys()))
            
        with tab_cam:
            battle_file = st.file_uploader("上傳對戰畫面", type=["jpg", "png"])
            if battle_file and api_key:
                img = Image.open(battle_file)
                st.image(img, width=200)
                if st.button("辨識對手屬性"):
                    with st.spinner("AI 正在觀察對手..."):
                        prompt = """
                        這是一個 Pokemon 對戰畫面，請辨識'對手'（通常在畫面右上方或對面）的'主要屬性'是什麼。
                        只回傳屬性名稱純文字，例如：'火' 或 '水'。不要回傳 JSON，不要句號。
                        如果有多個屬性，回傳最主要的一個即可。
                        """
                        try:
                            model = genai.GenerativeModel('gemini-1.5-flash')
                            res = model.generate_content([prompt, img])
                            detected_type = res.text.strip()
                            # 簡單的清理
                            detected_type = detected_type.replace("屬性", "").strip()
                            
                            if detected_type in TYPE_CHART:
                                opponent_type = detected_type
                                st.success(f"偵測到對手屬性：{opponent_type}")
                                # 強制更新手動選單的值 (稍微 tricky，但在這顯示就好)
                                st.session_state['last_detected_opponent'] = opponent_type
                            else:
                                st.warning(f"偵測結果 '{detected_type}' 不在已知屬性表中，請手動選擇。")
                        except Exception as e:
                            st.error(f"辨識失敗: {e}")

    with col2:
        st.subheader("2. 最佳隊伍推薦")
        
        # 如果剛剛有偵測到，優先使用偵測到的
        if 'last_detected_opponent' in st.session_state:
            opponent_type = st.session_state['last_detected_opponent']
            
        st.info(f"目標對手屬性：**{opponent_type}**")
        
        if st.button("🚀 計算最佳組合"):
            if not st.session_state['inventory']:
                st.error("你的卡匣是空的！請先去 '卡匣管理' 上傳卡片。")
            else:
                recommendations = []
                inventory = st.session_state['inventory']
                
                # 1. 計算每張卡的基礎分數
                for card in inventory:
                    eff = get_effectiveness(card['type'], opponent_type)
                    base_power = int(card.get('power', 100))
                    if base_power == 0: base_power = 100
                    
                    score = base_power * eff
                    
                    # 特殊能力加權
                    if card['tag'] != '無':
                        score *= 1.2 
                        
                    recommendations.append({
                        **card,
                        "effectiveness": eff,
                        "score": score
                    })
                
                # 2. 排序並篩選 (確保特殊能力不重複)
                recommendations.sort(key=lambda x: x['score'], reverse=True)
                
                final_team = []
                used_tags = set()
                
                for card in recommendations:
                    if len(final_team) >= 3:
                        break
                    
                    tag = card['tag']
                    
                    # 邏輯：如果這個特殊能力已經用過了（且不是'無'），跳過
                    if tag != '無' and tag in used_tags:
                        continue 
                    
                    final_team.append(card)
                    if tag != '無':
                        used_tags.add(tag)
                
                # 如果湊不滿3隻，再從剩下的補
                if len(final_team) < 3:
                    for card in recommendations:
                        if len(final_team) >= 3: break
                        # 避免加入已經在隊伍裡的卡片 (這裡簡單用名稱判斷，如果有多張同名卡可能會誤判，建議未來加上 ID)
                        if card not in final_team:
                            final_team.append(card)

                # 顯示結果
                st.success("🏆 推薦出戰寶可夢：")
                for i, p in enumerate(final_team):
                    tag_display = f"✨{p['tag']}" if p['tag'] != '無' else ""
                    eff_val = p['effectiveness']
                    eff_text = "🔥 效果絕佳" if eff_val > 1 else ("❄️ 效果不好" if eff_val < 1 else "普通")
                    
                    st.markdown(f"""
                    ---
                    **第 {i+1} 棒： {p['name']}** ({p['type']})
                    * ⚔️ 攻擊力: {p['power']} | {tag_display}
                    * 🎯 對戰優勢: {eff_text} (x{eff_val})
                    """)

# --- 主導覽 ---
st.sidebar.title("導覽")
mode = st.sidebar.radio("Go to", ["卡匣管理", "對戰分析"])

if mode == "卡匣管理":
    page_inventory()
else:
    page_battle()

# --- Footer ---
st.sidebar.markdown("---")
st.sidebar.caption("Mezastar Assistant")