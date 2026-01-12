import streamlit as st
import pandas as pd
import json
import os
import numpy as np
import cv2 # 需安裝: pip install opencv-python-headless
from PIL import Image
# 必須安裝: pip install streamlit-cropper
# 線上版請務必在 requirements.txt 加入 streamlit-cropper
from streamlit_cropper import st_cropper 

# --- 設定頁面 ---
st.set_page_config(page_title="Mezastar 檔案室", layout="wide", page_icon="🗃️")

# --- 設定資料庫與圖示路徑 ---
DB_FILE = "mezastar_db.json"
IMG_DIR = "cardinfo"
ICON_DIR = "att_icon" 

# 確保目錄存在
for d in [IMG_DIR, ICON_DIR]:
    if not os.path.exists(d):
        os.makedirs(d)

# --- Helper: 排序資料庫 ---
def sort_inventory(data):
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

# --- Helper: 儲存卡片圖片 ---
def save_card_images(name):
    current_key = st.session_state.get('uploader_key', 0)
    front = st.session_state.get(f"u_front_{current_key}")
    back = st.session_state.get(f"u_back_{current_key}")
    
    if front:
        Image.open(front).save(os.path.join(IMG_DIR, f"{name}_前.png"), "PNG")
    if back:
        Image.open(back).save(os.path.join(IMG_DIR, f"{name}_後.png"), "PNG")

# --- Helper: 核心辨識邏輯 (50% 縮放加速版) ---
def detect_attribute_icons(uploaded_image):
    """
    策略：
    1. 將輸入圖片長寬各縮小一半 (0.5x)，加速運算。
    2. 載入範本時，也同步縮小一半，維持 1:1 的比對比例。
    """
    # 1. 讀取圖片
    file_bytes = np.asarray(bytearray(uploaded_image.read()), dtype=np.uint8)
    img_bgr = cv2.imdecode(file_bytes, 1)
    if img_bgr is None: return [[], [], []]

    # 2. 影像前處理 (縮小 50%)
    h, w, _ = img_bgr.shape
    new_w, new_h = w // 2, h // 2
    img_resized = cv2.resize(img_bgr, (new_w, new_h))
    
    # 取下半部 ROI (0.55 ~ 0.98)
    start_y = int(new_h * 0.55)
    end_y = int(new_h * 0.98)
    img_roi = img_resized[start_y:end_y, :]
    
    roi_h, roi_w = img_roi.shape[:2]
    
    # 3. 載入範本 (Templates) 並同步縮小
    template_groups = {}
    if os.path.exists(ICON_DIR):
        for filename in os.listdir(ICON_DIR):
            if filename.endswith(".png"):
                # 檔名格式: "火_123456.png" -> 取 "火"
                type_name = filename.split("_")[0]
                icon_path = os.path.join(ICON_DIR, filename)
                t_img = cv2.imread(icon_path)
                if t_img is not None:
                    # *** 關鍵修正：範本也要縮小 50% ***
                    t_img_small = cv2.resize(t_img, (0, 0), fx=0.5, fy=0.5)
                    
                    if type_name not in template_groups:
                        template_groups[type_name] = []
                    template_groups[type_name].append(t_img_small)

    if not template_groups:
        st.warning("⚠️ 尚未建立圖示範本！請先至「🛠️ 建立圖示範本」分頁建立範本。")
        return [[], [], []]

    # 4. 比對流程
    detected_results = [set(), set(), set()]
    col_w = roi_w // 3
    
    # 進度條
    progress_bar = st.progress(0, text="正在進行快速掃描 (0.5x)...")
    total_types = len(template_groups)
    current_step = 0

    for type_name, templ_list in template_groups.items():
        current_step += 1
        progress_bar.progress(int(current_step / total_types * 100), text=f"比對屬性: {type_name}")

        for templ in templ_list:
            # 即使縮小了，還是做一點點多尺度 (0.9 ~ 1.1) 以防微小的距離差異
            scales = np.linspace(0.9, 1.1, 3)
            
            for scale in scales:
                t_h, t_w = templ.shape[:2]
                new_tw, new_th = int(t_w * scale), int(t_h * scale)
                
                if new_tw > roi_w or new_th > roi_h: continue
                
                resized_templ = cv2.resize(templ, (new_tw, new_th))
                
                # 使用 TM_CCOEFF_NORMED
                res = cv2.matchTemplate(img_roi, resized_templ, cv2.TM_CCOEFF_NORMED)
                
                # 門檻設為 0.7
                loc = np.where(res >= 0.7)
                
                for pt in zip(*loc[::-1]):
                    x, y = pt
                    center_x = x + new_tw // 2
                    c_idx = 0
                    if center_x > col_w and center_x < col_w*2: c_idx = 1
                    elif center_x >= col_w*2: c_idx = 2
                    
                    detected_results[c_idx].add(type_name)
    
    progress_bar.empty()
    uploaded_image.seek(0)
    return [list(s) for s in detected_results]

