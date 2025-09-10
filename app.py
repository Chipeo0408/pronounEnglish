import io
import time
import zipfile
from pathlib import Path

import streamlit as st
import pandas as pd

# Optional: only import if available
try:
    import eng_to_ipa as ipa
except Exception:
    ipa = None

try:
    from gtts import gTTS
except Exception:
    gTTS = None


st.set_page_config(page_title="IPA + TTS", page_icon="🔤", layout="centered")
st.title("🔤 English IPA + 🗣️ Text-to-Speech (Streamlit)")

with st.expander("ℹ️ Hướng dẫn nhanh", expanded=False):
    st.markdown(
        """
- Nhập câu tiếng Anh → bấm **Tạo IPA & Audio** → nghe trực tiếp & tải MP3.
- Tab **Batch CSV**: tải file CSV có cột `text` → nhận lại CSV + gói MP3 (ZIP).
- `gTTS` cần Internet; `eng_to_ipa` chuyển IPA cho tiếng Anh (xấp xỉ với câu dài).
        """
    )

tab_single, tab_batch = st.tabs(["🎧 Single", "📦 Batch CSV"])

# -----------------------------
# Helpers
# -----------------------------
def get_ipa(text: str) -> str:
    if ipa is None:
        return "(Thiếu thư viện eng_to_ipa — cài: pip install eng_to_ipa)"
    try:
        return ipa.convert(text)
    except Exception as e:
        return f"(Không tạo được IPA: {e})"

def tts_gtts_bytes(text: str, lang: str = "en", slow: bool = False) -> bytes:
    if gTTS is None:
        raise RuntimeError("Thiếu thư viện gTTS — cài: pip install gTTS")
    tts = gTTS(text, lang=lang, slow=slow)
    buf = io.BytesIO()
    tts.write_to_fp(buf)
    return buf.getvalue()

def sanitize_filename(s: str, maxlen=80) -> str:
    bad = '<>:"/\\|?*'
    for ch in bad:
        s = s.replace(ch, "_")
    s = "_".join(s.split())
    return s[:maxlen].strip("_") or "audio"

# -----------------------------
# Single mode
# -----------------------------
with tab_single:
    # Đặt giá trị mặc định trước
    if "count" not in st.session_state:
        st.session_state.count = 0
    sourece =  st.text_area("Nguồn:", height=210, placeholder="Overthinking can hurt you.")
    lstData = []
    if sourece:
        lstData = sourece.strip(".").split(".") if sourece.strip(".").find(".") == -1 else [sourece]
        lstData = [x.strip() for x in lstData if x.strip()]
        
        cola,colb = st.columns(2)
        with cola:
            if st.button("← Câu trước",use_container_width=True,type="primary"):
                if st.session_state.count>1:
                    st.session_state.count-=1
        with colb:
            if st.button("Câu sau →",use_container_width=True,type="primary"):
                if st.session_state.count<len(lstData):
                    st.session_state.count+=1

        text = st.text_area(f"Câu {st.session_state.count+1}", height=50, value=lstData[st.session_state.count] if lstData else "", placeholder="Nhập câu tiếng Anh ở đây...")
        with st.expander("Tùy chọn nâng cao", expanded=False):
            col1, col2, col3 = st.columns([1, 1, 1])
            with col1:
                lang = st.text_input("Ngôn ngữ gTTS", value="en", help="Ví dụ: en, en-uk, en-au")
            with col2:
                slow = st.checkbox("Đọc chậm (gTTS)")
            with col3:
                base_name = st.text_input("Tên file MP3", value="speech")

        if text:
            if not text.strip():
                st.warning("Vui lòng nhập nội dung.")
            else:
                with st.spinner("Đang xử lý..."):
                    ipa_text = get_ipa(text)
                    st.markdown("**IPA:**")
                    st.code(ipa_text or "(không có)",wrap_lines =True)

                    try:
                        audio_bytes = tts_gtts_bytes(text, lang=lang, slow=slow)
                        st.success("Đã tạo audio (gTTS).")
                        st.audio(audio_bytes, format="audio/mp3")
                        fname = f"{sanitize_filename(base_name)}.mp3"
                        st.download_button("⬇️ Tải MP3", data=audio_bytes, file_name=fname, mime="audio/mpeg")
                    except Exception as e:
                        st.error(f"Lỗi gTTS: {e}")
# -----------------------------
# Batch mode
# -----------------------------
with tab_batch:
    st.write("Tải lên **CSV** có cột `text` (mỗi dòng là một câu).")
    file = st.file_uploader("Chọn CSV", type=["csv"])

    colb1, colb2, colb3 = st.columns([1, 1, 1])
    with colb1:
        lang_b = st.text_input("Ngôn ngữ gTTS (batch)", value="en")
    with colb2:
        slow_b = st.checkbox("Đọc chậm (batch)")
    with colb3:
        zip_name = st.text_input("Tên gói ZIP", value="audios")

    if st.button("📦 Xử lý CSV → IPA + MP3", use_container_width=True):
        if file is None:
            st.warning("Vui lòng tải lên CSV.")
        else:
            try:
                df = pd.read_csv(file)
            except Exception as e:
                st.error(f"Không đọc được CSV: {e}")
                st.stop()

            if "text" not in df.columns:
                st.error("CSV phải có cột 'text'.")
                st.stop()

            # Chuẩn bị kết quả
            ipa_list = []
            zipped_bytes = io.BytesIO()
            with zipfile.ZipFile(zipped_bytes, "w", zipfile.ZIP_DEFLATED) as zf:
                for i, row in df.iterrows():
                    t = str(row["text"]).strip()
                    if not t:
                        ipa_list.append("")
                        continue

                    # IPA
                    ipa_text = get_ipa(t)
                    ipa_list.append(ipa_text)

                    # Audio
                    try:
                        audio_bytes = tts_gtts_bytes(t, lang=lang_b, slow=slow_b)
                        fname = f"{i:03d}_{sanitize_filename(t[:40])}.mp3"
                        zf.writestr(fname, audio_bytes)
                    except Exception as e:
                        # Ghi log lỗi thành file txt trong zip
                        zf.writestr(f"{i:03d}_ERROR.txt", f"Text: {t}\nError: {e}")

                # Thêm CSV kết quả (text + IPA)
                out_df = df.copy()
                out_df["ipa"] = ipa_list
                csv_bytes = out_df.to_csv(index=False).encode("utf-8")
                zf.writestr("results.csv", csv_bytes)

            st.success("Hoàn tất batch.")
            st.download_button(
                "⬇️ Tải ZIP (MP3 + results.csv)",
                data=zipped_bytes.getvalue(),
                file_name=f"{sanitize_filename(zip_name)}.zip",
                mime="application/zip",
            )
            st.dataframe(out_df)
