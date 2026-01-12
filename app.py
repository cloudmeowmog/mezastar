# --- Helper: OpenCV 圖示比對 (終極增強版) ---
def detect_attribute_icons(uploaded_image):
    """
    1. 轉灰階 (抗色偏)
    2. 限制搜尋區域 (只看下半部)
    3. 多重尺度 (嘗試 20 種大小)
    """
    # 1. 讀取圖片
    file_bytes = np.asarray(bytearray(uploaded_image.read()), dtype=np.uint8)
    img_bgr = cv2.imdecode(file_bytes, 1)
    
    if img_bgr is None:
        return [[], [], []]

    # 2. 影像前處理：縮放與灰階
    target_width = 1000
    h, w, _ = img_bgr.shape
    scale_factor = target_width / w
    new_h = int(h * scale_factor)
    img_resized = cv2.resize(img_bgr, (target_width, new_h))
    
    # 轉灰階 (比對形狀比比對顏色更準)
    img_gray = cv2.cvtColor(img_resized, cv2.COLOR_BGR2GRAY)
    
    # *** 關鍵優化：只保留下半部 (有利屬性通常在卡片下方) ***
    # 假設畫面是直的，我們只切取下方 40% 的區域來找圖示
    crop_start_y = int(new_h * 0.6) 
    img_crop = img_gray[crop_start_y:, :]
    
    # 為了顯示結果，我們需要對應的座標偏移
    
    # 切割成左、中、右三份 (針對切割後的 img_crop)
    crop_h, crop_w = img_crop.shape
    col_w = crop_w // 3
    
    rois = [
        img_crop[:, 0:col_w],       # 左
        img_crop[:, col_w:col_w*2], # 中
        img_crop[:, col_w*2:]       # 右
    ]
    
    detected_results = [[], [], []]
    
    # 3. 準備圖示模版 (轉灰階)
    templates = {}
    for filename in os.listdir(ICON_DIR):
        if filename.endswith(".png"):
            type_name = filename.replace(".png", "")
            icon_path = os.path.join(ICON_DIR, filename)
            
            # 讀取並轉灰階
            templ_bgr = cv2.imread(icon_path)
            if templ_bgr is not None:
                templ_gray = cv2.cvtColor(templ_bgr, cv2.COLOR_BGR2GRAY)
                # 簡單邊緣強化 (可選)
                templates[type_name] = templ_gray

    if not templates:
        return [[], [], []]

    # 4. 多重尺度比對 (更細膩)
    # 嘗試從 0.3倍 到 2.0倍，共測試 20 種尺寸
    icon_scales = np.linspace(0.3, 2.0, 20) 
    threshold = 0.65 # *** 降低門檻：照片翻拍通常無法達到 0.8 以上 ***

    progress_bar = st.progress(0, text="AI 影像深度分析中...")
    total_steps = len(templates)
    step_count = 0

    # 為了避免同一個屬性被重複偵測 (例如偵測到兩個火)，我們使用集合
    final_detections = [set(), set(), set()]

    for type_name, templ in templates.items():
        step_count += 1
        progress_bar.progress(int(step_count / total_steps * 100), text=f"掃描屬性: {type_name}...")
        
        # 針對該屬性圖示，嘗試所有尺寸
        for scale in icon_scales:
            # 調整圖示大小
            t_w = int(templ.shape[1] * scale)
            t_h = int(templ.shape[0] * scale)
            
            # 安全檢查
            if t_w == 0 or t_h == 0: continue
            
            # 縮放模版
            resized_templ = cv2.resize(templ, (t_w, t_h))
            
            # 在三個區域中尋找
            for i, roi in enumerate(rois):
                if t_w > roi.shape[1] or t_h > roi.shape[0]: continue
                
                # 樣板匹配 (使用相關係數法)
                res = cv2.matchTemplate(roi, resized_templ, cv2.TM_CCOEFF_NORMED)
                
                # 找出大於門檻的點
                if np.max(res) >= threshold:
                    final_detections[i].add(type_name)
                    # 這裡不 break，因為可能同時有不同大小的圖示? 
                    # 通常 break 可以加速，但為了準確度我們先跑完 scales
                    # 不過為了效能，如果某個 scale 分數極高 (>0.85)，可以直接 break
                    if np.max(res) > 0.85:
                        break 

    # 轉回 list
    for i in range(3):
        detected_results[i] = list(final_detections[i])
    
    progress_bar.empty()
    uploaded_image.seek(0)
    return detected_results