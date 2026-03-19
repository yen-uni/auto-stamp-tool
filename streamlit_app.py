import streamlit as st
from PIL import Image
from streamlit_image_coordinates import streamlit_image_coordinates

# ==========================================
# 0. 頁面基本設定與 CSS 注入
# ==========================================
st.set_page_config(layout="wide", page_title="蓋章小工具")

# 強制將圖片互動區塊與 Canvas 的滑鼠游標改成十字線
st.markdown(
    """
    <style>
    [data-testid="stImage"] img, canvas, .stImage {
        cursor: crosshair !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# 初始化 Session State 來儲存點擊座標，避免拉動滑桿時印章消失
if "stamp_pos" not in st.session_state:
    st.session_state.stamp_pos = None

# ==========================================
# 1. 側邊欄 UI
# ==========================================
st.sidebar.title("⚙️ 1. 頁面設定")
stamp_width_cm = st.sidebar.number_input("印章寬度 (公分)", min_value=1.0, value=3.0, step=0.1)

st.sidebar.title("🛠️ 2. 影像微調")
opacity = st.sidebar.slider("印章不透明度", 0.0, 1.0, 1.0)
rotation = st.sidebar.slider("印章旋轉角度", -180, 180, 0)

# ==========================================
# 2. 頂部上傳區塊
# ==========================================
col_up1, col_up2 = st.columns(2)
with col_up1:
    doc_file = st.file_uploader("上傳文件檔案 (圖片格式)", type=['png', 'jpg', 'jpeg'])
with col_up2:
    stamp_file = st.file_uploader("上傳印章檔案", type=['png', 'jpg', 'jpeg'])

# ==========================================
# 3. 主程式邏輯
# ==========================================
if doc_file and stamp_file:
    # 讀取並統一轉為 RGBA 以支援透明度處理
    doc_img = Image.open(doc_file).convert("RGBA")
    stamp_img = Image.open(stamp_file).convert("RGBA")

    # 效能優化：如果文件原圖太大(超過1600px)，先進行縮放，避免點擊時發生嚴重延遲或失效
    max_width = 1600
    if doc_img.width > max_width:
        ratio = max_width / doc_img.width
        new_h = int(doc_img.height * ratio)
        doc_img = doc_img.resize((max_width, new_h), Image.Resampling.LANCZOS)

    # --- 印章前處理 (大小、旋轉、透明度) ---
    stamp_ratio = (stamp_width_cm * 30) / stamp_img.width  
    new_size = (int(stamp_img.width * stamp_ratio), int(stamp_img.height * stamp_ratio))
    
    if new_size[0] > 0 and new_size[1] > 0:
        stamp_img = stamp_img.resize(new_size, Image.Resampling.LANCZOS)
    
    # 處理旋轉 (expand=True 確保旋轉後圖片不被裁切)
    stamp_img = stamp_img.rotate(rotation, expand=True)
    
    # 處理透明度 (更穩定的 RGBA 通道合併寫法)
    if opacity < 1.0:
        r, g, b, a = stamp_img.split()
        a = a.point(lambda p: p * opacity)
        stamp_img = Image.merge("RGBA", (r, g, b, a))

    # --- 左右雙欄對比顯示 ---
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("📍 **步驟一：滑鼠點擊定位**")
        st.markdown("🚨 <span style='color:red'>**重要提示：不需要拖曳了！**</span>", unsafe_allow_html=True)
        st.markdown("請將滑鼠移到下方文件影像上（游標會變成十字線），然後直接「點擊」你想蓋章的位置（這會是印章的左上角）。請點點看！")
        
        # 獲取點擊座標
        clicked_value = streamlit_image_coordinates(doc_img, key="doc_click", use_column_width=True)
        
        # 如果有新的點擊，更新 session_state
        if clicked_value is not None:
            st.session_state.stamp_pos = (clicked_value["x"], clicked_value["y"])

    with col2:
        st.markdown("👁️ **步驟二：即時預覽**")
        # 補齊兩行空白，消除與左側步驟一的高低差
        st.markdown("<br><br>", unsafe_allow_html=True)
        
        preview_img = doc_img.copy()

        # 使用 session_state 中記錄的座標來蓋章
        if st.session_state.stamp_pos is not None:
            x, y = st.session_state.stamp_pos
            preview_img.paste(stamp_img, (x, y), stamp_img)

        # 顯示預覽圖
        st.image(preview_img, use_container_width=True)

else:
    st.info("請先在上方上傳「文件」與「印章」檔案，即可開始測試游標與合成效果。")
