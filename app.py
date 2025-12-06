import streamlit as st
import os
import sys

# --- הגדרות העמוד ---
st.set_page_config(page_title="News Bot", layout="centered", page_icon="🤖")

# --- כותרת ---
st.title("🤖 בוט החדשות האוטומטי")
st.write("מערכת ליצירת רילס חדשותי עם כיתוב AI אוטומטי.")

# --- ייבוא הפונקציות (כולל התיקונים החדשים) ---
try:
    from main import create_visual_content, create_video, upload_to_instagram, generate_reel_description, CONFIG
except ImportError:
    st.error("❌ שגיאה: לא מוצא את הקובץ main.py או שההתקנות חסרות.")
    st.stop()

# ==========================================
#              ממשק המשתמש
# ==========================================

st.divider()

# תיבת בחירה להעלאה אוטומטית
upload_enabled = st.checkbox(
    "✅ הפעל העלאה אוטומטית לאינסטגרם (Upload to Instagram)",
    value=CONFIG.get("UPLOAD_TO_INSTAGRAM", False)
)

st.divider()

# --- הכפתור הראשי ---
if st.button("🔥 צור סרטון חדש 🔥", type="primary", use_container_width=True):
    
    # אזור סטטוס שנפתח ונסגר
    status_box = st.status("⏳ מתחיל בתהליך...", expanded=True)
    
    try:
        # 1. חיפוש חדשות ותמונות
        status_box.write("🔎 מחפש חדשות ומוריד תמונות...")
        img_path, vid_path, data = create_visual_content()
        
        if not img_path or not data:
            status_box.update(label="❌ נכשל: לא נמצאו חדשות", state="error")
            st.error("לא הצלחתי למצוא חדשות או תמונה מתאימה.")
            
        else:
            status_box.write(f"✅ נמצאה כתבה: {data['title']}")
            
            # 2. יצירת וידאו
            status_box.write("🎥 עורך את הוידאו...")
            success = create_video(img_path, vid_path)
            
            if success:
                # 3. יצירת תיאור (AI)
                status_box.write("🤖 ג'מיני כותב תיאור...")
                ai_text = generate_reel_description(data['title'], data['description'])
                final_caption = f"{ai_text}\n\n#חדשות {data['hashtags']}"
                
                status_box.update(label="✨ התהליך הסתיים!", state="complete", expanded=False)
                
                # ============================================
                # 👇👇👇 כאן קובעים את הסדר בתצוגה 👇👇👇
                # ============================================
                
                # א. קודם כל הוידאו
                st.subheader("📺 התוצאה הסופית")
                st.video(vid_path)
                
                # ב. קו מפריד
                st.divider()
                
                # ג. התיאור מופיע *מתחת* לוידאו
                st.subheader("📝 התיאור שנוצר (Caption)")
                st.info("התיאור הזה יישלח לאינסטגרם (או שתוכל להעתיק אותו מכאן):")
                
                # תיבת טקסט נוחה להעתקה (בצד ימין לשמאל)
                st.text_area("תוכן הפוסט:", value=final_caption, height=200)
                
                # ============================================

                # 4. העלאה לאינסטגרם (אם סומן ה-Checkbox)
                if upload_enabled:
                    with st.spinner("🚀 מעלה לאינסטגרם..."):
                        upload_to_instagram(vid_path, final_caption)
                    st.success("✅ הסרטון פורסם באינסטגרם בהצלחה!")
                    st.balloons()
                else:
                    st.warning("⚠️ מצב 'העלאה' כבוי. הסרטון נשמר במחשב בלבד.")

            else:
                status_box.update(label="❌ שגיאה בעריכת הוידאו", state="error")
                st.error("הייתה בעיה ביצירת קובץ ה-MP4.")

    except Exception as e:
        status_box.update(label="❌ שגיאה קריטית", state="error")
        st.error(f"התרחשה שגיאה: {e}")