import streamlit as st
import fitz  # PyMuPDF
from PIL import Image
import numpy as np
import io
from streamlit_cropper import st_cropper

st.set_page_config(page_title="環久國際機構-蓋章小工具V8.1 (UI優化版)", page_icon="📄", layout="wide")

# 將公分轉換為 PyMuPDF 支援的「點 (Points)」(1 公分 ≈ 28.346 點)
CM_TO_PTS = 28.346

def process_stamp(img_file, remove_bg, flip_h, flip_v, rotation_angle, opacity):
    # 讀取圖片並轉為 RGBA
    img = Image.open(img_file).convert("RGBA")
    data = np.array(img)
    
    # 1. 自動去背處理
    if remove_bg:
        r, g, b, a = data.T
        white_areas = (r > 200) & (g > 200) & (b > 200)
        data[..., 3][white_areas.T] = 0
        img = Image.fromarray(data)
    
    # 2. 自動裁切透明邊界
    bbox = img.getbbox()
    if bbox:
        img = img.crop(bbox)
        data = np.array(img)
        
    # 3. 透明度調整
    if opacity < 1.0:
        data[..., 3] = (data[..., 3] * opacity).astype(np.uint8)
        img = Image.fromarray(data)
        
    # 4. 鏡像與翻轉
    if flip_h:
        img = img.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
    if flip_v:
        img = img.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
        
    # 5. 旋轉處理
    if rotation_angle != 0:
        img = img.rotate(rotation_angle, expand=True)
        bbox2 = img.getbbox()
        if bbox2:
            img = img.crop(bbox2)
            
    return img

st.title("📄 環久國際機構-蓋章小工具V8.1")

# ==========================================
# 側邊欄：全域印章設定 (步驟一與步驟二共用)
# ==========================================
st.sidebar.header("⚙️ 印章參數設定 (全域)")
st.sidebar.info("請在「步驟一」視覺對照時調整此處數值，確認大小無誤後再進行「步驟二」。")
stamp_w_cm = st.sidebar.number_input("📐 印章寬度 (公分)", value=3.00, min_value=0.10, max_value=20.00, step=0.10, format="%.2f")
stamp_opacity = st.sidebar.slider("💧 印章不透明度", 0.1, 1.0, 0.75, 0.05, help="對照時建議調低透明度，套印時可調回 1.0")
auto_bg_remove = st.sidebar.checkbox("✨ 自動濾除印章白底", value=True)
rotation_angle = st.sidebar.select_slider("🔄 印章旋轉角度", options=[0, 90, 180, 270, 360], value=0)

# ==========================================
# 主畫面：三步驟流程 (新增 Tab 3)
# ==========================================
tab1, tab2, tab3 = st.tabs(["📍 步驟一：視覺對照確認尺寸", "🖨️ 步驟二：套印新文件", "📑 步驟三：多印章套印"])

# ------------------------------------------
# 📍 步驟一：視覺對照確認尺寸
# ------------------------------------------
with tab1:
    st.markdown("### 1. 上傳檔案與印章")
    col_upload1, col_upload2 = st.columns(2)
    with col_upload1:
        ref_pdf_file = st.file_uploader("📁 上傳「已蓋章」參考 PDF (對照用)", type=["pdf"], key="ref_pdf")
    with col_upload2:
        stamp_file = st.file_uploader("💮 上傳印章圖檔", type=["png", "jpg", "jpeg"], key="stamp")

    if ref_pdf_file and stamp_file:
        st.markdown("---")
        st.markdown("### 2. 拖曳對照尺寸")
        st.info("💡 **操作方式**：將藍框拖曳並縮放至舊印章位置（拉邊緣小方塊可縮放），並調整左側的「印章寬度」，直到右方預覽圖的數位印章完美重合。")
        
        ref_doc = fitz.open(stream=ref_pdf_file.read(), filetype="pdf")
        ref_page = ref_doc[0]
        ref_pix = ref_page.get_pixmap(matrix=fitz.Matrix(1.0, 1.0))
        ref_bg_img = Image.frombytes("RGB", [ref_pix.width, ref_pix.height], ref_pix.samples)
        
        stamp_file.seek(0)
        final_stamp = process_stamp(stamp_file, auto_bg_remove, False, False, rotation_angle, stamp_opacity)
        
        col_ref1, col_ref2 = st.columns([1.2, 1])
        with col_ref1:
            ref_coords = st_cropper(ref_bg_img, aspect_ratio=None, box_color='#0000FF', return_type='box', key='ref_cropper')
        
        with col_ref2:
            st.markdown("**🔍 對照預覽區**")
            
            # 【優化】將提示訊息移至圖面上方
            st.success("✅ 尺寸確認 OK 後，請切換到上方「步驟二」頁籤。")
            
            stamp_w_pts = stamp_w_cm * CM_TO_PTS
            pillow_ratio = final_stamp.width / final_stamp.height
            stamp_h_pts = stamp_w_pts / pillow_ratio
            
            center_x = ref_coords['left'] + (ref_coords['width'] / 2)
            center_y = ref_coords['top'] + (ref_coords['height'] / 2)
            
            rect_x0 = center_x - (stamp_w_pts / 2)
            rect_y0 = center_y - (stamp_h_pts / 2)
            rect_x1 = center_x + (stamp_w_pts / 2)
            rect_y1 = center_y + (stamp_h_pts / 2)
            
            preview_doc = fitz.open(stream=ref_pdf_file.getvalue(), filetype="pdf")
            rect = fitz.Rect(rect_x0, rect_y0, rect_x1, rect_y1)
            
            stamp_bytes_io = io.BytesIO()
            final_stamp.save(stamp_bytes_io, format="PNG")
            preview_doc[0].insert_image(rect, stream=stamp_bytes_io.getvalue())
            
            zoom_matrix = fitz.Matrix(2.0, 2.0)
            preview_img_pix = preview_doc[0].get_pixmap(matrix=zoom_matrix)
            preview_img = Image.frombytes("RGB", [preview_img_pix.width, preview_img_pix.height], preview_img_pix.samples)
            
            # 【優化】利用欄位比例將圖面縮小為 80% (1:8:1) 並置中
            c1, c2, c3 = st.columns([1, 8, 1])
            with c2:
                st.image(preview_img, caption=f"對位預覽 (印章設定為 {stamp_w_cm} 公分)", use_container_width=True)

