import sqlite3
import time
from datetime import datetime
import pandas as pd
import streamlit as st

# =========================
#  Logo (Option A)
# =========================
# Datei: assets/ukf_logo.png
try:
    st.logo("assets/ukf_logo.png")
except Exception:
    pass  # Logo ist optional; App läuft auch ohne

st.title("UKF-TumorRADS – Datenerfassung & Reviewer-konforme Zeitmessung")

# =========================
#  DB Setup
# =========================
conn = sqlite3.connect("ukf_tumorrads.db", check_same_thread=False)
c = conn.cursor()
c.execute("""
CREATE TABLE IF NOT EXISTS responses (
    id INTEGER PRIMARY KEY,
    rater TEXT NOT NULL,
    role TEXT NOT NULL,
    case_id TEXT NOT NULL,
    start_time REAL,
    duration_active REAL,
    duration_paused REAL,
    inactivity_flag INTEGER DEFAULT 0,
    -- NRAD Felder
    age INTEGER, gender TEXT, histology TEXT,
    scanner TEXT,
    seq_t2 INTEGER, seq_flair INTEGER, seq_t1_native INTEGER,
    seq_dwi INTEGER, seq_swi INTEGER, seq_mprage INTEGER, seq_dsc INTEGER,
    img_quality TEXT,
    dia_a INTEGER, dia_b INTEGER, laterality TEXT, contralat INTEGER,
    multifocal INTEGER, n_foci INTEGER, cortical TEXT, subcortical TEXT,
    dwi_adc TEXT, rcbv INTEGER,
    flair_a INTEGER, flair_b INTEGER, contrast_a INTEGER, contrast_b INTEGER,
    rano_category TEXT,
    summary TEXT, recommendation TEXT,
    completeness_ok INTEGER DEFAULT 0,
    missing_fields TEXT,
    -- NCH Ratings
    clarity INTEGER, organization INTEGER, completeness INTEGER,
    actionability INTEGER, language INTEGER, extractive INTEGER,
    global_1to10 INTEGER,
    comments TEXT,
    created_at TEXT
)
""")
conn.commit()
try:
    c.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_unique_case ON responses(rater, role, case_id);")
    conn.commit()
except sqlite3.OperationalError:
    pass

# =========================
#  Login / Kopf
# =========================
colA, colB, colC = st.columns([2,2,2])
with colA:
    rater = st.text_input("Rater Name", key="rater")
with colB:
    role = st.selectbox("Rolle", [
        "Neuroradiologist FOA (Fachoberarzt)",
        "Neurosurgeon FOA/OA (Fach- oder Oberarzt)"
    ], key="role")
with colC:
    case_id = st.text_input("Case ID", key="case_id")

# =========================
#  Timer State
# =========================
if "start_time" not in st.session_state:
    st.session_state.start_time = None
if "last_event_ts" not in st.session_state:
    st.session_state.last_event_ts = time.time()
if "paused_seconds" not in st.session_state:
    st.session_state.paused_seconds = 0.0
if "pause_active" not in st.session_state:
    st.session_state.pause_active = False
if "inactivity_flag" not in st.session_state:
    st.session_state.inactivity_flag = 0

def touch():
    # Heartbeat/Interaktion: aktualisiert Zeitstempel für Inaktivitätslogik
    st.session_state.last_event_ts = time.time()

# ===== Kopfzeile: Start/Timer/Anzeige
col1, col2, col3, col4 = st.columns([1.2,1,1,1.2])
with col1:
    if st.session_state.start_time is None:
        if st.button("Start Case", type="primary"):
            st.session_state.start_time = time.time()
            touch()
    else:
        now = time.time()
        since_last = now - st.session_state.last_event_ts
        # Auto-Pause bei Inaktivität > 60 s
        if since_last > 60 and not st.session_state.pause_active:
            st.session_state.pause_active = True
            st.session_state.inactivity_flag = 1
        elapsed_total = int(now - st.session_state.start_time)
        elapsed_active = max(0, elapsed_total - int(st.session_state.paused_seconds))
        with col2:
            st.metric("Gesamt (mm:ss)", f"{elapsed_total//60:02d}:{elapsed_total%60:02d}")
        with col3:
            st.metric("Aktiv (mm:ss)", f"{elapsed_active//60:02d}:{elapsed_active%60:02d}")
        with col4:
            st.metric("Pause (mm:ss)", f"{int(st.session_state.paused_seconds)//60:02d}:{int(st.session_state.paused_seconds)%60:02d}")

colp1, colp2, colp3 = st.columns([1,1,2])
with colp1:
    if st.session_state.start_time is not None and not st.session_state.pause_active:
        if st.button("⏸ Pause"):
            st.session_state.pause_active = True
            touch()
