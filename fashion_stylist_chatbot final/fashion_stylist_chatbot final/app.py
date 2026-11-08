"""StyleMate AI — local conversational fashion stylist."""
import re
import time
import hashlib
import secrets
import streamlit as st
import streamlit.components.v1 as components
import extra_streamlit_components as st_logged
from database import (
    init_db, get_preferences, save_preferences,
    create_conversation, list_conversations, get_conversation, get_conversation_profile,
    save_conversation_profile, get_messages,
    add_message, update_conversation_title, delete_conversation, delete_all_conversations,
    add_recommendation, get_user_by_id, set_user_session_token, get_user_by_session_token
)
from auth import register_user, authenticate_user, reset_password
from src.chat_controller import ChatController
from src.conversation_manager import new_profile, rebuild_profile, remembered_preferences

st.set_page_config(page_title="StyleMate AI", page_icon="👗", layout="wide", initial_sidebar_state="expanded")

init_db()

# Cookie manager for persistent login across browser sessions
cookie_manager = st_logged.CookieManager()

# Initialize authentication & navigation state
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "user_id" not in st.session_state:
    st.session_state.user_id = None
if "auth_view" not in st.session_state:
    st.session_state.auth_view = "landing"  # "landing", "login", "signup", "forgot"

# Persistent login check via secure cookie and database token hash
if not st.session_state.authenticated:
    cookie_token = cookie_manager.get(cookie="stylemate_session_token")
    if cookie_token:
        token_hash = hashlib.sha256(cookie_token.encode()).hexdigest()
        user = get_user_by_session_token(token_hash)
        if user:
            st.session_state.authenticated = True
            st.session_state.user_id = int(user["id"])

# ---------------------------------------------------------------------------
# Theme state (persisted in the URL so it survives a browser refresh)
# ---------------------------------------------------------------------------
if "theme" not in st.session_state:
    url_theme = st.query_params.get("theme", "light")
    st.session_state.theme = url_theme if url_theme in ("light", "dark") else "light"


def on_theme_toggle():
    st.session_state.theme = "dark" if st.session_state.theme_toggle_menu else "light"
    st.query_params["theme"] = st.session_state.theme


THEMES = {
    "light": {
        "bg": "#F4EFF9", "panel": "#EBE3F5", "surface": "#FFFFFF",
        "ink": "#262626", "muted": "#6B6B6B", "border": "#D8CDEA",
        "accent": "#7656A8", "user_bubble": "#F0EBFA", "bot_bubble": "#FFFFFF",
        "hover": "#E6E2DA", "scheme": "light",
    },
    "dark": {
        "bg": "#121212", "panel": "#1E1E1E", "surface": "#262626",
        "ink": "#E8E8E8", "muted": "#A0A0A0", "border": "#2F2F2F",
        "accent": "#9D72E0", "user_bubble": "#2A2438", "bot_bubble": "#1E1E24",
        "hover": "#2E2E2E", "scheme": "dark",
    },
}
T = THEMES[st.session_state.theme]