# --- 初始化 Session State ---
if 'inventory' not in st.session_state:
    st.session_state['inventory'] = load_db()
if 'uploader_key' not in st.session_state:
    st.session_state['uploader_key'] = 0
if 'last_battle_img' not in st.session_state:
    st.session_state['last_battle_img'] = None

defaults = {
    "add_name_input": "", "add_attack_input": 100, "add_sp_attack_input": 100, "add_tag_input": "無",
    "add_t1_input": "一般", "add_t2_input": "無", "add_m1_name_input": "", "add_m1_type_input": "一般", "add_m1_cat_input": "攻擊",
    "add_m2_name_input": "", "add_m2_type_input": "一般", "add_m2_cat_input": "攻擊", "msg_area": "",
    "edit_select_index": 0, "edit_name_input": "", "edit_attack_input": 100, "edit_sp_attack_input": 100,
    "edit_tag_input": "無", "edit_t1_input": "一般", "edit_t2_input": "無", "edit_m1_name_input": "",
    "edit_m1_type_input": "一般", "edit_m1_cat_input": "攻擊", "edit_m2_name_input": "",
    "edit_m2_type_input": "一般", "edit_m2_cat_input": "攻擊", "manage_sub_mode": "➕ 新增卡片",
    "battle_config": [
        {"name": "對手 1 (左)", "manual_t1": "無", "manual_t2": "無", "detected_weakness": []},
        {"name": "對手 2 (中)", "manual_t1": "無", "manual_t2": "無", "detected_weakness": []},
        {"name": "對手 3 (右)", "manual_t1": "無", "manual_t2": "無", "detected_weakness": []}
    ]
}
for key, val in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = val

POKEMON_TYPES = ["一般", "火", "水", "草", "電", "冰", "格鬥", "毒", "地面", "飛行", "超能力", "蟲", "岩石", "幽靈", "龍", "惡", "鋼", "妖精", "無"]
SPECIAL_TAGS = ["無", "Mega進化", "Z招式", "極巨化", "太晶化", "特別聯手對戰", "雙重招式"]
MOVE_CATEGORIES = ["攻擊", "特攻"]

# --- Helper Functions ---
@st.dialog("卡片影像預覽", width="large")
def show_card_image_modal(card_name):
    st.subheader(card_name)
    col_img, _ = st.columns([1, 0.1])
    f_path, b_path = os.path.join(IMG_DIR, f"{card_name}_前.png"), os.path.join(IMG_DIR, f"{card_name}_後.png")
    with col_img:
        if os.path.exists(f_path): st.image(f_path, caption="正面", use_container_width=True)
        else: st.warning("無正面影像")
        if os.path.exists(b_path): st.image(b_path, caption="背面", use_container_width=True)
        else: st.warning("無背面影像")

def fill_edit_fields():
    if not st.session_state['inventory']: return
    idx = st.session_state.get('edit_select_index', 0)
    if idx >= len(st.session_state['inventory']): idx = 0
    c = st.session_state['inventory'][idx]
    st.session_state.update({
        'edit_name_input': c['name'], 'edit_attack_input': c.get('attack', 100), 'edit_sp_attack_input': c.get('sp_attack', 100),
        'edit_tag_input': c['tag'], 'edit_t1_input': c['type'], 'edit_t2_input': c.get('type2', '無'),
        'edit_m1_name_input': c['moves'][0]['name'], 'edit_m1_type_input': c['moves'][0]['type'], 'edit_m1_cat_input': c['moves'][0].get('category', '攻擊'),
        'edit_m2_name_input': c['moves'][1]['name'], 'edit_m2_type_input': c['moves'][1]['type'], 'edit_m2_cat_input': c['moves'][1].get('category', '攻擊')
    })

