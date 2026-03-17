import streamlit as st
import fitz  # PyMuPDF
from PIL import Image
import numpy as np
import io

# 設定網頁標題與圖示
st.set_page_config(page_title="自動蓋章小工具", page_icon="📄", layout="wide")

# --- 雲端變數密碼防護 ---
def check_password():
    """驗證密碼是否正確"""
    if "password_correct" not in st.session_state:
        st.session_state["password_correct"] = False

    if not st.session_state["password_correct"]:
        st.title("🔒 內部系統存取限制")
        pwd_input = st.text_input("請輸入內部使用密碼", type="password")
        
        # 讀取 Streamlit Cloud 後台設定的 Secrets
        # 如果沒設定，預設為 None
        try:
            correct_password = st.secrets["MY_PWD"]
        except:
            st.error("系統尚未設定密碼，請聯繫管理員。")
            st.stop()

        if pwd_input == correct_password:
            st.session_state["password_correct"] = True
            st.rerun()
        elif pwd_input:
            st.error("❌ 密碼錯誤")
        return False
    return True

if not check_password():
    st.stop()

# --- 原本的蓋章邏輯 (以下不變) ---
CM_TO_PTS = 28.346

def process_stamp(img_file, remove_bg, flip_h, flip_v, opacity):
    img = Image.open(img_file).convert("RGBA")
    data = np.array(img)
    if remove_bg:
        r, g, b, a = data.T
        white_areas = (r > 200) & (g > 200) & (b > 200)
        data[..., 3][white_areas.T] = 0
    if opacity < 1.0:
        data[..., 3] = (data[..., 3] * opacity).astype(np.uint8)
    img = Image.fromarray(data)
    if flip_h:
        img = img.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
    if flip_v:
        img = img.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
    return img

st.title("📄 專屬自動蓋章小工具")
# ... (其餘 UI 邏輯維持原樣) ...
