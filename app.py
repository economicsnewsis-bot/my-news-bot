import streamlit as st
import os
import sys

# --- הגדרות העמוד (חייב להיות ראשון) ---
st.set_page_config(
    page_title="News Bot",
    layout="centered",
    page_icon="🤖",
    initial_sidebar_state="collapsed"
)

# --- כותרת ועיצוב ---
st.title("🤖 בוט החדשות האוטומטי")
st.caption("יוצר רילס חדשותי עם כתוביות AI, מוכן להורדה או לפרסום.")

# --- ייבוא הפונקציות מהקובץ הראשי ---
try:
    from main import create_visual_content, create_video, upload_to_instagram, generate_reel_description, CONFIG
except ImportError:
    st.error("❌ שגיאה קריטית: לא ניתן לטעון את main.py. וודא שהקובץ קיים ב-GitHub.")
    st.stop()

# ==========================================
#              ממשק המשתמש
# ==========================================

st.divider()

# תיבת בחירה: האם להעלות אוטומטית לאינסטגרם?
# (ברירת המחדל נלקחת מההגדרות ב-main.py)
upload_enabled = st.checkbox(
    "📸 פרסום אוטומטי לאינסטגרם (Upload to Instagram)",
    value=CONFIG.get("UPLOAD_TO_INSTAGRAM", False)
)

st.divider()

# --- הכפתור הראשי ---
if st.button("🔥 צור סרטון חדש 🔥", type="primary", use_container_width=True):
    
    # אזור סטטוס שנפתח ונסגר אוטומטית
    status_box = st.status("⏳ מתחיל בתהליך...", expanded=True)
    
    try:
        # 1. חיפוש חדשות ותמונות
        status_box.write("🔎 סורק את הרשת אחר חדשות חמות...")
        img_path, vid_path, data = create_visual_content()
        
        if not img_path or not data:
            status_box.update(label="❌ נכשל: לא נמצאו חדשות מתאימות", state="error")
            st.error("לא הצלחתי למצוא חדשות או תמונה מתאימה כרגע.")
            
        else:
            status_box.write(f"✅ נמצאה כתבה: {data['title']}")
            
            # 2. יצירת וידאו (MoviePy)
            status_box.write("🎥 עורך את הוידאו ומוסיף מוזיקה...")
            success = create_video(img_path, vid_path)
            
            if success:
                # 3. יצירת תיאור (Gemini AI)
                status_box.write("🤖 ג'מיני כותב תיאור לפוסט...")
                ai_text = generate_reel_description(data['title'], data['description'])
                
                # יצירת התיאור הסופי (הטקסט של ה-AI + האשטאגים)
                # אם אתה רוצה רק מה שה-AI כתב, תשאיר רק את ai_text
                final_caption = ai_text 
                
                status_box.update(label="✨ הסרטון מוכן!", state="complete", expanded=False)
                
                # --- הצגת התוצאה ---
                st.balloons()
                
                st.subheader("📺 התוצאה הסופית")
                st.video(vid_path)
                
                # --- כפתור הורדה לטלפון (חשוב מאוד בענן!) ---
                with open(vid_path, "rb") as file:
                    st.download_button(
                        label="⬇️ שמור את הסרטון לגלריה (Download)",
                        data=file,
                        file_name="news_reel.mp4",
                        mime="video/mp4",
                        use_container_width=True
                    )
                
                st.divider()
                
                # --- הצגת התיאור להעתקה ---
                st.subheader("📝 תיאור לפוסט (Caption)")
                st.info("העתק את הטקסט הזה לטיקטוק/אינסטגרם:")
                st.text_area("תוכן:", value=final_caption, height=150)
                
                # --- שלב ההעלאה לאינסטגרם (רק אם סומן) ---
                if upload_enabled:
                    with st.spinner("🚀 מתחבר לאינסטגרם ומעלה..."):
                        upload_to_instagram(vid_path, final_caption)
                    st.success("✅ הסרטון פורסם באינסטגרם בהצלחה!")
                else:
                    st.warning("⚠️ מצב 'העלאה אוטומטית' כבוי. הסרטון זמין להורדה בלבד.")

            else:
                status_box.update(label="❌ שגיאה בעריכת הוידאו", state="error")
                st.error("הייתה בעיה טכנית ביצירת קובץ ה-MP4.")

    except Exception as e:
        status_box.update(label="❌ שגיאה קריטית", state="error")
        st.error(f"התרחשה שגיאה לא צפויה: {e}")