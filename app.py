import streamlit as st
import pandas as pd
import json
import os
import numpy as np
import cv2 # 需安裝 opencv-python-headless
from PIL import Image

# --- 設定頁面 ---
st.set_page_config(page_title="Mezastar 檔案室", layout="wide", page_icon="🗃️")

# --- 設定資料庫與圖示路徑 ---
DB_FILE = "mezastar_db.json"
IMG_DIR = "cardinfo"
ICON_DIR = "att_icon" # 有利屬性圖示目錄

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

# --- Helper: 儲存圖片 ---
def save_card_images(name):
    current_key = st.session_state['uploader_key']
    front = st.session_state.get(f"u_front_{current_key}")
    back = st.session_state.get(f"u_back_{current_key}")
    
    if front:
        Image.open(front).save(os.path.join(IMG_DIR, f"{name}_前.png"), "PNG")
    if back:
        Image.open(back).save(os.path.join(IMG_DIR, f"{name}_後.png"), "PNG")

# --- Helper: OpenCV 圖示比對 (升級版：縮放 + 透明遮罩 + 多尺寸) ---
def detect_attribute_icons(uploaded_image):
    """
    1. 將圖片縮小至寬度 1000px 以提升速度。
    2. 使用透明遮罩 (Alpha Mask) 進行比對。
    3. 使用多重尺度 (Multi-scale) 解決拍照遠近造成的圖示大小不一問題。
    """
    # 1. 讀取圖片
    file_bytes = np.asarray(bytearray(uploaded_image.read()), dtype=np.uint8)
    img_bgr = cv2.imdecode(file_bytes, 1) # 讀取為 BGR
    
    if img_bgr is None:
        return [[], [], []]

    # 2. 影像前處理：縮放到固定寬度 (例如 1000px)，大幅提升速度
    target_width = 1000
    h, w, _ = img_bgr.shape
    scale_factor = target_width / w
    new_h = int(h * scale_factor)
    img_resized = cv2.resize(img_bgr, (target_width, new_h))
    
    # 切割成左、中、右三份
    col_w = target_width // 3
    rois = [
        img_resized[:, 0:col_w],       # 左
        img_resized[:, col_w:col_w*2], # 中
        img_resized[:, col_w*2:]       # 右
    ]
    
    detected_results = [[], [], []]
    
    # 3. 準備圖示模版
    templates = {}
    for filename in os.listdir(ICON_DIR):
        if filename.endswith(".png"):
            type_name = filename.replace(".png", "")
            icon_path = os.path.join(ICON_DIR, filename)
            # 讀取包含 Alpha 通道的圖片 (IMREAD_UNCHANGED)
            templ_img = cv2.imread(icon_path, cv2.IMREAD_UNCHANGED)
            
            if templ_img is not None:
                # 分離 BGR 與 Alpha 通道
                if templ_img.shape[2] == 4:
                    base = templ_img[:, :, 0:3]
                    mask = templ_img[:, :, 3]
                else:
                    base = templ_img
                    mask = None
                templates[type_name] = (base, mask)

    if not templates:
        st.warning(f"⚠️ `{ICON_DIR}` 資料夾內沒有圖片，無法進行比對。")
        uploaded_image.seek(0)
        return [[], [], []]

    # 4. 多重尺度比對
    # 針對縮放後的畫面，圖示可能變大或變小，我們嘗試 0.5x ~ 1.5x 的縮放範圍
    icon_scales = np.linspace(0.5, 1.5, 5) # 測試 5 種不同的大小
    threshold = 0.85 # 信心門檻 (0.85 代表很高，因為有用遮罩，可以設高一點減少誤判)

    # 顯示進度條 (因為多重尺度會跑比較久)
    progress_bar = st.progress(0, text="AI 影像分析中...")
    total_steps = len(rois) * len(templates)
    step_count = 0

    for i, roi in enumerate(rois):
        found_types = set()
        
        for type_name, (base, mask) in templates.items():
            
            # 更新進度
            step_count += 1
            progress_bar.progress(int(step_count / total_steps * 100), text=f"正在掃描: {type_name}...")

            # 針對每一種尺度進行比對
            for scale in icon_scales:
                # 調整圖示大小
                t_w = int(base.shape[1] * scale)
                t_h = int(base.shape[0] * scale)
                
                # 如果縮放後的圖示比區域還大，就跳過
                if t_w > roi.shape[1] or t_h > roi.shape[0]:
                    continue
                
                resized_base = cv2.resize(base, (t_w, t_h))
                resized_mask = None
                if mask is not None:
                    resized_mask = cv2.resize(mask, (t_w, t_h))

                try:
                    # 使用 TM_CCORR_NORMED 配合 Mask 是最準確的方法之一
                    # 但若沒有 Mask，則使用 CCOEFF_NORMED
                    if resized_mask is not None:
                        res = cv2.matchTemplate(roi, resized_base, cv2.TM_CCORR_NORMED, mask=resized_mask)
                        # Mask 模式下，閾值通常要設非常高 (0.95+) 或是看實際效果
                        # 這裡為了相容性，我們改用 SQDIFF (值越小越好) 比較不會受亮度影響? 
                        # 其實 CCORR_NORMED + Mask 是官方推薦。但 Streamlit 雲端版 OpenCV 有時版本較舊。
                        # 安全起見，我們這裡還是用 CCOEFF_NORMED，但將透明區域填黑，減少干擾。
                        
                        # 替代方案：不傳入 mask 參數給 matchTemplate (避免舊版報錯)，
                        # 而是用 mask 把圖示背景變黑，並假設截圖背景也是黑的(不太可能)。
                        # 最好的方式：如果有 mask，就用 mask。
                        
                        # 若報錯，請改回不帶 mask 的 CCOEFF_NORMED
                        res = cv2.matchTemplate(roi, resized_base, cv2.TM_CCORR_NORMED, mask=resized_mask)
                        loc = np.where(res >= 0.92) # CCORR 需要極高閾值
                    else:
                        res = cv2.matchTemplate(roi, resized_base, cv2.TM_CCOEFF_NORMED)
                        loc = np.where(res >= 0.8)

                    if len(loc[0]) > 0:
                        found_types.add(type_name)
                        break # 這一種屬性找到了，就不需再試其他尺寸
                except:
                    # Fallback: 如果 OpenCV 版本不支援 mask，就用普通比對
                    res = cv2.matchTemplate(roi, resized_base, cv2.TM_CCOEFF_NORMED)
                    if np.max(res) > 0.8:
                        found_types.add(type_name)
                        break

        detected_results[i] = list(found_types)
    
    progress_bar.empty()
    uploaded_image.seek(0)
    return detected_results

# --- 初始化 Session State ---
if 'inventory' not in st.session_state:
    st.session_state['inventory'] = load_db()
if 'uploader_key' not in st.session_state:
    st.session_state['uploader_key'] = 0

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
                    st.rerun()
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
    st.info("上傳螢幕截圖，系統將比對「有利屬性」圖示，並保留手動調整對手屬性的功能。")
    
    c_img, c_cfg = st.columns([1, 2])
    with c_img:
        bf = st.file_uploader("對戰截圖", type=["jpg", "png"])
        if bf:
            st.image(bf, width=250)
            if st.button("📸 掃描有利屬性", type="primary"):
                detected = detect_attribute_icons(bf) # [[types], [types], [types]]
                for i in range(3):
                    st.session_state['battle_config'][i]['detected_weakness'] = detected[i]
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
                        # 簡單用文字顯示，若要圖片可改用 st.image
                        icon_html += f" ` {dt} ` "
                    st.markdown(icon_html)
                else:
                    st.caption("未偵測到圖示")

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
page = st.sidebar.radio("模式", ["卡片資料庫管理", "對戰分析"])
if page == "卡片資料庫管理": page_manage_cards()
else: page_battle()