def common_save(is_new=False):
    key_prefix = "add" if is_new else "edit"
    card = {
        "name": st.session_state[f"{key_prefix}_name_input"],
        "attack": st.session_state[f"{key_prefix}_attack_input"],
        "sp_attack": st.session_state[f"{key_prefix}_sp_attack_input"],
        "tag": st.session_state[f"{key_prefix}_tag_input"],
        "type": st.session_state[f"{key_prefix}_t1_input"],
        "type2": st.session_state[f"{key_prefix}_t2_input"],
        "moves": [
            {"name": st.session_state[f"{key_prefix}_m1_name_input"], "type": st.session_state[f"{key_prefix}_m1_type_input"], "category": st.session_state[f"{key_prefix}_m1_cat_input"]},
            {"name": st.session_state[f"{key_prefix}_m2_name_input"], "type": st.session_state[f"{key_prefix}_m2_type_input"], "category": st.session_state[f"{key_prefix}_m2_cat_input"]}
        ]
    }
    if is_new:
        save_card_images(card['name'])
        st.session_state['inventory'].append(card)
        msg = f"✅ 已新增並存檔：{card['name']}"
        st.session_state.update({k: v for k, v in defaults.items() if k.startswith("add_")})
        st.session_state['uploader_key'] += 1
    else:
        idx = st.session_state['edit_select_index']
        st.session_state['inventory'][idx] = card
        msg = f"✅ 已更新並存檔：{card['name']}"
    
    sort_inventory(st.session_state['inventory'])
    save_db(st.session_state['inventory'])
    st.session_state['msg_area'] = msg
    if not is_new: fill_edit_fields()

def delete_card_callback():
    idx = st.session_state['edit_select_index']
    if idx < len(st.session_state['inventory']):
        removed = st.session_state['inventory'].pop(idx)
        save_db(st.session_state['inventory'])
        st.session_state['msg_area'] = f"🗑️ 已刪除：{removed['name']}"
        st.session_state['edit_select_index'] = 0
        fill_edit_fields()

# --- Page: Template Creator (滑鼠框選版) ---
def page_template_creator():
    st.header("🛠️ 建立圖示範本 (訓練模式)")
    st.info("請上傳螢幕截圖，用滑鼠直接框選屬性圖示，然後儲存為範本。")
    st.markdown("> **注意**：這裡建立的範本是高解析度的，程式在比對時會自動與縮小後的截圖同步處理。")
    
    uploaded_file = st.file_uploader("上傳含有屬性圖示的照片", type=["jpg", "png", "jpeg"], key="template_uploader")
    
    if uploaded_file:
        img = Image.open(uploaded_file)
        
        st.markdown("👇 **直接在下方圖片上用滑鼠拖曳框選一個圖示：**")
        
        # 使用 st_cropper，預設 box_color 為紅，回傳的 cropped_img 會是原始解析度
        cropped_img = st_cropper(img, realtime_update=True, box_color='#FF0000', aspect_ratio=(1,1), key="cropper")
        
        st.markdown("---")
        col_preview, col_save = st.columns([1, 2])
        
        with col_preview:
            st.image(cropped_img, caption="裁切預覽 (原圖解析度)", width=100)
            
        with col_save:
            icon_type = st.selectbox("這是什麼屬性？", POKEMON_TYPES, key="icon_type_selector")
            
            if st.button("💾 儲存此範本"):
                if cropped_img:
                    timestamp = int(pd.Timestamp.now().timestamp())
                    save_name = f"{icon_type}_{timestamp}.png"
                    save_path = os.path.join(ICON_DIR, save_name)
                    
                    img_array = np.array(cropped_img)
                    img_bgr = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
                    
                    cv2.imwrite(save_path, img_bgr)
                    st.success(f"✅ 已儲存範本：{save_name}")
                else:
                    st.error("裁切無效")

    # 管理現有範本
    st.markdown("---")
    st.markdown("### 📚 目前的圖示範本庫")
    if os.path.exists(ICON_DIR):
        files = os.listdir(ICON_DIR)
        files.sort()
        if files:
            img_files = [f for f in files if f.endswith(".png")]
            if img_files:
                count_dict = {}
                for f in img_files:
                    t = f.split("_")[0]
                    count_dict[t] = count_dict.get(t, 0) + 1
                
                st.write(f"總計 {len(img_files)} 個範本。")
                
                cols = st.columns(8)
                for i, f in enumerate(img_files):
                    with cols[i % 8]:
                        st.image(os.path.join(ICON_DIR, f), caption=f.split("_")[0])
                        if st.button("🗑️", key=f"del_{f}"):
                            os.remove(os.path.join(ICON_DIR, f))
                            st.rerun() 
            else:
                st.info("資料夾內無 PNG 圖片。")
        else:
            st.info("目前沒有範本。")

