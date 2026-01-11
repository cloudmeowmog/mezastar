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

# --- 輔助函式：AI 視覺辨識 (支援多圖) ---
def analyze_images_with_ai(image_list, prompt):
    if not api_key:
        st.error("❌ 請先設定 API Key")
        return None
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        # 建立內容請求清單：提示詞 + 圖片1 + 圖片2...
        request_content = [prompt]
        request_content.extend(image_list)
        
        response = model.generate_content(request_content)
        
        text = response.text
        # 清理 Markdown json 格式
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
    st.info("💡 提示：同時上傳正面與背面，AI 讀取的數值會更準確喔！")
    
    col_upload, col_data = st.columns([1, 2])
    
    with col_upload:
        st.subheader("1. 上傳照片")
        front_file = st.file_uploader("上傳【正面】", type=["jpg", "png", "jpeg"], key="front")
        back_file = st.file_uploader("上傳【背面】(選填)", type=["jpg", "png", "jpeg"], key="back")
        
        images_to_process = []
        if front_file:
            img_f = Image.open(front_file)
            st.image(img_f, caption="正面預覽", use_container_width=True)
            images_to_process.append(img_f)
            
        if back_file:
            img_b = Image.open(back_file)
            st.image(img_b, caption="背面預覽", use_container_width=True)
            images_to_process.append(img_b)

        if st.button("🔍 AI 辨識並加入資料庫"):
            if not api_key:
                st.error("請先填寫 API Key")
            elif not images_to_process:
                st.error("請至少上傳一張正面照片")
            else:
                with st.spinner("AI 正在綜合分析正反面資訊..."):
                    prompt = """
                    請辨識這些 Pokemon Mezastar 卡片圖片（可能包含正面與背面）。
                    請綜合兩張圖片的資訊，回傳 JSON 格式。
                    
                    規則：
                    1. name: 寶可夢名稱 (string)
                    2. type: 屬性 (string, 例如: 火, 水, 草...)
                    3. power: 數值/攻擊力 (int). 請優先在'背面'尋找詳細數值(例如總和或最大數值)，如果沒有背面，則看正面的數值。
                    4. tag: 特殊能力 (string). 只能是: 'Mega進化', 'Z招式', '極巨化', '雙重招式', '太晶化', '無'。請仔細檢查正反面是否有相關圖示。
                    
                    JSON 範例: {"name": "噴火龍", "type": "火", "power": 118, "tag": "極巨化"}
                    """
                    data = analyze_images_with_ai(images_to_process, prompt)
                    
                    if data:
                        st.success(f"成功辨識！加入: {data['name']}")
                        st.session_state['inventory'].append(data)
    
    with col_data:
        st.subheader("2. 目前卡匣清單")
        if st.session_state['inventory']:
            df = pd.DataFrame(st.session_state['inventory'])
            edited_df = st.data_editor(df, num_rows="dynamic", use_container_width=True)
            st.session_state['inventory'] = edited_df.to_dict('records')
            
            # 備份功能
            json_str = json.dumps(st.session_state['inventory'], ensure_ascii=False)
            st.download_button("⬇️ 下載備份 (.json)", json_str, "my_mezastar.json")
        else:
            st.info("目前沒有資料，請從左側上傳卡片。")

# --- 功能 2: 對戰分析 ---
def get_effectiveness(attacker_type, defender_type):
    if attacker_type not in TYPE_CHART: return 1.0
    return TYPE_CHART[attacker_type].get(defender_type, 1.0)

def page_battle():
    st.header("⚔️ 對戰分析與推薦")
    
    col1, col2 = st.columns(2)
    opponent_type = "一般"
    
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
                        prompt = "辨識畫面中對手的主要屬性(例如'火'或'水')，只回傳屬性名稱純文字。"
                        try:
                            model = genai.GenerativeModel('gemini-1.5-flash')
                            res = model.generate_content([prompt, img])
                            detected = res.text.strip().replace("屬性", "")
                            if detected in TYPE_CHART:
                                opponent_type = detected
                                st.session_state['last_opp'] = detected
                                st.success(f"偵測到：{opponent_type}")
                            else:
                                st.warning(f"偵測不明：{detected}，請手動選擇")
                        except Exception as e:
                            st.error(f"辨識失敗: {e}")

    with col2:
        st.subheader("2. 最佳隊伍推薦")
        if 'last_opp' in st.session_state:
            opponent_type = st.session_state['last_opp']
            
        st.markdown(f"目標對手屬性：**{opponent_type}**")
        
        if st.button("🚀 計算最佳組合"):
            if not st.session_state['inventory']:
                st.error("卡匣是空的！請先管理卡匣。")
            else:
                recs = []
                for card in st.session_state['inventory']:
                    eff = get_effectiveness(card['type'], opponent_type)
                    power = int(card.get('power', 100))
                    score = power * eff
                    if card['tag'] != '無': score *= 1.2
                    recs.append({**card, "eff": eff, "score": score})
                
                recs.sort(key=lambda x: x['score'], reverse=True)
                
                final_team = []
                used_tags = set()
                
                for card in recs:
                    if len(final_team) >= 3: break
                    tag = card['tag']
                    if tag != '無' and tag in used_tags: continue
                    final_team.append(card)
                    if tag != '無': used_tags.add(tag)
                
                if len(final_team) < 3:
                    for card in recs:
                        if len(final_team) >= 3: break
                        if card not in final_team: final_team.append(card)

                st.success("🏆 推薦出戰：")
                for p in final_team:
                    eff_txt = "🔥絕佳" if p['eff'] > 1 else "❄️不好" if p['eff'] < 1 else "普通"
                    st.markdown(f"**{p['name']}** ({p['type']}) | {p.get('tag','')} | 攻{p['power']} | {eff_txt}")

# --- 主導覽 ---
st.sidebar.title("導覽")
mode = st.sidebar.radio("Go to", ["卡匣管理", "對戰分析"])

if mode == "卡匣管理":
    page_inventory()
else:
    page_battle()