st.markdown(f"""
<style>
:root {{
    --sm-bg: {T['bg']};
    --sm-panel: {T['panel']};
    --sm-surface: {T['surface']};
    --sm-purple: {T['accent']};
    --sm-ink: {T['ink']};
    --sm-muted: {T['muted']};
    --sm-border: {T['border']};
    --sm-hover: {T['hover']};
    --sm-user: {T['user_bubble']};
    --sm-bot: {T['bot_bubble']};
    color-scheme: {T['scheme']};
}}

/* ---------- App shell ---------- */
html, body, .stApp, [data-testid="stAppViewContainer"], [data-testid="stMain"], section.main {{
    background: var(--sm-bg) !important;
    color: var(--sm-ink) !important;
}}
.block-container, [data-testid="stMainBlockContainer"] {{
    max-width: 1040px;
    padding-top: 4.5rem !important;
    padding-bottom: 7.5rem !important;
}}

[data-testid="stHeader"], header[data-testid="stHeader"] {{
    background: var(--sm-bg) !important;
}}
[data-testid="stToolbar"], [data-testid="stToolbar"] *,
[data-testid="stHeader"] button, [data-testid="stHeader"] svg {{
    color: var(--sm-muted) !important;
}}
[data-testid="stDecoration"] {{ display: none; }}

/* Completely hide CookieManager / unwanted dropdown elements on landing page */
iframe[src*="extra_streamlit_components"], [data-testid="stIFrame"], [data-testid="stElementToolbar"] {{
    display: none !important;
    height: 0 !important;
    width: 0 !important;
    visibility: hidden !important;
    position: absolute !important;
    pointer-events: none !important;
}}

/* ---------- Password Visibility Eye Icon Fix for Dark/Light Mode ---------- */
[data-testid="stTextInput"] button[kind="secondary"],
[data-testid="stTextInput"] [data-testid="stBaseButton-secondary"],
[data-testid="stTextInput"] button svg {{
    color: var(--sm-ink) !important;
    fill: var(--sm-ink) !important;
    opacity: 0.85 !important;
}}
[data-testid="stTextInput"] button:hover svg {{
    color: var(--sm-purple) !important;
    fill: var(--sm-purple) !important;
    opacity: 1 !important;
}}

/* ---------- Sidebar ---------- */
[data-testid="stSidebar"], [data-testid="stSidebar"] > div:first-child {{
    background: var(--sm-panel) !important;
    border-right: 1px solid var(--sm-border);
}}
[data-testid="stSidebarHeader"] {{
    position: absolute !important;
    top: 0.4rem; right: 0.4rem;
    width: auto !important; height: auto !important; min-height: 0 !important;
    padding: 0 !important;
    background: transparent !important;
    z-index: 10;
}}
[data-testid="stSidebarUserContent"], [data-testid="stSidebarContent"] {{ padding-top: 0 !important; }}
[data-testid="stSidebarUserContent"] {{ padding-top: 0.6rem !important; }}
[data-testid="stSidebar"] .block-container {{ padding-top: 0.5rem !important; }}
[data-testid="stSidebar"] div[data-testid="stVerticalBlock"] {{ gap: 0.4rem; }}
[data-testid="stSidebar"] .sm-brand {{ margin-top: 0; padding-right: 2rem; }}

[data-testid="stSidebarContent"] {{
    height: 100% !important;
    overflow: hidden !important;
}}
[data-testid="stSidebarUserContent"] {{
    height: 100% !important;
    overflow: hidden !important;
    padding-bottom: 0.6rem !important;
    display: flex;
    flex-direction: column;
}}
[data-testid="stSidebarUserContent"] > div,
[data-testid="stSidebarUserContent"] > div > [data-testid="stVerticalBlock"],
[data-testid="stSidebarUserContent"] > [data-testid="stVerticalBlock"] {{
    height: 100%;
    min-height: 0;
    flex-wrap: nowrap;
}}

[data-testid="stSidebar"] .st-key-sm_header,
[data-testid="stSidebar"] .st-key-sm_footer,
[data-testid="stSidebar"] :has(> .st-key-sm_header):not(:has(> .st-key-sm_history)),
[data-testid="stSidebar"] :has(> .st-key-sm_footer):not(:has(> .st-key-sm_history)) {{
    flex: 0 0 auto;
}}

[data-testid="stSidebar"] :has(> .st-key-sm_history):not(:has(> .st-key-sm_header)) {{
    flex: 1 1 auto;
    min-height: 0;
    display: flex;
    flex-direction: column;
}}
[data-testid="stSidebar"] .st-key-sm_history {{
    flex: 1 1 auto;
    min-height: 0;
    overflow-y: auto;
    overflow-x: hidden;
    padding-right: 4px;
    flex-wrap: nowrap;
}}

[data-testid="stSidebarCollapseButton"] button,
[data-testid="stSidebarCollapseButton"] svg,
[data-testid="collapsedControl"] svg {{ color: var(--sm-ink) !important; }}

/* ---------- Text ---------- */
p, span, label, h1, h2, h3, h4, h5, h6, li,
.stMarkdown, [data-testid="stMarkdownContainer"], [data-testid="stCaptionContainer"] {{
    color: var(--sm-ink) !important;
}}
[data-testid="stCaptionContainer"], .sm-note {{ color: var(--sm-muted) !important; font-size: .8rem; }}
hr {{ border-color: var(--sm-border) !important; }}

/* ---------- Scrollbars ---------- */
::-webkit-scrollbar {{ width: 6px; height: 6px; }}
::-webkit-scrollbar-track {{ background: transparent; }}
::-webkit-scrollbar-thumb {{ background: var(--sm-border); border-radius: 10px; }}
::-webkit-scrollbar-thumb:hover {{ background: var(--sm-purple); }}

/* ---------- Brand ---------- */
.sm-brand {{ display: flex; gap: 12px; align-items: center; margin-bottom: 1rem; margin-top: 0.5rem; }}
.sm-logo {{ width: 42px; height: 42px; border-radius: 12px; display: flex; align-items: center; justify-content: center; background: var(--sm-purple); color: white; font-size: 22px; box-shadow: 0 4px 12px rgba(118, 86, 168, 0.25); }}
.sm-brand h1 {{ font-size: 1.35rem; line-height: 1.15; margin: 0; padding: 0; color: var(--sm-ink) !important; }}
.sm-brand p {{ margin: 2px 0 0; color: var(--sm-muted) !important; font-size: .82rem; }}

/* ---------- Welcome screen ---------- */
.sm-welcome {{
    display: flex; flex-direction: column; align-items: center; justify-content: center;
    text-align: center;
    min-height: 58vh;
    gap: .35rem;
}}
.sm-welcome-logo {{
    width: 76px; height: 76px; border-radius: 22px;
    display: flex; align-items: center; justify-content: center;
    background: var(--sm-purple); color: white; font-size: 40px;
    margin-bottom: .9rem;
    box-shadow: 0 8px 24px rgba(118, 86, 168, 0.28);
}}
.sm-welcome h1 {{ font-size: 2.2rem; line-height: 1.15; margin: 0; padding: 0; color: var(--sm-ink) !important; }}
.sm-welcome p {{ margin: 0; color: var(--sm-muted) !important; font-size: 1.05rem; }}

/* ---------- Professional Landing Page Styles ---------- */
.landing-hero {{
    padding: 2rem 0 3rem 0;
}}
.landing-badge {{
    display: inline-flex;
    align-items: center;
    gap: 8px;
    padding: 6px 16px;
    background: var(--sm-surface);
    border: 1px solid var(--sm-border);
    border-radius: 20px;
    font-size: 0.85rem;
    color: var(--sm-purple);
    font-weight: 600;
    margin-bottom: 1.2rem;
    box-shadow: 0 2px 8px rgba(0,0,0,0.02);
}}
.landing-title {{
    font-size: 3.2rem;
    font-weight: 800;
    line-height: 1.1;
    margin-bottom: 1.2rem;
    color: var(--sm-ink);
    letter-spacing: -0.02em;
}}
.landing-subtitle {{
    font-size: 1.15rem;
    color: var(--sm-muted);
    line-height: 1.6;
    margin-bottom: 2rem;
}}
.hero-card-visual {{
    background: linear-gradient(135deg, var(--sm-panel) 0%, var(--sm-surface) 100%);
    border: 1px solid var(--sm-border);
    border-radius: 24px;
    padding: 2.5rem;
    text-align: center;
    box-shadow: 0 12px 32px rgba(118, 86, 168, 0.1);
    position: relative;
    overflow: hidden;
}}
.hero-card-visual::before {{
    content: '';
    position: absolute;
    top: -50px; right: -50px;
    width: 150px; height: 150px;
    background: var(--sm-purple);
    opacity: 0.08;
    border-radius: 50%;
    filter: blur(20px);
}}
.feature-card {{
    background: var(--sm-surface);
    border: 1px solid var(--sm-border);
    border-radius: 18px;
    padding: 1.5rem 1.2rem;
    height: 280px;
    display: flex;
    flex-direction: column;
    justify-content: flex-start;
    box-shadow: 0 4px 16px rgba(0,0,0,0.03);
    transition: transform 0.25s ease, border-color 0.25s ease, box-shadow 0.25s ease;
    overflow: hidden;
}}
.feature-card:hover {{
    border-color: var(--sm-purple);
    transform: translateY(-4px);
    box-shadow: 0 8px 24px rgba(118, 86, 168, 0.12);
}}
.feature-icon {{
    font-size: 28px;
    margin-bottom: 0.6rem;
    display: inline-block;
    padding: 8px;
    background: var(--sm-panel);
    border-radius: 10px;
    width: fit-content;
}}
.feature-card h3 {{
    font-size: 1.05rem;
    font-weight: 700;
    margin-bottom: 0.4rem;
    color: var(--sm-ink);
    line-height: 1.3;
}}
.feature-card p {{
    font-size: 0.86rem;
    color: var(--sm-muted);
    line-height: 1.45;
    margin: 0;
}}

/* Strictly Centered Step Cards with Uniform Size */
.step-card {{
    background: var(--sm-surface);
    border: 1px solid var(--sm-border);
    border-radius: 18px;
    padding: 2rem 1.2rem;
    min-height: 280px;
    height: 100%;
    display: flex;
    flex-direction: column;
    align-items: center !important;
    justify-content: flex-start !important;
    text-align: center !important;
    box-shadow: 0 4px 16px rgba(0,0,0,0.03);
    transition: transform 0.25s ease, border-color 0.25s ease, box-shadow 0.25s ease;
}}
.step-card:hover {{
    border-color: var(--sm-purple);
    transform: translateY(-4px);
    box-shadow: 0 8px 24px rgba(118, 86, 168, 0.12);
}}
.step-card h3 {{
    font-size: 1.05rem !important;
    font-weight: 700 !important;
    margin-bottom: 0.6rem !important;
    color: var(--sm-ink) !important;
    text-align: center !important;
    width: 100% !important;
}}
.step-card p {{
    font-size: 0.88rem !important;
    color: var(--sm-muted) !important;
    line-height: 1.5 !important;
    margin: 0 !important;
    text-align: center !important;
    width: 100% !important;
}}

.demo-card {{
    background: var(--sm-surface);
    border: 1px solid var(--sm-border);
    border-radius: 16px;
    padding: 1.5rem;
    text-align: center;
    box-shadow: 0 4px 12px rgba(0,0,0,0.02);
    min-height: 150px;
    display: flex;
    flex-direction: column;
    justify-content: center;
    align-items: center;
}}
.step-number {{
    width: 38px; height: 38px;
    background: var(--sm-purple);
    color: white;
    font-weight: 700;
    border-radius: 50%;
    display: flex; align-items: center; justify-content: center;
    margin: 0 auto 1.2rem auto;
    font-size: 1rem;
    box-shadow: 0 4px 12px rgba(118, 86, 168, 0.25);
    flex-shrink: 0;
}}
.cta-box {{
    background: var(--sm-surface);
    border: 1px solid var(--sm-border);
    border-radius: 20px;
    padding: 2.5rem;
    text-align: center;
    box-shadow: 0 8px 24px rgba(118, 86, 168, 0.08);
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
}}

/* Feedback Card Style */
.feedback-card {{
    background: var(--sm-surface);
    border: 1px solid var(--sm-border);
    border-radius: 16px;
    padding: 1.8rem;
    text-align: center;
    box-shadow: 0 4px 16px rgba(0,0,0,0.03);
    min-height: 200px;
    height: 100%;
    display: flex;
    flex-direction: column;
    justify-content: center;
    align-items: center;
}}

/* Navbar Styling Fixes */
.sm-navbar {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    width: 100%;
    padding: 0.4rem 0.2rem;
}}
.sm-navbar-brand {{
    display: flex;
    align-items: center;
    gap: 10px;
    white-space: nowrap;
}}
.sm-navbar-links {{
    display: flex;
    align-items: center;
    gap: 28px;
    white-space: nowrap;
}}
.sm-navbar-links a {{
    color: var(--sm-muted);
    text-decoration: none;
    font-weight: 500;
    font-size: 0.95rem;
    transition: color 0.2s ease;
}}
.sm-navbar-links a:hover {{
    color: var(--sm-purple);
}}

/* ---------- Buttons ---------- */
.stButton > button, [data-testid="stBaseButton-secondary"] {{
    border-radius: 10px;
    border: 1px solid var(--sm-border) !important;
    background: var(--sm-surface) !important;
    color: var(--sm-ink) !important;
    font-weight: 500;
    transition: all 0.2s ease;
}}
.stButton > button:hover, [data-testid="stBaseButton-secondary"]:hover {{
    background: var(--sm-hover) !important;
    border-color: var(--sm-purple) !important;
    color: var(--sm-purple) !important;
}}
.stButton > button p, [data-testid="stBaseButton-secondary"] p {{ color: var(--sm-ink) !important; }}
.stButton > button[kind="primary"], [data-testid="stBaseButton-primary"] {{
    background: var(--sm-purple) !important;
    border-color: var(--sm-purple) !important;
    color: #fff !important;
    box-shadow: 0 4px 14px rgba(118, 86, 168, 0.3);
}}
.stButton > button[kind="primary"] p, [data-testid="stBaseButton-primary"] p {{ color: #fff !important; }}
.stButton > button[kind="primary"]:hover {{
    opacity: 0.92;
    transform: translateY(-1px);
}}

/* Modern Compact Action Buttons in Navbar */
div[data-testid="stColumn"] button {{
    white-space: nowrap !important;
}}

/* ---------- Sidebar Footer Profile Button Fix for Dark/Light Mode ---------- */
[data-testid="stSidebar"] [data-testid="stPopover"] button {{
    background: var(--sm-surface) !important;
    border: 1px solid var(--sm-border) !important;
    color: var(--sm-ink) !important;
}}
[data-testid="stSidebar"] [data-testid="stPopover"] button p {{
    color: var(--sm-ink) !important;
}}
[data-testid="stSidebar"] [data-testid="stPopover"] button:hover {{
    background: var(--sm-hover) !important;
    border-color: var(--sm-purple) !important;
    color: var(--sm-purple) !important;
}}
[data-testid="stSidebar"] [data-testid="stPopover"] button:hover p {{
    color: var(--sm-purple) !important;
}}

/* ---------- Sidebar chat rows ---------- */
[class*="st-key-row_"] {{
    border-radius: 10px;
    transition: background .15s ease;
}}
[class*="st-key-row_"]:hover {{
    background: var(--sm-hover);
}}
[class*="st-key-row_"] [data-testid="stHorizontalBlock"] {{
    gap: 0 !important;
    align-items: center;
}}
[class*="st-key-row_"] .stButton > button {{
    background: transparent !important;
    border: none !important;
    box-shadow: none !important;
    justify-content: flex-start;
    text-align: left;
}}
[class*="st-key-row_"] .stButton > button:hover {{
    background: transparent !important;
    border: none !important;
}}
[class*="st-key-row_"] .stButton > button [data-testid="stMarkdownContainer"] {{
    width: 100%;
    text-align: left;
}}
[class*="st-key-row_"] [data-testid="stPopover"] button {{
    background: transparent !important;
    border: none !important;
    box-shadow: none !important;
    padding: 0 !important;
    min-width: 0;
    width: 100%;
    justify-content: center;
    opacity: 0;
    transition: opacity .15s ease;
}}
[class*="st-key-row_"]:hover [data-testid="stPopover"] button,
[class*="st-key-row_"] [data-testid="stPopover"] button[aria-expanded="true"] {{
    opacity: 1;
}}
[class*="st-key-row_"] [data-testid="stPopover"] button:hover {{
    background: var(--sm-border) !important;
    border-radius: 8px;
}}
[class*="st-key-row_"] [data-testid="stPopover"] button svg,
[class*="st-key-row_"] [data-testid="stPopover"] button [data-testid="stIconMaterial"] {{
    display: none !important;
}}
[class*="st-key-row_"] [data-testid="stPopover"] button p {{
    font-size: 1.1rem;
    line-height: 1;
}}

/* ---------- Modern Profile Menu Popover Styling ---------- */
[data-testid="stPopoverBody"] {{
    background: var(--sm-surface) !important;
    border: 1px solid var(--sm-border) !important;
    border-radius: 14px !important;
    min-width: 0 !important;
    width: 250px !important;
    padding: 10px !important;
    box-shadow: 0 10px 30px rgba(0,0,0,0.2) !important;
}}
[data-testid="stPopoverBody"] .stButton > button {{
    background: transparent !important;
    border: 1px solid var(--sm-border) !important;
    justify-content: flex-start;
    padding: 0.35rem 0.6rem !important;
    min-height: 0 !important;
    height: auto !important;
    border-radius: 8px !important;
}}
[data-testid="stPopoverBody"] .stButton > button p {{
    font-size: 0.85rem !important;
    line-height: 1.2 !important;
    margin: 0 !important;
}}
[data-testid="stPopoverBody"] .stButton > button:hover {{
    background: var(--sm-hover) !important;
    border-color: var(--sm-purple) !important;
}}
[data-testid="stPopoverBody"] [data-testid="stToggle"] {{
    margin-bottom: 2px !important;
    margin-top: 2px !important;
}}

[data-testid="stCheckbox"] label span, [data-testid="stToggle"] label span,
[data-testid="stToggle"] p {{ color: var(--sm-ink) !important; }}

/* ---------- Chat messages (Spacious & Expanded) ---------- */
[data-testid="stChatMessage"] {{
    border: 1px solid var(--sm-border);
    border-radius: 18px;
    padding: 1.1rem 1.3rem;
    margin-bottom: 0.8rem;
    max-width: 100% !important;
    box-shadow: 0 4px 12px rgba(0,0,0,0.04);
    background: var(--sm-bot) !important;
}}
div[data-testid="stChatMessage"]:has([aria-label="Chat message from user"]),
div[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) {{
    background: var(--sm-user) !important;
}}
div[data-testid="stChatMessage"]:has([aria-label="Chat message from assistant"]),
div[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarAssistant"]) {{
    background: var(--sm-bot) !important;
}}
[data-testid="stChatMessage"] p, [data-testid="stChatMessage"] li {{ color: var(--sm-ink) !important; line-height: 1.6; }}

/* ---------- Chat input ---------- */
[data-testid="stBottom"], [data-testid="stBottom"] > div,
[data-testid="stBottomBlockContainer"], .stChatFloatingInputContainer {{
    background: var(--sm-bg) !important;
}}
[data-testid="stChatInput"], [data-testid="stChatInput"] > div {{
    background: var(--sm-panel) !important;
    border-color: var(--sm-border) !important;
    border-radius: 16px;
}}
[data-testid="stChatInput"] textarea {{
    background: transparent !important;
    color: var(--sm-ink) !important;
    -webkit-text-fill-color: var(--sm-ink) !important;
}}
[data-testid="stChatInput"] textarea::placeholder {{
    color: var(--sm-muted) !important;
    -webkit-text-fill-color: var(--sm-muted) !important;
    opacity: 1;
}}
[data-testid="stChatInputSubmitButton"] {{
    background: transparent !important;
    color: var(--sm-ink) !important;
}}
[data-testid="stChatInputSubmitButton"]:hover {{ background: var(--sm-hover) !important; }}
[data-testid="stChatInputSubmitButton"] svg {{ color: var(--sm-ink) !important; fill: var(--sm-ink) !important; }}

/* ---------- Thinking Indicator ---------- */
.sm-thinking {{
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 8px 4px;
}}
.sm-dot {{
    width: 8px;
    height: 8px;
    background: var(--sm-muted);
    border-radius: 50%;
    animation: sm-bounce 1.4s infinite ease-in-out both;
}}
.sm-dot:nth-child(1) {{ animation-delay: -0.32s; }}
.sm-dot:nth-child(2) {{ animation-delay: -0.16s; }}
@keyframes sm-bounce {{
    0%, 80%, 100% {{ transform: scale(0); }}
    40% {{ transform: scale(1.0); }}
}}

[data-testid="stAlert"], [data-testid="stExpander"] {{
    background: var(--sm-panel) !important;
    border-color: var(--sm-border) !important;
}}
code, pre {{ background: var(--sm-panel) !important; color: var(--sm-ink) !important; }}
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Authentication & Landing Page Flow
# ---------------------------------------------------------------------------
if not st.session_state.authenticated:
    col_nav_brand, col_nav_links, col_nav_actions = st.columns([1.8, 3.2, 2.5])
    
    with col_nav_brand:
        st.markdown("""
        <div id="home" class="sm-navbar-brand">
            <div style="width: 38px; height: 38px; border-radius: 10px; background: var(--sm-purple); display: flex; align-items: center; justify-content: center; color: white; font-size: 18px; box-shadow: 0 4px 12px rgba(118, 86, 168, 0.25);">👗</div>
            <span style="font-weight: 700; font-size: 1.25rem; color: var(--sm-ink);">StyleMate AI</span>
        </div>
        """, unsafe_allow_html=True)

    with col_nav_links:
        st.markdown("""
        <div class="sm-navbar-links" style="height: 100%; justify-content: center; padding-top: 6px;">
            <a href="#home">Home</a>
            <a href="#features">Features</a>
            <a href="#how-it-works">How It Works</a>
            <a href="#about">About</a>
        </div>
        """, unsafe_allow_html=True)

    with col_nav_actions:
        c_mode, c_signin, c_signup = st.columns([1.1, 1, 1.2])
        with c_mode:
            theme_btn_text = "🌙 Dark" if st.session_state.theme == "light" else "☀️ Light"
            if st.button(theme_btn_text, use_container_width=True):
                st.session_state.theme = "dark" if st.session_state.theme == "light" else "light"
                st.query_params["theme"] = st.session_state.theme
                st.rerun()
        with c_signin:
            if st.button("Sign In", use_container_width=True):
                st.session_state.auth_view = "login"
                st.rerun()
        with c_signup:
            if st.button("Get Started", type="primary", use_container_width=True):
                st.session_state.auth_view = "signup"
                st.rerun()

    st.markdown("<hr style='margin-top: 0.8rem; margin-bottom: 2rem;'>", unsafe_allow_html=True)

    view = st.session_state.auth_view

    if view == "landing":
        st.markdown("""
        <div class="landing-hero">
        """, unsafe_allow_html=True)
        
        hero_left, hero_right = st.columns([1.2, 1], gap="large")
        with hero_left:
            st.markdown("""
            <div class="landing-badge">✨ Your Personal AI Fashion Assistant</div>
            <h1 class="landing-title">Your Style. Your Identity. Your AI Stylist.</h1>
            <p class="landing-subtitle">Discover personalized outfit ideas inspired by your occasion, season, skin tone, body type, and individual styling needs with advanced conversational intelligence.</p>
            """, unsafe_allow_html=True)
            
            c_cta1, c_cta2 = st.columns(2)
            with c_cta1:
                if st.button("Get Started Free 🚀", type="primary", use_container_width=True):
                    st.session_state.auth_view = "signup"
                    st.rerun()
            with c_cta2:
                if st.button("Sign In to Account", use_container_width=True):
                    st.session_state.auth_view = "login"
                    st.rerun()

        with hero_right:
            st.markdown("""
            <div class="hero-card-visual">
                <div style="font-size: 56px; margin-bottom: 1rem;">✨👗✨</div>
                <h3 style="font-size: 1.3rem; font-weight: 700; margin-bottom: 0.5rem; color: var(--sm-ink);">Intelligent Outfit Curation</h3>
                <p style="color: var(--sm-muted); font-size: 0.92rem; margin: 0;">Tailored matching for Pakistani weddings, Eid celebrations, formal dinners, and university casual wear.</p>
            </div>
            """, unsafe_allow_html=True)

        st.markdown("</div>", unsafe_allow_html=True)
        st.markdown("<br><hr style='margin: 3rem 0;'><br>", unsafe_allow_html=True)

        st.markdown("""
        <div id="features" style="text-align: center; max-width: 650px; margin: 0 auto 3rem auto;">
            <div class="landing-badge">Powerful Capabilities</div>
            <h2 style="font-size: 2.2rem; font-weight: 800; margin-bottom: 0.8rem; color: var(--sm-ink);">Designed for Effortless Styling</h2>
            <p style="color: var(--sm-muted); font-size: 1.05rem;">Everything you need to plan your wardrobe, discover color harmonies, and coordinate accessories perfectly.</p>
        </div>
        """, unsafe_allow_html=True)

        f1, f2, f3 = st.columns(3, gap="medium")
        with f1:
            st.markdown("""
            <div class="feature-card">
                <div class="feature-icon">🎯</div>
                <h3>Smart Recommendations</h3>
                <p>Get precise outfit suggestions tailored to specific events, seasons, and personal preferences instantly.</p>
            </div>
            """, unsafe_allow_html=True)
        with f2:
            st.markdown("""
            <div class="feature-card">
                <div class="feature-icon">🎨</div>
                <h3>Skin Tone & Color Guide</h3>
                <p>Discover complementary hues and color palettes that naturally enhance your complexion and appearance.</p>
            </div>
            """, unsafe_allow_html=True)
        with f3:
            st.markdown("""
            <div class="feature-card">
                <div class="feature-icon">📐</div>
                <h3>Wearing Style & Body Type Guidance</h3>
                <p>Receive professional advice on silhouettes, cuts, and layering that flatter your unique body proportions.</p>
            </div>
            """, unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)

        f4, f5, f6 = st.columns(3, gap="medium")
        with f4:
            st.markdown("""
            <div class="feature-card">
                <div class="feature-icon">👞</div>
                <h3>Footwear</h3>
                <p>Complete your look with perfectly matched shoes and footwear styles for every outfit.</p>
            </div>
            """, unsafe_allow_html=True)
        with f5:
            st.markdown("""
            <div class="feature-card">
                <div class="feature-icon">👜</div>
                <h3>Accessories</h3>
                <p>Elevate your ensemble with carefully coordinated handbags, jewelry, and seasonal add-ons.</p>
            </div>
            """, unsafe_allow_html=True)
        with f6:
            st.markdown("""
            <div class="feature-card">
                <div class="feature-icon">🧠</div>
                <h3>Personalization</h3>
                <p>Enjoy a tailored styling experience with persistent memory for your sizing, preferences, and chat history.</p>
            </div>
            """, unsafe_allow_html=True)

        st.markdown("<br><hr style='margin: 3rem 0;'><br>", unsafe_allow_html=True)

        st.markdown("""
        <div style="text-align: center; max-width: 650px; margin: 0 auto 2.5rem auto;">
            <div class="landing-badge">Lookbook Preview</div>
            <h2 style="font-size: 2.2rem; font-weight: 800; margin-bottom: 0.8rem; color: var(--sm-ink);">Curated for Every Occasion</h2>
            <p style="color: var(--sm-muted); font-size: 1.05rem;">Explore sample outfits generated by StyleMate AI for popular cultural and modern events.</p>
        </div>
        """, unsafe_allow_html=True)

        d1, d2, d3, d4 = st.columns(4, gap="small")
        with d1:
            st.markdown("""
            <div class="demo-card">
                <div style="font-size: 28px; margin-bottom: 0.3rem;">👑</div>
                <h4 style="font-size: 0.95rem; font-weight: 700; margin-bottom: 0.2rem;">Pakistani Weddings</h4>
                <p style="font-size: 0.75rem; color: var(--sm-muted); margin: 0;">Embroidered Lehengas & Sherwanis</p>
            </div>
            """, unsafe_allow_html=True)
        with d2:
            st.markdown("""
            <div class="demo-card">
                <div style="font-size: 28px; margin-bottom: 0.3rem;">🌙</div>
                <h4 style="font-size: 0.95rem; font-weight: 700; margin-bottom: 0.2rem;">Eid Celebrations</h4>
                <p style="font-size: 0.75rem; color: var(--sm-muted); margin: 0;">Pastel Kurtis & Classic Shalwar Kameez</p>
            </div>
            """, unsafe_allow_html=True)
        with d3:
            st.markdown("""
            <div class="demo-card">
                <div style="font-size: 28px; margin-bottom: 0.3rem;">🎒</div>
                <h4 style="font-size: 0.95rem; font-weight: 700; margin-bottom: 0.2rem;">University Casual</h4>
                <p style="font-size: 0.75rem; color: var(--sm-muted); margin: 0;">Comfortable Denim & Layered Shirts</p>
            </div>
            """, unsafe_allow_html=True)
        with d4:
            st.markdown("""
            <div class="demo-card">
                <div style="font-size: 28px; margin-bottom: 0.3rem;">💼</div>
                <h4 style="font-size: 0.95rem; font-weight: 700; margin-bottom: 0.2rem;">Formal & Office</h4>
                <p style="font-size: 0.75rem; color: var(--sm-muted); margin: 0;">Tailored Blazers & Smart Trousers</p>
            </div>
            """, unsafe_allow_html=True)

        st.markdown("<br><hr style='margin: 3rem 0;'><br>", unsafe_allow_html=True)

        st.markdown("""
        <div id="how-it-works" style="text-align: center; max-width: 650px; margin: 0 auto 2.5rem auto;">
            <div class="landing-badge">Simple 3-Step Process</div>
            <h2 style="font-size: 2.2rem; font-weight: 800; margin-bottom: 0.8rem; color: var(--sm-ink);">How StyleMate AI Works</h2>
        </div>
        """, unsafe_allow_html=True)

        s1, s2, s3 = st.columns(3, gap="medium")
        with s1:
            st.markdown("""
            <div class="step-card">
                <div class="step-number">1</div>
                <h3>Share Your Requirements</h3>
                <p>Tell the AI about your event, preferred colors, season, and personal styling goals through natural chat.</p>
            </div>
            """, unsafe_allow_html=True)
        with s2:
            st.markdown("""
            <div class="step-card">
                <div class="step-number">2</div>
                <h3>Explore Recommendations</h3>
                <p>Receive tailored outfit combinations, garment breakdown details, and color harmony insights instantly.</p>
            </div>
            """, unsafe_allow_html=True)
        with s3:
            st.markdown("""
            <div class="step-card">
                <div class="step-number">3</div>
                <h3>Complete Your Look</h3>
                <p>Refine your selection and get personalized suggestions for footwear, accessories, and styling finishes.</p>
            </div>
            """, unsafe_allow_html=True)

        st.markdown("<br><br>", unsafe_allow_html=True)
        st.markdown('<div id="about"></div>', unsafe_allow_html=True)
        
        st.markdown("""
        <div style="text-align: center; max-width: 650px; margin: 0 auto 2.5rem auto;">
            <div class="landing-badge">Loved by Users</div>
            <h2 style="font-size: 2.2rem; font-weight: 800; margin-bottom: 0.8rem; color: var(--sm-ink);">User Feedback & Stories</h2>
            <p style="color: var(--sm-muted); font-size: 1.05rem;">See how StyleMate AI is helping people style their daily wardrobes and special occasions effortlessly.</p>
        </div>
        """, unsafe_allow_html=True)

        fb1, fb2, fb3 = st.columns(3, gap="medium")
        with fb1:
            st.markdown("""
            <div class="feedback-card">
                <div style="color: var(--sm-purple); font-size: 20px; margin-bottom: 0.5rem;">⭐⭐⭐⭐⭐</div>
                <p style="font-size: 0.90rem; font-style: italic; color: var(--sm-ink); margin-bottom: 0.8rem;">"StyleMate AI saved my outfit planning for my cousin's wedding! The traditional wear recommendations were spot on."</p>
                <p style="font-size: 0.80rem; font-weight: 700; color: var(--sm-muted); margin: 0;">— Ayesha K.</p>
            </div>
            """, unsafe_allow_html=True)
        with fb2:
            st.markdown("""
            <div class="feedback-card">
                <div style="color: var(--sm-purple); font-size: 20px; margin-bottom: 0.5rem;">⭐⭐⭐⭐⭐</div>
                <p style="font-size: 0.90rem; font-style: italic; color: var(--sm-ink); margin-bottom: 0.8rem;">"The skin tone color guide helped me choose colors that actually complement me. Absolutely love the conversational UI!"</p>
                <p style="font-size: 0.80rem; font-weight: 700; color: var(--sm-muted); margin: 0;">— Zainab M.</p>
            </div>
            """, unsafe_allow_html=True)
        with fb3:
            st.markdown("""
            <div class="feedback-card">
                <div style="color: var(--sm-purple); font-size: 20px; margin-bottom: 0.5rem;">⭐⭐⭐⭐⭐</div>
                <p style="font-size: 0.90rem; font-style: italic; color: var(--sm-ink); margin-bottom: 0.8rem;">"Super fast and smart recommendations for university wear. It feels like having a personal stylist right in your pocket."</p>
                <p style="font-size: 0.80rem; font-weight: 700; color: var(--sm-muted); margin: 0;">— Fatima R.</p>
            </div>
            """, unsafe_allow_html=True)

        st.markdown("<br><br>", unsafe_allow_html=True)
        _, col_b_cta, _ = st.columns([1, 1.3, 1])
        with col_b_cta:
            st.markdown("""
            <div class="cta-box">
                <h3 style="font-size: 1.5rem; font-weight: 800; margin-bottom: 0.6rem; color: var(--sm-ink);">Ready to Transform Your Wardrobe?</h3>
                <p style="color: var(--sm-muted); font-size: 0.95rem; margin-bottom: 1.5rem;">Join StyleMate AI today and experience intelligent, personalized fashion styling.</p>
            """, unsafe_allow_html=True)
            
            if st.button("Get Started Now 🚀", type="primary", use_container_width=True):
                st.session_state.auth_view = "signup"
                st.rerun()
            
            st.markdown("</div>", unsafe_allow_html=True)
        st.markdown("<br><br>", unsafe_allow_html=True)

    elif view == "login":
        _, col_auth, _ = st.columns([1, 1.3, 1])
        with col_auth:
            st.markdown("### Welcome Back")
            st.caption("Sign in to continue your fashion journey.")
            
            login_email = st.text_input("Email Address", key="login_email_input")
            login_pass = st.text_input("Password", type="password", key="login_pass_input")
            
            if st.button("Sign In", type="primary", use_container_width=True):
                success, msg, uid = authenticate_user(login_email, login_pass)
                if success:
                    st.session_state.authenticated = True
                    st.session_state.user_id = uid
                    st.session_state.conversation_id = None
                    prefs, remember = get_preferences(uid)
                    st.session_state.remember_enabled = remember
                    st.session_state.profile = new_profile(remembered_preferences(prefs) if remember else None)
                    raw_token = secrets.token_hex(32)
                    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
                    set_user_session_token(uid, token_hash)
                    cookie_manager.set("stylemate_session_token", raw_token, expires_at=None)
                    st.success(msg)
                    time.sleep(0.3)
                    st.rerun()
                else:
                    st.error(msg)

            c_link1, c_link2 = st.columns(2)
            with c_link1:
                if st.button("Forgot Password?", use_container_width=True):
                    st.session_state.auth_view = "forgot"
                    st.rerun()
            with c_link2:
                if st.button("Create Account", use_container_width=True):
                    st.session_state.auth_view = "signup"
                    st.rerun()

            if st.button("← Back to Home", use_container_width=True):
                st.session_state.auth_view = "landing"
                st.rerun()

    elif view == "signup":
        _, col_auth, _ = st.columns([1, 1.3, 1])
        with col_auth:
            st.markdown("### Create Your Account")
            st.caption("Join StyleMate AI and get your personal stylist today.")

            signup_name = st.text_input("Full Name", key="signup_name_input")
            signup_email = st.text_input("Email Address", key="signup_email_input")
            signup_pass = st.text_input("Create Password", type="password", key="signup_pass_input")
            signup_confirm = st.text_input("Confirm Password", type="password", key="signup_confirm_input")

            if st.button("Sign Up & Start Chatting", type="primary", use_container_width=True):
                success, msg, uid = register_user(signup_name, signup_email, signup_pass, signup_confirm)
                if success:
                    st.session_state.authenticated = True
                    st.session_state.user_id = uid
                    st.session_state.conversation_id = None
                    prefs, remember = get_preferences(uid)
                    st.session_state.remember_enabled = remember
                    st.session_state.profile = new_profile(remembered_preferences(prefs) if remember else None)
                    raw_token = secrets.token_hex(32)
                    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
                    set_user_session_token(uid, token_hash)
                    cookie_manager.set("stylemate_session_token", raw_token, expires_at=None)
                    st.success(msg)
                    time.sleep(0.3)
                    st.rerun()
                else:
                    st.error(msg)

            if st.button("Already have an account? Sign In", use_container_width=True):
                st.session_state.auth_view = "login"
                st.rerun()

            if st.button("← Back to Home", use_container_width=True):
                st.session_state.auth_view = "landing"
                st.rerun()

    elif view == "forgot":
        _, col_auth, _ = st.columns([1, 1.3, 1])
        with col_auth:
            st.markdown("### Reset Password")
            st.caption("Enter your registered email and set a new password.")
            st.info("ℹ️ Local Development Mode: Since email delivery is not configured in this local environment, you can reset your password directly below.")

            reset_email = st.text_input("Registered Email Address", key="reset_email_input")
            new_pass = st.text_input("New Password (min 6 chars)", type="password", key="reset_new_pass")
            confirm_pass = st.text_input("Confirm New Password", type="password", key="reset_confirm_pass")

            if st.button("Reset Password", type="primary", use_container_width=True):
                success, msg = reset_password(reset_email, new_pass, confirm_pass)
                if success:
                    st.success(msg)
                    st.session_state.auth_view = "login"
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error(msg)

            if st.button("Back to Sign In", use_container_width=True):
                st.session_state.auth_view = "login"
                st.rerun()

    st.stop()

# Retrieve authenticated user ID
user_id = st.session_state.user_id
saved_preferences, remember_saved = get_preferences(user_id)

# Always open on the welcome screen when the app starts
if "conversation_id" not in st.session_state:
    st.session_state.conversation_id = None
if "remember_enabled" not in st.session_state:
    st.session_state.remember_enabled = remember_saved
if "profile" not in st.session_state:
    st.session_state.profile = new_profile(remembered_preferences(saved_preferences) if remember_saved else None)
if "pinned_chats" not in st.session_state:
    st.session_state.pinned_chats = []
if "active_menu" not in st.session_state:
    st.session_state.active_menu = None
if "is_thinking" not in st.session_state:
    st.session_state.is_thinking = False

with st.sidebar:
    with st.container(key="sm_header"):
        st.markdown('<div class="sm-brand"><div class="sm-logo">✦</div><div><h1>StyleMate AI</h1><p>Your personal outfit companion</p></div></div>', unsafe_allow_html=True)

        if st.button("＋  New chat", type="primary", use_container_width=True):
            st.session_state.conversation_id = None
            st.session_state.profile = new_profile(remembered_preferences(saved_preferences) if st.session_state.remember_enabled else None)
            st.session_state.active_menu = None
            st.session_state.is_thinking = False
            st.rerun()

        st.markdown("**Recent chats**")

    with st.container(key="sm_history"):
        conversations = list_conversations(user_id)
        conversations = sorted(
            conversations,
            key=lambda c: 0 if c["id"] in st.session_state.pinned_chats else 1
        )

        if not conversations:
            st.caption("Your conversations will appear here.")

        for conversation in conversations:
            conv_id = conversation["id"]
            title = (conversation["title"] or "Fashion chat").strip()
            is_pinned = conv_id in st.session_state.pinned_chats
            prefix = "📌 " if is_pinned else "💬 "
            label = title if len(title) <= 20 else title[:17] + "…"

            with st.container(key=f"row_{conv_id}"):
                col_chat, col_dots = st.columns([0.82, 0.18])
                with col_chat:
                    if st.button(prefix + label, key=f"chat_{conv_id}", use_container_width=True):
                        st.session_state.conversation_id = conv_id
                        prefs, remember = get_preferences(user_id)
                        st.session_state.remember_enabled = remember
                        conversation_profile = get_conversation_profile(conv_id)
                        if not conversation_profile:
                            conversation_profile = rebuild_profile(get_messages(conv_id))
                            save_conversation_profile(conv_id, conversation_profile)
                        st.session_state.profile = new_profile(conversation_profile)
                        st.session_state.active_menu = None
                        st.session_state.is_thinking = False
                        st.rerun()
                with col_dots:
                    with st.popover("⋮", use_container_width=True):
                        pin_text = "📌  Unpin" if is_pinned else "📌  Pin"
                        if st.button(pin_text, key=f"pin_action_{conv_id}", use_container_width=True):
                            if is_pinned:
                                st.session_state.pinned_chats.remove(conv_id)
                            else:
                                st.session_state.pinned_chats.append(conv_id)
                            st.session_state.active_menu = None
                            st.rerun()
                        if st.button("🗑️  Delete", key=f"del_action_{conv_id}", use_container_width=True):
                            delete_conversation(conv_id, user_id)
                            if st.session_state.conversation_id == conv_id:
                                st.session_state.conversation_id = None
                                prefs, remember = get_preferences(user_id)
                                st.session_state.profile = new_profile(remembered_preferences(prefs) if remember else None)
                            if conv_id in st.session_state.pinned_chats:
                                st.session_state.pinned_chats.remove(conv_id)
                            st.session_state.active_menu = None
                            st.rerun()

    with st.container(key="sm_footer"):
        st.divider()
        user_info = get_user_by_id(user_id)
        display_name = user_info.get("display_name", "User") if user_info else "User"
        email_addr = user_info.get("email", "") if user_info else ""
        initial = display_name[0].upper() if display_name else "U"

        with st.popover(display_name, use_container_width=True):
            st.markdown(f"""
            <div style="display: flex; align-items: center; gap: 10px; padding: 2px 0 6px 0; border-bottom: 1px solid var(--sm-border); margin-bottom: 6px;">
                <div style="width: 34px; height: 34px; border-radius: 50%; background: var(--sm-purple); color: white; display: flex; align-items: center; justify-content: center; font-weight: 600; font-size: 14px; flex-shrink: 0;">{initial}</div>
                <div style="overflow: hidden; line-height: 1.2;">
                    <div style="font-weight: 600; font-size: 0.92rem; color: var(--sm-ink); white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">{display_name}</div>
                    <div style="font-size: 0.76rem; color: var(--sm-muted); white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">{email_addr}</div>
                </div>
            </div>
            """, unsafe_allow_html=True)

            st.markdown("<div style='font-size: 0.78rem; font-weight: 600; color: var(--sm-muted); margin-bottom: 2px;'>Appearance</div>", unsafe_allow_html=True)
            st.toggle(
                "Dark Mode",
                value=(st.session_state.theme == "dark"),
                key="theme_toggle_menu",
                on_change=on_theme_toggle,
            )

            st.markdown("<div style='font-size: 0.78rem; font-weight: 600; color: var(--sm-muted); margin: 6px 0 2px 0;'>Preferences & memory</div>", unsafe_allow_html=True)
            new_remember = st.toggle("Remember my preferences", value=st.session_state.remember_enabled, key="remember_toggle_menu")
            if new_remember != st.session_state.remember_enabled:
                st.session_state.remember_enabled = new_remember
                if new_remember:
                    save_preferences(user_id, remembered_preferences(st.session_state.profile), True)
                else:
                    save_preferences(user_id, {}, False)
                st.rerun()

            st.markdown("<div style='height: 1px; background: var(--sm-border); margin: 6px 0;'></div>", unsafe_allow_html=True)

            if st.button("Clear current chat", use_container_width=True, disabled=st.session_state.conversation_id is None):
                delete_conversation(st.session_state.conversation_id, user_id)
                st.session_state.conversation_id = None
                st.session_state.profile = new_profile(remembered_preferences(saved_preferences) if st.session_state.remember_enabled else None)
                st.session_state.active_menu = None
                st.session_state.is_thinking = False
                st.rerun()

            if st.button("Log out", use_container_width=True):
                set_user_session_token(user_id, None)
                cookie_manager.delete("stylemate_session_token")
                st.session_state.authenticated = False
                st.session_state.user_id = None
                st.session_state.conversation_id = None
                st.session_state.profile = new_profile()
                st.session_state.auth_view = "landing"
                st.session_state.active_menu = None
                st.session_state.is_thinking = False
                st.rerun()

conversation_id = st.session_state.conversation_id
conversation = get_conversation(conversation_id, user_id) if conversation_id is not None else None
if conversation_id is not None and conversation is None:
    st.session_state.conversation_id = None
    conversation_id = None

welcome_slot = st.empty()

if conversation_id is not None:
    st.markdown('<div class="sm-brand"><div class="sm-logo">👗</div><div><h1>StyleMate AI</h1><p>Thoughtful outfit ideas tailored for you.</p></div></div>', unsafe_allow_html=True)
    messages = get_messages(conversation_id)
else:
    messages = []
    welcome_slot.markdown(
        '<div class="sm-welcome">'
        '<div class="sm-welcome-logo">👗</div>'
        '<h1>StyleMate AI</h1>'
        '<p>Thoughtful outfit ideas tailored for you.</p>'
        '</div>',
        unsafe_allow_html=True,
    )

for message in messages:
    with st.chat_message(message["role"]):
        st.markdown(message["message"])

if st.session_state.is_thinking:
    with st.chat_message("assistant"):
        st.markdown('<div class="sm-thinking"><div class="sm-dot"></div><div class="sm-dot"></div><div class="sm-dot"></div></div>', unsafe_allow_html=True)

last_assistant = next((m["message"].lower() for m in reversed(messages) if m["role"] == "assistant"), "")
quick_replies = []
if last_assistant.startswith("are you looking for a male or female outfit"):
    quick_replies = ["Female", "Male"]
elif last_assistant.startswith("which age group"):
    quick_replies = ["Young adult", "Middle-aged adult", "Senior citizen", "Teenager", "Child"]
elif last_assistant.startswith("what is the occasion") or last_assistant.startswith("what occasion"):
    quick_replies = ["Formal Wear", "Wedding Wear", "Party Wear", "Casual Wear", "College Wear"]
elif last_assistant.startswith("how is the weather"):
    quick_replies = ["Summer", "Winter", "Spring", "Autumn"]

if quick_replies and len(messages) <= 5 and not st.session_state.is_thinking:
    st.caption("Quick suggestions")
    reply_cols = st.columns(len(quick_replies))
    for index, reply in enumerate(quick_replies):
        if reply_cols[index].button(reply, key=f"quick_{len(messages)}_{index}", use_container_width=True):
            st.session_state.pending_prompt = reply
            st.rerun()

prompt = st.chat_input("Message StyleMate…", disabled=st.session_state.is_thinking)
if not prompt and st.session_state.get("pending_prompt"):
    prompt = st.session_state.pop("pending_prompt")

if prompt and prompt.strip() and not st.session_state.is_thinking:
    prompt = prompt.strip()

    welcome_slot.empty()

    if st.session_state.conversation_id is None:
        new_conv_id = create_conversation(user_id, prompt)
        st.session_state.conversation_id = new_conv_id

    conversation_id = st.session_state.conversation_id
    add_message(conversation_id, "user", prompt)
    
    st.session_state.is_thinking = True
    st.rerun()

if st.session_state.is_thinking:
    time.sleep(0.35)
    conversation_id = st.session_state.conversation_id
    messages_curr = get_messages(conversation_id)
    last_user_msg = messages_curr[-1]["message"] if messages_curr else ""

    controller = ChatController(
        saved_preferences=st.session_state.profile,
        remember_enabled=st.session_state.remember_enabled,
    )
    response, profile = controller.handle_message(last_user_msg)
    st.session_state.profile = profile
    add_message(conversation_id, "assistant", response)
    update_conversation_title(conversation_id, last_user_msg)

    if st.session_state.remember_enabled:
        save_preferences(user_id, remembered_preferences(profile), True)
    save_conversation_profile(conversation_id, profile)
    for outfit_id in dict.fromkeys(re.findall(r"(?:Catalog ID|Outfit ID):\s*([A-Z]+-\d+)", response)):
        add_recommendation(conversation_id, outfit_id, response)
        
    st.session_state.is_thinking = False
    st.rerun()

components.html(
    """
    <script>
    function install() {
        var style = document.getElementById('sm-scroll-style') || document.createElement('style');
        style.id = 'sm-scroll-style';
        style.textContent =
            '#sm-scroll-btn{position:fixed;bottom:calc(env(safe-area-inset-bottom, 0px) + 126px);width:38px;height:38px;border-radius:50%;' +
            'display:flex;align-items:center;justify-content:center;cursor:pointer;padding:0;' +
            'border:1px solid var(--sm-border);background:var(--sm-surface);color:var(--sm-ink);' +
            'box-shadow:0 4px 14px rgba(0,0,0,.18);opacity:0;pointer-events:none;' +
            'transform:translateY(6px);transition:opacity .2s ease,transform .2s ease;z-index:1000;}' +
            '#sm-scroll-btn.visible{opacity:1;pointer-events:auto;transform:translateY(0);}' +
            '#sm-scroll-btn:hover{border-color:var(--sm-purple);}';
        if (!style.isConnected) document.head.appendChild(style);
        window.__smAutoScroll = true;
        if (window.__smScrollCleanup) window.__smScrollCleanup();

        var NEAR = 120;
        var stick = window.__smStickToBottom !== false;
        var raf = null;
        var listeners = new AbortController();

        var btn = document.getElementById('sm-scroll-btn') || document.createElement('button');
        btn.id = 'sm-scroll-btn';
        btn.type = 'button';
        btn.setAttribute('aria-label', 'Scroll to bottom');
        btn.innerHTML = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" ' +
            'stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 5v14M5 12l7 7 7-7"/></svg>';
        if (!btn.isConnected) document.body.appendChild(btn);

        function getScroller() {
            var sels = ['[data-testid="stAppScrollToBottomContainer"]', 'main.stMain', '[data-testid="stMain"]', 'section.main', '.main'];
            for (var i = 0; i < sels.length; i++) {
                var el = document.querySelector(sels[i]);
                if (el && el.scrollHeight > el.clientHeight + 1) return el;
            }
            return document.querySelector('[data-testid="stAppScrollToBottomContainer"]') ||
                document.querySelector('main.stMain') || document.scrollingElement;
        }
        function distFromBottom(el) { return el.scrollHeight - el.scrollTop - el.clientHeight; }
        function setStick(value) {
            stick = value;
            window.__smStickToBottom = value;
        }
        function toBottom(smooth) {
            var el = getScroller();
            if (el) el.scrollTo({ top: el.scrollHeight, behavior: smooth ? 'smooth' : 'auto' });
        }
        function updateButton() {
            var el = getScroller();
            if (!el) return;
            var r = el.getBoundingClientRect();
            btn.style.left = (r.right - 52) + 'px';
            btn.classList.toggle('visible', distFromBottom(el) > NEAR);
        }

        document.addEventListener('scroll', function (e) {
            if (e.target !== getScroller()) return;
            setStick(distFromBottom(e.target) <= NEAR);
            updateButton();
        }, { capture: true, signal: listeners.signal });

        var observer = new MutationObserver(function () {
            if (raf) return;
            raf = requestAnimationFrame(function () {
                raf = null;
                if (stick) toBottom(false);
                updateButton();
            });
        });
        observer.observe(document.body, { childList: true, subtree: true, characterData: true });
        window.__smScrollCleanup = function () {
            listeners.abort();
            observer.disconnect();
            if (raf) cancelAnimationFrame(raf);
        };

        btn.addEventListener('click', function () { setStick(true); toBottom(true); }, { signal: listeners.signal });

        document.addEventListener('keydown', function (e) {
            if (e.key === 'Enter' && !e.shiftKey && e.target.closest &&
                e.target.closest('[data-testid="stChatInput"]')) setStick(true);
            }, { capture: true, signal: listeners.signal });
        document.addEventListener('click', function (e) {
            if (e.target.closest && (e.target.closest('[data-testid="stChatInputSubmitButton"]') ||
                e.target.closest('[data-testid="stSidebar"]'))) setStick(true);
            }, { capture: true, signal: listeners.signal });
            window.addEventListener('resize', updateButton, { signal: listeners.signal });

        setTimeout(function () { toBottom(false); updateButton(); }, 100);
    }

    var s = window.parent.document.createElement('script');
    s.textContent = '(' + install.toString() + ')();';
    window.parent.document.head.appendChild(s);
    s.remove();
    </script>
    """,
    height=0,
)