with colp2:
    if st.session_state.start_time is not None and st.session_state.pause_active:
        if st.button("▶ Resume"):
            st.session_state.paused_seconds += max(0, time.time() - st.session_state.last_event_ts)
            st.session_state.pause_active = False
            touch()

# Heartbeat außerhalb von Forms (vermeidet Form-Callback-Fehler)
st.text_input("🫀 Interaktions-Heartbeat (automatisch)", value=str(datetime.utcnow()),
              key="hb", on_change=touch)

# =========================
#  Formulare
# =========================
if st.session_state.start_time:

    # ---------- NRAD: komplettes UKF-TumorRADS (RANO 2.0) ----------
    if role.startswith("Neuroradiologist"):
        st.subheader("NRAD – UKF-TumorRADS Formular (RANO 2.0)")

        with st.form("ukf_form_nrad", clear_on_submit=False):
            st.markdown("**1. Patientendaten & Indikation**")
            age = st.number_input("Alter (Jahre)", min_value=18, max_value=120)
            gender = st.selectbox("Geschlecht", ["männlich","weiblich","divers"])
            histology = st.text_input("Histologie & WHO-Grad")

            st.markdown("**2. Bildgebungsprotokoll**")
            scanner = st.selectbox("Scanner", ["Siemens Prisma 3 T","Siemens Avanto 1.5 T"])
            seq_t2 = st.checkbox("T2-gewichtet (axial)")
            seq_flair = st.checkbox("3D-FLAIR")
            seq_t1_native = st.checkbox("T1 nativ")
            seq_dwi = st.checkbox("DWI (inkl. ADC)")
            seq_swi = st.checkbox("SWI")
            seq_mprage = st.checkbox("3D T1 MPRAGE post Gd")
            seq_dsc = st.checkbox("DSC-Perfusion")
            img_quality = st.selectbox("Bildqualität", ["gut","ok","schlecht"])

            st.markdown("**3. Tumor-Charakterisierung**")
            dia_a = st.number_input("Durchmesser A (mm)", min_value=0, max_value=500)
            dia_b = st.number_input("Durchmesser B (mm)", min_value=0, max_value=500)
            laterality = st.selectbox("Laterality", ["links","rechts","zentriert"])
            contralat = st.checkbox("Kontralaterale Infiltration")
            multifocal = st.checkbox("Multifokalität")
            n_foci = st.number_input("Anzahl der Foci", min_value=0, max_value=20)
            cortical = st.text_input("Kortikale Areale")
            subcortical = st.text_input("Subkortikale Areale")

            st.markdown("**4. Diffusion & Perfusion**")
            dwi_adc = st.selectbox("DWI/ADC", ["Restriktion","kein Restriktion"])
            rcbv = st.slider("DSC rCBV (1–5)", 1, 5, 1)

            st.markdown("**5. RANO 2.0 Assessment (A×B in mm², Δ% = (Pₙ−P₀)/P₀ ×100)**")
            flair_a = st.number_input("FLAIR A (mm²)", min_value=0)
            flair_b = st.number_input("FLAIR B (mm²)", min_value=0)
            contrast_a = st.number_input("Kontrast A (mm²)", min_value=0)
            contrast_b = st.number_input("Kontrast B (mm²)", min_value=0)
            rano_category = st.selectbox("RANO 2.0 Kategorie", ["CR","PR","MR","SD","PD"])

            st.markdown("**6. Fazit & Empfehlung**")
            summary = st.text_area("Kurzzusammenfassung")
            recommendation = st.selectbox("Empfehlung",
                                          ["Kontrolle in __ Wochen","OP","Biopsie","Therapieadaptation"])

            # Vollständigkeits-Check
            missing = []
            for label, val in [
                ("Alter", age), ("Geschlecht", gender), ("Histologie", histology),
                ("A (mm)", dia_a), ("B (mm)", dia_b), ("RANO", rano_category)
            ]:
                if label in ["A (mm)", "B (mm)"]:
                    if val == 0:
                        missing.append(label)
                else:
                    if isinstance(val, str) and not val.strip():
                        missing.append(label)
            completeness_ok = 0 if missing else 1

            submitted = st.form_submit_button("Submit & Stop Timer", type="primary")
            if submitted:
                total = time.time() - st.session_state.start_time
                if st.session_state.pause_active:
                    st.session_state.paused_seconds += max(0, time.time() - st.session_state.last_event_ts)
                duration_active = max(0.0, total - st.session_state.paused_seconds)

                try:
                    c.execute("""
                        INSERT INTO responses (
                            rater, role, case_id, start_time, duration_active, duration_paused, inactivity_flag,
                            age, gender, histology, scanner, seq_t2, seq_flair, seq_t1_native, seq_dwi, seq_swi, seq_mprage, seq_dsc,
                            img_quality, dia_a, dia_b, laterality, contralat, multifocal, n_foci, cortical, subcortical,
                            dwi_adc, rcbv, flair_a, flair_b, contrast_a, contrast_b, rano_category,
                            summary, recommendation, completeness_ok, missing_fields, comments, created_at
                        ) VALUES (?,?,?,?,?, ?, ?, ?,?,?, ?,?,?,?,?,?, ?, ?,?,?,?,?,?,?, ?, ?,?,?, ?, ?,?,?, ?, ?,?,?,?)
                    """, (
                        rater, role, case_id, st.session_state.start_time,
                        round(duration_active,2), round(st.session_state.paused_seconds,2), st.session_state.inactivity_flag,
                        age, gender, histology, scanner,
                        int(seq_t2), int(seq_flair), int(seq_t1_native), int(seq_dwi), int(seq_swi), int(seq_mprage), int(seq_dsc),
                        img_quality, dia_a, dia_b, laterality, int(contralat), int(multifocal), n_foci, cortical, subcortical,
                        dwi_adc, rcbv, flair_a, flair_b, contrast_a, contrast_b, rano_category,
                        summary, recommendation, int(completeness_ok), ", ".join(missing), "",
                        datetime.utcnow().isoformat()
                    ))
                    conn.commit()
                    st.success("Gespeichert ✅")
                    # Timer zurücksetzen
                    st.session_state.start_time = None
                    st.session_state.paused_seconds = 0.0
                    st.session_state.pause_active = False
                    st.session_state.inactivity_flag = 0
                except sqlite3.IntegrityError:
                    st.error("Duplikat: Dieser Rater und diese Rolle haben Case-ID bereits erfasst (UNIQUE-Schutz).")

    # ---------- NCH: Konsumenten-Ratings ----------
    else:
        st.subheader("NCH – Konsumenten-Bewertung (Likert & Global)")

        with st.form("ukf_form_nch", clear_on_submit=False):
            clarity = st.slider("Klarheit der Diagnose (1–5)", 1, 5, 3)
            organization = st.slider("Übersichtlichkeit/Gliederung (1–5)", 1, 5, 3)
            completeness = st.slider("Vollständigkeit (1–5)", 1, 5, 3)
            actionability = st.slider("Actionability/Handlungsfähigkeit (1–5)", 1, 5, 3)
            language = st.slider("Sprachverständlichkeit (1–5)", 1, 5, 3)
            extractive = st.slider("Extraktive Nutzbarkeit (1–5)", 1, 5, 3)
            global_1to10 = st.slider("Global (1–10)", 1, 10, 7)
            comments = st.text_area("Kommentare (optional)")

            submitted = st.form_submit_button("Submit & Stop Timer", type="primary")
            if submitted:
                total = time.time() - st.session_state.start_time
                if st.session_state.pause_active:
                    st.session_state.paused_seconds += max(0, time.time() - st.session_state.last_event_ts)
                duration_active = max(0.0, total - st.session_state.paused_seconds)

                try:
                    c.execute("""
                        INSERT INTO responses (
                            rater, role, case_id, start_time, duration_active, duration_paused, inactivity_flag,
                            clarity, organization, completeness, actionability, language, extractive, global_1to10,
                            comments, created_at
                        ) VALUES (?,?,?,?,?, ?, ?, ?,?,?,?,?,?, ?,?)
                    """, (
                        rater, role, case_id, st.session_state.start_time,
                        round(duration_active,2), round(st.session_state.paused_seconds,2), st.session_state.inactivity_flag,
                        clarity, organization, completeness, actionability, language, extractive, global_1to10,
                        comments, datetime.utcnow().isoformat()
                    ))
                    conn.commit()
                    st.success("Gespeichert ✅")
                    st.session_state.start_time = None
                    st.session_state.paused_seconds = 0.0
                    st.session_state.pause_active = False
                    st.session_state.inactivity_flag = 0
                except sqlite3.IntegrityError:
                    st.error("Duplikat: Dieser Rater und diese Rolle haben Case-ID bereits erfasst (UNIQUE-Schutz).")

# =========================
#  Export
# =========================
st.divider()
if st.button("📥 Download CSV aller Antworten"):
    df = pd.read_sql_query("SELECT * FROM responses", conn)
    csv = df.to_csv(index=False).encode("utf-8")
    st.download_button("Download CSV", data=csv,
                       file_name="ukf_tumorrads_responses.csv", mime="text/csv")
