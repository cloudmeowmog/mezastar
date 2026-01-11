import streamlit as st
import pandas as pd
import google.generativeai as genai
from PIL import Image
import json
import os

# --- 設定頁面 ---
st.set_page_config(page_title="Mezastar 攻略輔助", layout="wide", page_icon="🎮")

# --- 側邊欄：設定與資料管理 ---
st.sidebar.title("⚙️ 設定 & 資料")
api_key = st.sidebar.text_input("輸入 Google Gemini API Key", type="password", help="請至 Google AI Studio 申請免費 API Key")

if api_key:
    genai.configure(api_key=api_key)

# 模擬本地資料庫 (使用 Session State 暫存，若要永久儲存需串接 JSON 檔或 SQLite)
if 'inventory' not in st.session_state:
    st.session_state['inventory'] = []

# --- 核心資料：屬性相剋表 (簡化版，1=正常, 2=效果絕佳, 0.5=效果不好, 0=無效) ---
# 為了程式簡潔，這裡列出主要邏輯，實際應用可擴充至完整 18 屬性
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
        return None
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        response = model.generate_content([prompt, image])
        # 清理並回傳 JSON
        text = response.text.replace('```json', '').replace('```', '')
        return json.loads(text)
    except Exception as e:
        st.error(f"AI 辨識失敗: {e}")
        return None

# --- 功能 1: 卡片管理 ---
def page_inventory():
    st.header("🗂️ 我的卡匣管理")
    st.info("上傳卡片照片，AI 自動辨識並建檔。")
    
    uploaded_file = st.file_uploader("上傳 Mezastar 卡片照片", type=["jpg", "png", "jpeg"])
    
    if uploaded_file is not None:
        image = Image.open(uploaded_file)
        st.image(image, caption="預覽圖片", width=300)
        
        if st.button("🔍 AI 辨識並加入資料庫") and api_key:
            with st.spinner("AI 正在分析卡片資訊..."):
                prompt = """
                請辨識這張 Pokemon Mezastar 卡片的以下資訊，並以 JSON 格式回傳，不要有其他文字。
                欄位包含：
                - name (寶可夢名稱, string)
                - type (屬性, 例如: 火, 水, 草..., string)
                - power (數值/攻擊力, int, 如果找不到就填 0)
                - tag (特殊能力, string, 只能是以下其中之一或 '無': 'Mega進化', 'Z招式', '極巨化', '雙重招式', '太晶化')
                
                JSON 範例: {"name": "皮卡丘", "type": "電", "power": 100, "tag": "Z招式"}
                """
                data = analyze_image_with_ai(image, prompt)
                
                if data:
                    st.success(f"成功辨識！加入: {data['name']}")
                    st.session_state['inventory'].append(data)
    
    # 顯示目前資料庫
    if st.session_state['inventory']:
        df = pd.DataFrame(st.session_state['inventory'])
        st.dataframe(df, use_container_width=True)
        
        # 下載備份功能
        json_str = json.dumps(st.session_state['inventory'], ensure_ascii=False)
        st.download_button("⬇️ 下載卡匣備份 (.json)", json_str, "my_mezastar.json")

# --- 功能 2: 對戰分析 ---
def get_effectiveness(attacker_type, defender_type):
    # 預設係數為 1
    if attacker_type not in TYPE_CHART: return 1.0
    return TYPE_CHART[attacker_type].get(defender_type, 1.0)

def page_battle():
    st.header("⚔️ 對戰分析與推薦")
    st.info("上傳對戰畫面（或是手動輸入對手屬性），系統將從你的卡匣推薦最佳 3 張卡。")
    
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
                    prompt = """
                    這是一個 Pokemon 對戰畫面，請辨識'對手'（通常在畫面右上方或對面）的'主要屬性'是什麼。
                    只回傳屬性名稱，例如：'火' 或 '水'。不要回傳 JSON，只要純文字。
                    """
                    # 簡單處理，直接呼叫模型
                    try:
                        model = genai.GenerativeModel('gemini-1.5-flash')
                        res = model.generate_content([prompt, img])
                        detected_type = res.text.strip()
                        if detected_type in TYPE_CHART:
                            opponent_type = detected_type
                            st.success(f"偵測到對手屬性：{opponent_type}")
                        else:
                            st.warning(f"偵測結果 '{detected_type}' 不在已知屬性表中，請手動選擇。")
                    except:
                        st.error("辨識失敗")

    with col2:
        st.subheader("2. 最佳隊伍推薦")
        st.write(f"對手屬性：**{opponent_type}**")
        
        if st.button("🚀 計算最佳組合"):
            if not st.session_state['inventory']:
                st.error("你的卡匣是空的！請先去 '卡匣管理' 上傳卡片。")
            else:
                recommendations = []
                inventory = st.session_state['inventory']
                
                # 1. 計算每張卡的基礎分數
                for card in inventory:
                    eff = get_effectiveness(card['type'], opponent_type)
                    
                    # 簡單評分公式：攻擊力 * 屬性剋制倍率
                    # 若無攻擊力資料，預設給 100 方便計算
                    base_power = card.get('power', 100)
                    if base_power == 0: base_power = 100
                    
                    score = base_power * eff
                    
                    # 特殊能力加權 (因為有特殊能力通常比較強)
                    if card['tag'] != '無':
                        score *= 1.2 
                        
                    recommendations.append({
                        **card,
                        "effectiveness": eff,
                        "score": score
                    })
                
                # 2. 排序並篩選 (貪婪演算法：優先選分數高的，但要過濾重複機制)
                # 規則：希望特殊能力多樣化 (例如: 1隻Mega, 1隻Z招, 1隻極巨)
                
                recommendations.sort(key=lambda x: x['score'], reverse=True)
                
                final_team = []
                used_tags = set()
                
                for card in recommendations:
                    if len(final_team) >= 3:
                        break
                    
                    tag = card['tag']
                    
                    # 邏輯：如果這個特殊能力已經用過了（且不是'無'），則稍微降低優先權或跳過
                    # 這裡示範嚴格模式：每種特殊能力只能有一隻 (除了'無')
                    if tag != '無' and tag in used_tags:
                        continue # 跳過這隻，找下一隻
                    
                    final_team.append(card)
                    if tag != '無':
                        used_tags.add(tag)
                
                # 如果湊不滿3隻 (因為特殊能力重複太嚴重)，再從剩下的補
                if len(final_team) < 3:
                    for card in recommendations:
                        if len(final_team) >= 3: break
                        if card not in final_team:
                            final_team.append(card)

                # 顯示結果
                st.success("推薦隊伍組合：")
                for i, p in enumerate(final_team):
                    tag_display = f"✨{p['tag']}" if p['tag'] != '無' else ""
                    eff_text = "效果絕佳! 🔥" if p['effectiveness'] > 1 else ("效果不好 ❄️" if p['effectiveness'] < 1 else "普通")
                    
                    st.markdown(f"""
                    **{i+1}. {p['name']}** ({p['type']}) {tag_display}
                    * 預估傷害分數: {int(p['score'])}
                    * 對 {opponent_type} 屬性: {eff_text} (x{p['effectiveness']})
                    """)

# --- 主導覽 ---
mode = st.sidebar.radio("選擇模式", ["卡匣管理", "對戰分析"])

if mode == "卡匣管理":
    page_inventory()
else:
    page_battle()

# --- Footer ---
st.sidebar.markdown("---")
st.sidebar.caption("Mezastar Assistant v1.0 | Built with Streamlit")