# --- Page: Manage Cards ---
def page_manage_cards():
    st.header("🗃️ 卡片資料庫管理")
    st.sidebar.markdown("---")
    if st.sidebar.button("手動強制存檔", type="secondary"): save_db(st.session_state['inventory'])
    if st.session_state['msg_area']: st.success(st.session_state['msg_area']); st.session_state['msg_area'] = ""
    
    sub = st.radio("功能", ["➕ 新增卡片", "✏️ 編輯與刪除"], horizontal=True, key="manage_sub_mode")
    st.markdown("---")
    
    if sub == "➕ 新增卡片":
        c1, c2 = st.columns([1, 2])
        with c1:
            key = st.session_state['uploader_key']
            f = st.file_uploader("正面", type=["jpg","png"], key=f"u_front_{key}")
            b = st.file_uploader("背面", type=["jpg","png"], key=f"u_back_{key}")
            if f: 
                st.image(f, caption="正面預覽", use_container_width=True)
                if 'last_p' not in st.session_state or st.session_state['last_p'] != f.name:
                    n = os.path.splitext(f.name)[0].replace("_前", "").replace("_front", "")
                    st.session_state['add_name_input'] = n
                    st.session_state['last_p'] = f.name
            if b: st.image(b, caption="背面預覽", use_container_width=True)
        with c2:
            with st.form("add"):
                st.text_input("名稱", key="add_name_input")
                c_s1, c_s2 = st.columns(2)
                c_s1.number_input("攻擊", min_value=0, step=1, key="add_attack_input")
                c_s2.number_input("特攻", min_value=0, step=1, key="add_sp_attack_input")
                st.selectbox("特殊能力", SPECIAL_TAGS, key="add_tag_input")
                c_t1, c_t2 = st.columns(2)
                c_t1.selectbox("屬性1", POKEMON_TYPES, key="add_t1_input")
                c_t2.selectbox("屬性2", POKEMON_TYPES, index=len(POKEMON_TYPES)-1, key="add_t2_input")
                st.markdown("---")
                m1a, m1b, m1c = st.columns([2,1,1])
                m1a.text_input("一般招式", key="add_m1_name_input")
                m1b.selectbox("屬性", POKEMON_TYPES, key="add_m1_type_input")
                m1c.selectbox("分類", MOVE_CATEGORIES, key="add_m1_cat_input")
                m2a, m2b, m2c = st.columns([2,1,1])
                m2a.text_input("強力招式", key="add_m2_name_input")
                m2b.selectbox("屬性", POKEMON_TYPES, key="add_m2_type_input")
                m2c.selectbox("分類", MOVE_CATEGORIES, key="add_m2_cat_input")
                st.form_submit_button("💾 新增並存檔", type="primary", on_click=lambda: common_save(True))

    else: # Edit
        if not st.session_state['inventory']: st.info("無資料"); return
        sort_inventory(st.session_state['inventory'])
        opts = [f"{i+1}. {c['name']}" for i, c in enumerate(st.session_state['inventory'])]
        st.selectbox("選擇卡片", range(len(opts)), format_func=lambda x: opts[x], key="edit_select_index", on_change=fill_edit_fields)
        if not st.session_state['edit_name_input']: fill_edit_fields()
        
        c1, c2 = st.columns([3, 1])
        with c1:
            with st.form("edit"):
                st.text_input("名稱", key="edit_name_input")
                c_s1, c_s2 = st.columns(2)
                c_s1.number_input("攻擊", key="edit_attack_input")
                c_s2.number_input("特攻", key="edit_sp_attack_input")
                st.selectbox("特殊", SPECIAL_TAGS, key="edit_tag_input")
                c_t1, c_t2 = st.columns(2)
                c_t1.selectbox("屬性1", POKEMON_TYPES, key="edit_t1_input")
                c_t2.selectbox("屬性2", POKEMON_TYPES, key="edit_t2_input")
                st.markdown("---")
                m1a, m1b, m1c = st.columns([2,1,1])
                m1a.text_input("一般招式", key="edit_m1_name_input")
                m1b.selectbox("屬性", POKEMON_TYPES, key="edit_m1_type_input")
                m1c.selectbox("分類", MOVE_CATEGORIES, key="edit_m1_cat_input")
                m2a, m2b, m2c = st.columns([2,1,1])
                m2a.text_input("強力招式", key="edit_m2_name_input")
                m2b.selectbox("屬性", POKEMON_TYPES, key="edit_m2_type_input")
                m2c.selectbox("分類", MOVE_CATEGORIES, key="edit_m2_cat_input")
                st.form_submit_button("✅ 更新並存檔", type="primary", on_click=lambda: common_save(False))
        with c2:
            st.button("🗑️ 刪除", type="secondary", on_click=delete_card_callback)
            cn = st.session_state['edit_name_input']
            if cn:
                fp, bp = os.path.join(IMG_DIR, f"{cn}_前.png"), os.path.join(IMG_DIR, f"{cn}_後.png")
                if os.path.exists(fp): st.image(fp, caption="正")
                if os.path.exists(bp): st.image(bp, caption="背")

    if st.session_state['inventory']:
        st.markdown("---")
        with st.expander("資料庫清單", expanded=True):
            df = pd.DataFrame([{
                "名稱": i['name'], "數值": f"{i.get('attack')}/{i.get('sp_attack')}", "屬性": f"{i['type']}/{i.get('type2','無')}",
                "招式": f"{i['moves'][0]['name']}/{i['moves'][1]['name']}"
            } for i in st.session_state['inventory']])
            df.index += 1
            ev = st.dataframe(df, use_container_width=True, on_select="rerun", selection_mode="single-row")
            if len(ev.selection.rows): show_card_image_modal(st.session_state['inventory'][ev.selection.rows[0]]['name'])