# ------------------------------------------
# 🖨️ 步驟二：套印新文件
# ------------------------------------------
with tab2:
    st.markdown("### 1. 上傳空白文件")
    target_pdf_file = st.file_uploader("📁 上傳欲套印之「空白」 PDF 檔案", type=["pdf"], key="target_pdf")
    
    if target_pdf_file and stamp_file:
        st.markdown("---")
        st.markdown("### 2. 中心點定位與蓋章")
        st.info("💡 **提示**：請移動紅框（可縮放大小輔助對位），將紅框的 **「正中心」** 對準目標位置。系統會以紅框中心點進行套印。")
        
        target_doc = fitz.open(stream=target_pdf_file.read(), filetype="pdf")
        
        c_mode, c_page = st.columns(2)
        with c_mode:
            apply_mode = st.radio("蓋章範圍", ["單頁", "全頁 (所有頁面)"], horizontal=True)
        with c_page:
            page_num = st.number_input("目標頁數", min_value=1, max_value=len(target_doc), value=1)
            page_index = page_num - 1
            
        target_page = target_doc[page_index]
        target_pix = target_page.get_pixmap(matrix=fitz.Matrix(1.0, 1.0))
        target_bg_img = Image.frombytes("RGB", [target_pix.width, target_pix.height], target_pix.samples)
        
        col_main1, col_main2 = st.columns([1.2, 1])
        
        with col_main1:
            box_coords = st_cropper(target_bg_img, aspect_ratio=None, box_color='#FF0000', return_type='box', key='target_cropper')
            
        with col_main2:
            st.markdown("**📄 最終成品預覽**")
            
            stamp_file.seek(0)
            final_stamp = process_stamp(stamp_file, auto_bg_remove, False, False, rotation_angle, stamp_opacity)
            stamp_bytes_io = io.BytesIO()
            final_stamp.save(stamp_bytes_io, format="PNG")
            
            center_x = box_coords['left'] + (box_coords['width'] / 2)
            center_y = box_coords['top'] + (box_coords['height'] / 2)
            
            stamp_w_pts = stamp_w_cm * CM_TO_PTS
            pillow_ratio = final_stamp.width / final_stamp.height
            stamp_h_pts = stamp_w_pts / pillow_ratio
            
            rect_x0 = center_x - (stamp_w_pts / 2)
            rect_y0 = center_y - (stamp_h_pts / 2)
            rect_x1 = center_x + (stamp_w_pts / 2)
            rect_y1 = center_y + (stamp_h_pts / 2)
            
            rect = fitz.Rect(rect_x0, rect_y0, rect_x1, rect_y1)
            
            if apply_mode == "全頁 (所有頁面)":
                for p in target_doc:
                    p.insert_image(rect, stream=stamp_bytes_io.getvalue())
            else:
                target_page.insert_image(rect, stream=stamp_bytes_io.getvalue())
                
            output_pdf = io.BytesIO()
            target_doc.save(output_pdf)
            
            # 【優化】將下載按鈕移至圖面上方
            st.download_button(
                label="📥 點我下載已蓋章 PDF",
                data=output_pdf.getvalue(),
                file_name=f"套印完成_{target_pdf_file.name}",
                mime="application/pdf",
                type="primary",
                use_container_width=True
            )
            
            zoom_matrix = fitz.Matrix(2.0, 2.0)
            final_pix = target_page.get_pixmap(matrix=zoom_matrix)
            final_img = Image.frombytes("RGB", [final_pix.width, final_pix.height], final_pix.samples)
            
            # 【優化】利用欄位比例將圖面縮小為 80% (1:8:1) 並置中
            c4, c5, c6 = st.columns([1, 8, 1])
            with c5:
                st.image(final_img, caption="最終成品預覽 (中心點對位)", use_container_width=True)

