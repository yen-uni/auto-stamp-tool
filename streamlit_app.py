import streamlit as st
import fitz  # PyMuPDF
from PIL import Image
import numpy as np
import io

# 設定網頁標題與圖示
st.set_page_config(page_title="自動蓋章小工具", page_icon="📄", layout="wide")

# --- 雲端變數密碼防護 (Streamlit Cloud 專用) ---
def check_password():
    """驗證密碼是否正確"""
    if "password_correct" not in st.session_state:
        st.session_state["password_correct"] = False

    if not st.session_state["password_correct"]:
        st.text_input("🔒 請輸入內部使用密碼", type="password", key="pwd")
        
        try:
            # 讀取 Streamlit Cloud 後台設定的 Secrets
            secret_password = st.secrets["MY_PWD"]
        except KeyError:
            st.error("⚠️ 系統尚未設定密碼 (Secrets)，請聯繫管理員。")
            return False

        # 檢查輸入的密碼是否與後台設定相符
        if st.session_state["pwd"] == secret_password:
            st.session_state["password_correct"] = True
            st.rerun() # 密碼正確，重新載入畫面
        elif st.session_state["pwd"]:
            st.error("❌ 密碼錯誤，請重新輸入")
        return False
    return True

if not check_password():
    st.stop() # 如果密碼沒過，就停止執行下面的程式碼

# --- 以下為原本的蓋章工具程式碼 ---
# 將公分轉換為 PyMuPDF 支援的「點 (Points)」(1 公分 ≈ 28.346 點)
CM_TO_PTS = 28.346

# --- 影像處理函式 (包含去背、透明度與翻轉) ---
def process_stamp(img_file, remove_bg, flip_h, flip_v, opacity):
    # 讀取圖片並轉為 RGBA
    img = Image.open(img_file).convert("RGBA")
    data = np.array(img)
    
    # 1. 自動去背處理
    if remove_bg:
        r, g, b, a = data.T
        white_areas = (r > 200) & (g > 200) & (b > 200)
        data[..., 3][white_areas.T] = 0
        
    # 2. 透明度調整 (將 Alpha 通道乘上比例)
    if opacity < 1.0:
        data[..., 3] = (data[..., 3] * opacity).astype(np.uint8)
        
    img = Image.fromarray(data)
    
    # 3. 鏡像翻轉處理
    if flip_h:
        img = img.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
    if flip_v:
        img = img.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
        
    return img

# --- 網頁主要畫面 ---
st.title("📄 專屬自動蓋章小工具")
st.markdown("只需上傳 PDF 與印章，**修改左側數值，下方的預覽畫面會「即時」自動更新！**")

# --- 左側設定選單 ---
st.sidebar.header("⚙️ 1. 印章位置與頁面設定")
# 新增單頁/全頁選項
apply_mode = st.sidebar.radio("蓋章範圍", ["單頁", "全頁 (所有頁面)"])
page_num = st.sidebar.number_input("目標 / 預覽頁數", min_value=1, value=1)

# 座標設定 (改為公分)
st.sidebar.markdown("---")
st.sidebar.markdown("**📍 印章座標位置 (公分)**")
st.sidebar.caption("提示：標準 A4 紙張約為 21 寬 × 29.7 高 (公分)")
x_pos_cm = st.sidebar.number_input("X座標 (從左邊界起算, 公分)", value=14.00, min_value=0.00, max_value=100.00, step=0.01, format="%.2f")
y_pos_cm = st.sidebar.number_input("Y座標 (從上邊界起算, 公分)", value=6.00, min_value=0.00, max_value=10