# --- Page: Battle Analysis ---
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

def get_effectiveness(atk, deff):
    if deff == "無" or atk == "無": return 1.0
    return TYPE_CHART.get(atk, {}).get(deff, 1.0)

def page_battle():
    st.header("⚔️ 對戰分析 (3 vs 3)")
    st.info("上傳螢幕截圖，系統將比對您建立的圖示範本 (使用0.5倍縮放加速)。")
    
    c_img, c_cfg = st.columns([1, 2])
    with c_img:
        bf = st.file_uploader("對戰截圖", type=["jpg", "png"], key="battle_uploader")
        
        # --- 自動清空邏輯 ---
        current_file_name = bf.name if bf else ""
        if current_file_name != st.session_state.get('last_battle_img', ""):
            # 檔名改變，清空結果
            for i in range(3):
                st.session_state['battle_config'][i]['detected_weakness'] = []
            st.session_state['last_battle_img'] = current_file_name
        # ------------------

        if bf:
            st.image(bf, width=250)
            if st.button("📸 掃描有利屬性", type="primary"):
                detected = detect_attribute_icons(bf) 
                for i in range(3):
                    st.session_state['battle_config'][i]['detected_weakness'] = detected[i]
                
                if not any(detected):
                    st.warning("⚠️ 未偵測到圖示。請檢查是否已建立範本。")
                else:
                    st.success("掃描完成！")

    with c_cfg:
        cols = st.columns(3)
        cfg = st.session_state['battle_config']
        for i, col in enumerate(cols):
            with col:
                st.markdown(f"#### 🥊 {cfg[i]['name']}")
                det_list = cfg[i]['detected_weakness']
                if det_list:
                    st.markdown(f"**有利屬性:**")
                    icon_html = ""
                    for dt in det_list:
                        icon_html += f" ` {dt} ` "
                    st.markdown(icon_html)
                else:
                    st.caption("未偵測到")

                cfg[i]['manual_t1'] = st.selectbox(f"屬性 1", POKEMON_TYPES, index=POKEMON_TYPES.index(cfg[i]['manual_t1']), key=f"op{i}t1")
                cfg[i]['manual_t2'] = st.selectbox(f"屬性 2", POKEMON_TYPES, index=POKEMON_TYPES.index(cfg[i]['manual_t2']), key=f"op{i}t2")

    st.markdown("---")
    if st.button("🚀 計算最佳隊伍", type="primary"):
        if not st.session_state['inventory']: st.error("無卡片資料"); return
        
        cands = []
        for card in st.session_state['inventory']:
            atk_v = card.get('attack', 100)
            sp_atk_v = card.get('sp_attack', 100)
            
            # Mode A: Special
            max_dmg_s = 0
            best_move_s = ""
            for idx, m in enumerate(card['moves']):
                if not m['name']: continue
                eff_total = 0
                for i in range(3):
                    eff = get_effectiveness(m['type'], cfg[i]['manual_t1']) * get_effectiveness(m['type'], cfg[i]['manual_t2'])
                    if m['type'] in cfg[i]['detected_weakness']:
                        eff = max(eff, 2.5)
                    eff_total += eff
                
                base = atk_v if m.get('category') == '攻擊' else sp_atk_v
                mult = 1.2 if idx == 1 else 1.0
                dmg = base * mult * eff_total
                if dmg > max_dmg_s:
                    max_dmg_s = dmg
                    best_move_s = f"{m['name']}({m['type']})"
            
            score_s = max_dmg_s
            tag = card['tag']
            if tag in ["極巨化", "Z招式"]: score_s *= 1.3
            elif tag != "無": score_s *= 1.15
            
            cands.append({"name": card['name'], "mode": "special", "tag": tag, "move": best_move_s, "score": score_s, "dmg": max_dmg_s})

            # Mode B: Normal
            if tag != "無":
                m = card['moves'][0] # Force 1st move
                if m['name']:
                    eff_total = 0
                    for i in range(3):
                        eff = get_effectiveness(m['type'], cfg[i]['manual_t1']) * get_effectiveness(m['type'], cfg[i]['manual_t2'])
                        if m['type'] in cfg[i]['detected_weakness']: eff = max(eff, 2.5)
                        eff_total += eff
                    
                    base = atk_v if m.get('category') == '攻擊' else sp_atk_v
                    dmg = base * 1.0 * eff_total
                    cands.append({"name": card['name'], "mode": "normal", "tag": "無", "move": f"{m['name']}({m['type']})", "score": dmg, "dmg": dmg})

        cands.sort(key=lambda x: x['score'], reverse=True)
        
        team, used_names, used_tags = [], set(), set()
        for c in cands:
            if len(team) >= 3: break
            if c['name'] in used_names: continue
            if c['tag'] != "無" and c['tag'] in used_tags: continue
            
            team.append(c)
            used_names.add(c['name'])
            if c['tag'] != "無": used_tags.add(c['tag'])
            
        st.subheader("🏆 推薦出戰陣容")
        cols = st.columns(3)
        for i, p in enumerate(team):
            with cols[i]:
                t_txt = p['tag']
                if p['mode'] == 'normal' and t_txt == '無': t_txt = "一般招式 (保留特殊)"
                st.success(f"**第 {i+1} 棒**\n\n### {p['name']}\n* **模式**: {t_txt}\n* **建議**: {p['move']}\n* **預估火力**: {int(p['dmg'])}")

# --- Main ---
page = st.sidebar.radio("模式", ["卡片資料庫管理", "對戰分析", "🛠️ 建立圖示範本"])
if page == "卡片資料庫管理": page_manage_cards()
elif page == "🛠️ 建立圖示範本": page_template_creator()
else: page_battle()