# ------------------------------------------
# 📑 步驟三：多印章套印 (新增)
# ------------------------------------------
with tab3:
    st.markdown("### 1. 上傳欲套印之「空白」 PDF 檔案")
    multi_pdf_file = st.file_uploader("📁 上傳 PDF (多章模式)", type=["pdf"], key="multi_pdf")

    if multi_pdf_file:
        st.markdown("---")
        col_cfg1, col_cfg2 = st.columns([1, 2])
        with col_cfg1:
            stamp_count = st.number_input("🔢 需要蓋幾個不同的章？", min_value=1, max_value=6, value=3)
            page_num_multi = st.number_input("📄 目標頁碼 (多章)", min_value=1, value=1)

        all_stamps_data = []

        # 讀取 PDF
        doc_multi = fitz.open(stream=multi_pdf_file.read(), filetype="pdf")
        page_index_multi = page_num_multi - 1
        
        if page_index_multi >= len(doc_multi):
            st.warning("頁碼超出範圍！")
        else:
            page_multi = doc_multi[page_index_multi]
            pix_multi = page_multi.get_pixmap(matrix=fitz.Matrix(1.0, 1.0))
            bg_multi = Image.frombytes("RGB", [pix_multi.width, pix_multi.height], pix_multi.samples)

            st.markdown("### 2. 依序設定各別印章與位置")
            st.info("請於下方展開對應印章的設定面板。這裡會套用左側全域的「去背」與「透明度」設定。")
            
            for i in range(stamp_count):
                with st.expander(f"📌 第 {i+1} 個印章設定", expanded=(i==0)):
                    c1, c2 = st.columns([1, 1.5])
                    with c1:
                        s_file = st.file_uploader(f"💮 上傳印章 {i+1}", type=["png", "jpg", "jpeg"], key=f"s_f_{i}")
                        s_w = st.number_input(f"📐 印章寬度 (cm)", value=3.00, step=0.10, key=f"s_w_{i}")
                        s_rot = st.selectbox(f"🔄 旋轉", [0, 90, 180, 270, 360], key=f"s_r_{i}")
                    with c2:
                        if s_file:
                            st.caption("拖曳紅框，將「中心點」對準欲蓋章位置")
                            coords = st_cropper(bg_multi, aspect_ratio=None, box_color='#FF0000', return_type='box', key=f"s_c_{i}")
                            all_stamps_data.append({
                                "file": s_file, "width": s_w, "rot": s_rot, "coords": coords
                            })
                        else:
                            st.warning("請先上傳此印章的圖檔")

            st.markdown("---")
            if len(all_stamps_data) == stamp_count:
                if st.button("🚀 開始一鍵合成所有印章", type="primary", use_container_width=True):
                    with st.spinner("正在合成中..."):
                        for data in all_stamps_data:
                            data["file"].seek(0)
                            # 處理每顆印章圖檔，套用全域的去背與透明度
                            processed = process_stamp(data["file"], auto_bg_remove, False, False, data["rot"], stamp_opacity)
                            img_byte_arr = io.BytesIO()
                            processed.save(img_byte_arr, format='PNG')

                            cx = data["coords"]['left'] + (data["coords"]['width'] / 2)
                            cy = data["coords"]['top'] + (data["coords"]['height'] / 2)
                            sw_pts = data["width"] * CM_TO_PTS
                            sh_pts = sw_pts / (processed.width / processed.height)

                            rect = fitz.Rect(cx - sw_pts/2, cy - sh_pts/2, cx + sw_pts/2, cy + sh_pts/2)
                            page_multi.insert_image(rect, stream=img_byte_arr.getvalue())

                        out_multi = io.BytesIO()
                        doc_multi.save(out_multi)

                        st.success("✅ 全部印章套印完成！")
                        st.download_button(
                            label="📥 下載多章合成文件",
                            data=out_multi.getvalue(),
                            file_name=f"多章套印_{multi_pdf_file.name}",
                            mime="application/pdf",
                            use_container_width=True
                        )
