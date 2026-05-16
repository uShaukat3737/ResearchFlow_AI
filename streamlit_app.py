import html
import os
import sys
import uuid

import streamlit as st
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
load_dotenv()

from app.graph.builder import create_research_graph
from app.utils.ui_helpers import (
    build_initial_inputs,
    extract_final_report,
    get_confidence_label,
)

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="ResearchFlow AI",
    page_icon="⚗️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Theme CSS ──────────────────────────────────────────────────────────────────
st.markdown(
    """
<style>
/* Base */
html, body, [class*="css"] { font-family: 'Inter', 'Segoe UI', sans-serif; }
.stApp { background-color: #0B1929; color: #EDE4C8; }

/* Sidebar */
[data-testid="stSidebar"] {
    background-color: #0F1E30;
    border-right: 1px solid #1E3A5F;
}
[data-testid="stSidebar"] .stMarkdown,
[data-testid="stSidebar"] label,
[data-testid="stSidebar"] p { color: #EDE4C8 !important; }

/* Typography */
h1 { color: #C9A84C !important; font-weight: 700 !important; letter-spacing: 1px; }
h2, h3 { color: #E2C97E !important; }
h4, h5, h6 { color: #B8A070 !important; }
p, li, span { color: #EDE4C8; }

/* Text input / textarea */
.stTextInput > div > div > input,
.stTextArea > div > div > textarea {
    background-color: #142236 !important;
    border: 1px solid #1E3A5F !important;
    color: #EDE4C8 !important;
    border-radius: 8px !important;
}
.stTextInput > div > div > input:focus,
.stTextArea > div > div > textarea:focus {
    border-color: #C9A84C !important;
    box-shadow: 0 0 0 2px rgba(201,168,76,0.25) !important;
}
.stTextInput label, .stTextArea label { color: #B8A070 !important; }

/* Primary button (form submit) */
.stFormSubmitButton > button,
button[kind="primary"] {
    background: linear-gradient(135deg, #C9A84C 0%, #8B6914 100%) !important;
    color: #0B1929 !important;
    border: none !important;
    border-radius: 8px !important;
    font-weight: 700 !important;
    font-size: 1rem !important;
    padding: 0.55rem 2rem !important;
    transition: all 0.2s ease !important;
}
.stFormSubmitButton > button:hover,
button[kind="primary"]:hover {
    background: linear-gradient(135deg, #E2C97E 0%, #C9A84C 100%) !important;
    transform: translateY(-1px) !important;
    box-shadow: 0 4px 16px rgba(201,168,76,0.45) !important;
}

/* Secondary button (sidebar) */
.stButton > button {
    background-color: #142236 !important;
    color: #C9A84C !important;
    border: 1px solid #1E3A5F !important;
    border-radius: 8px !important;
    font-weight: 600 !important;
    transition: all 0.2s ease !important;
}
.stButton > button:hover {
    border-color: #C9A84C !important;
    box-shadow: 0 0 8px rgba(201,168,76,0.3) !important;
}

/* Radio */
.stRadio > div { gap: 0.4rem; }
.stRadio label { color: #EDE4C8 !important; }
[data-testid="stWidgetLabel"] p { color: #B8A070 !important; }

/* Expander */
[data-testid="stExpander"] {
    background-color: #0F1E30;
    border: 1px solid #1E3A5F;
    border-radius: 10px;
}
[data-testid="stExpander"] summary {
    color: #C9A84C !important;
    font-weight: 600;
}

/* Metrics */
[data-testid="metric-container"] {
    background-color: #142236;
    border: 1px solid #1E3A5F;
    border-radius: 10px;
    padding: 1rem 1.2rem;
}
[data-testid="stMetricLabel"] { color: #7E90AA !important; }
[data-testid="stMetricValue"] { color: #C9A84C !important; }

/* Divider */
hr { border-color: #1E3A5F !important; }

/* Alerts */
.stAlert { border-radius: 8px !important; }

/* Scrollbar */
::-webkit-scrollbar { width: 5px; height: 5px; }
::-webkit-scrollbar-track { background: #0B1929; }
::-webkit-scrollbar-thumb { background: #1E3A5F; border-radius: 4px; }
::-webkit-scrollbar-thumb:hover { background: #C9A84C; }

/* Spinner */
.stSpinner > div { border-top-color: #C9A84C !important; }

/* ── Custom component classes ── */
.rf-stage-card {
    background-color: #142236;
    border: 1px solid #1E3A5F;
    border-radius: 10px;
    padding: 1rem 1.1rem;
    min-height: 110px;
    transition: border-color 0.3s ease, box-shadow 0.3s ease;
}
.rf-stage-card.active {
    border-color: #C9A84C;
    box-shadow: 0 0 14px rgba(201,168,76,0.35);
}
.rf-stage-card.complete {
    border-color: #2E7D52;
    background-color: #0C2118;
}
.rf-stage-card.pending { opacity: 0.45; }

.rf-stage-icon { font-size: 1.5rem; margin-bottom: 0.15rem; }
.rf-stage-title { font-weight: 700; color: #C9A84C; margin: 0 0 0.15rem 0; font-size: 0.95rem; }
.rf-stage-desc { color: #7E90AA; font-size: 0.78rem; margin: 0; }
.rf-stage-detail { color: #B8A070; font-size: 0.82rem; margin: 0.4rem 0 0 0; line-height: 1.5; }

.rf-report-wrapper {
    background-color: #0F1E30;
    border: 2px solid #C9A84C;
    border-radius: 12px;
    padding: 1.75rem 2rem;
    margin-top: 1.5rem;
    box-shadow: 0 0 24px rgba(201,168,76,0.15);
}
.rf-report-title { color: #E2C97E; font-size: 1.15rem; font-weight: 700; margin: 0 0 0.5rem 0; }
.rf-report-body {
    color: #EDE4C8;
    line-height: 1.8;
    white-space: pre-wrap;
    font-size: 0.97rem;
}

.rf-source-card {
    background-color: #142236;
    border: 1px solid #1E3A5F;
    border-radius: 8px;
    padding: 0.85rem 1rem;
    margin-bottom: 0.6rem;
}
.rf-source-title { color: #C9A84C; font-weight: 600; font-size: 0.92rem; margin: 0 0 0.2rem 0; }
.rf-source-url  { color: #5B8DB8; font-size: 0.78rem; margin: 0 0 0.3rem 0; }
.rf-source-body { color: #B0A890; font-size: 0.85rem; margin: 0; }

.rf-empty-state {
    text-align: center;
    padding: 4rem 0 3rem 0;
    color: #7E90AA;
}
.rf-empty-icon { font-size: 3.5rem; margin-bottom: 0.5rem; }
</style>
""",
    unsafe_allow_html=True,
)

# ── Session state ──────────────────────────────────────────────────────────────
_SESSION_DEFAULTS = {
    "graph": None,
    "thread_id": None,
    "completed_nodes": [],
    "awaiting_clarification": False,
    "final_report": None,
    "research_data": [],
    "last_pipeline_state": {},
}

for _k, _v in _SESSION_DEFAULTS.items():
    if _k not in st.session_state:
        st.session_state[_k] = _v

if st.session_state.graph is None:
    st.session_state.graph = create_research_graph()

if st.session_state.thread_id is None:
    st.session_state.thread_id = str(uuid.uuid4())

_config = {"configurable": {"thread_id": st.session_state.thread_id}}

# ── Sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## ⚗️ ResearchFlow AI")
    st.markdown("*Multi-Agent Business Intelligence*")
    st.markdown("---")

    st.markdown("#### LLM Provider")
    provider_choice = st.radio(
        "provider",
        options=["🖥️ Local — Ollama (phi3:mini)", "☁️ Cloud — Groq (llama-3.3-70b)"],
        label_visibility="collapsed",
    )
    if "Ollama" in provider_choice:
        os.environ["LLM_PROVIDER"] = "ollama"
        os.environ["OLLAMA_MODEL"] = "phi3:mini"
        st.success("Ollama active", icon="🖥️")
    else:
        os.environ["LLM_PROVIDER"] = "groq"
        st.success("Groq active", icon="☁️")

    st.markdown("---")
    st.markdown("#### Session")
    st.caption(f"Thread `{st.session_state.thread_id[:12]}…`")

    if st.button("⟳  New Session", use_container_width=True):
        for key in _SESSION_DEFAULTS:
            st.session_state[key] = _SESSION_DEFAULTS[key]
        st.rerun()

    st.markdown("---")
    st.markdown(
        """
#### Pipeline Stages
<small style='color:#7E90AA; line-height:2'>
<span style='color:#C9A84C'>🔍 Clarity Agent</span><br>
Validates scope &amp; intent<br><br>
<span style='color:#C9A84C'>🔬 Research Agent</span><br>
Web search + confidence scoring<br><br>
<span style='color:#C9A84C'>✅ Validator Agent</span><br>
Quality audit &amp; gap detection<br><br>
<span style='color:#C9A84C'>📊 Synthesis Agent</span><br>
Composes final report
</small>
""",
        unsafe_allow_html=True,
    )

# ── Header ────────────────────────────────────────────────────────────────────
st.markdown(
    """
<div style='text-align:center; padding: 1.5rem 0 0.75rem 0;'>
  <h1 style='font-size:2.4rem; letter-spacing:3px; margin-bottom:0.25rem;'>⚗️ RESEARCHFLOW AI</h1>
  <p style='color:#7E90AA; font-size:1rem; margin:0;'>
    Multi-Agent Business Intelligence &nbsp;·&nbsp;
    Clarity → Research → Validation → Synthesis
  </p>
</div>
""",
    unsafe_allow_html=True,
)
st.markdown("---")

# ── Stage card renderer ────────────────────────────────────────────────────────
_STAGE_META: dict[str, tuple[str, str, str]] = {
    "clarity_agent":   ("🔍", "Clarity Agent",   "Validates scope & intent"),
    "research_agent":  ("🔬", "Research Agent",  "Web search + confidence scoring"),
    "validator_agent": ("✅", "Validator Agent", "Quality audit & gap detection"),
    "synthesis_agent": ("📊", "Synthesis Agent", "Composes final report"),
}


def _render_stage_cards(completed_nodes: list[dict]) -> None:
    completed_map: dict[str, dict] = {}
    for entry in completed_nodes:
        completed_map[entry["node"]] = entry["update"]

    # The last node in the list is the one currently active (or just finished)
    active_node = completed_nodes[-1]["node"] if completed_nodes else None

    cols = st.columns(4, gap="small")
    for col, (node_key, (icon, title, desc)) in zip(cols, _STAGE_META.items()):
        with col:
            is_complete = node_key in completed_map
            is_active = node_key == active_node and not is_complete
            
            # Detect skipped validator agent: if synthesis started but validator didn't run
            is_skipped = (
                not is_complete 
                and node_key == "validator_agent" 
                and ("synthesis_agent" in completed_map or active_node == "synthesis_agent")
            )

            card_class = (
                "rf-stage-card complete"
                if is_complete
                else ("rf-stage-card active" if is_active else "rf-stage-card pending")
            )
            
            if is_skipped:
                badge = "»"  # Skip icon
            else:
                badge = "✓" if is_complete else ("▶" if is_active else "○")

            detail_lines: list[str] = []
            if is_complete:
                upd = completed_map[node_key]
                if "clarity_status" in upd:
                    detail_lines.append(f"Status: <b>{html.escape(str(upd['clarity_status']))}</b>")
                if "confidence_score" in upd:
                    lbl, emoji = get_confidence_label(upd["confidence_score"])
                    detail_lines.append(
                        f"Score: <b>{html.escape(str(upd['confidence_score']))}/10</b> {emoji}"
                    )
                if "attempts" in upd:
                    detail_lines.append(f"Attempt #{html.escape(str(upd['attempts']))}")
                if "validation_result" in upd and upd["validation_result"]:
                    detail_lines.append(
                        f"Result: <b>{html.escape(str(upd['validation_result']))}</b>"
                    )
                if "degraded_mode" in upd and upd["degraded_mode"]:
                    detail_lines.append("⚠️ Degraded mode")

            if is_skipped:
                detail_html = "Threshold met so skipped"
            elif is_complete:
                detail_html = "<br>".join(detail_lines) if detail_lines else "Completed"
            elif is_active:
                detail_html = "<em>In progress…</em>"
            else:
                detail_html = "Waiting"


            st.markdown(
                f"""
<div class='{card_class}'>
  <div class='rf-stage-icon'>{icon}</div>
  <p class='rf-stage-title'>{title} {badge}</p>
  <p class='rf-stage-desc'>{desc}</p>
  <p class='rf-stage-detail'>{detail_html}</p>
</div>
""",
                unsafe_allow_html=True,
            )


# ── Query form ────────────────────────────────────────────────────────────────
if st.session_state.awaiting_clarification:
    st.warning(
        "The AI needs clarification before continuing. Answer below.",
        icon="💬",
    )
    _query_label = "Your clarification"
    _placeholder = "Provide more detail to help narrow down the research…"
    _btn_label = "Submit Clarification"
else:
    _query_label = "Research Query"
    _placeholder = (
        "e.g. Analyse OpenAI's latest revenue figures and competitive positioning against Anthropic."
    )
    _btn_label = "Run Research ⟶"

with st.form("query_form", clear_on_submit=True):
    user_input = st.text_area(
        _query_label,
        placeholder=_placeholder,
        height=90,
    )
    submitted = st.form_submit_button(_btn_label, use_container_width=True)

# ── Pipeline execution ─────────────────────────────────────────────────────────
stage_placeholder = st.empty()

if submitted and user_input.strip():
    st.session_state.completed_nodes = []
    st.session_state.final_report = None
    st.session_state.research_data = []
    st.session_state.last_pipeline_state = {}

    inputs = build_initial_inputs(user_input.strip(), st.session_state.awaiting_clarification)

    with st.spinner("Multi-agent pipeline running…"):
        for event in st.session_state.graph.stream(inputs, _config, stream_mode="updates"):
            for node_name, state_update in event.items():
                update = state_update or {}
                st.session_state.completed_nodes.append({"node": node_name, "update": update})

                if update.get("research_data"):
                    st.session_state.research_data = update["research_data"]

                with stage_placeholder.container():
                    st.markdown("### Pipeline Execution")
                    _render_stage_cards(st.session_state.completed_nodes)

    final_state = st.session_state.graph.get_state(_config)
    state_values = final_state.values or {}
    st.session_state.final_report = extract_final_report(state_values.get("messages", []))
    st.session_state.last_pipeline_state = state_values
    st.session_state.awaiting_clarification = (
        state_values.get("clarity_status") == "needs_clarification"
    )
    # Ensure research_data is populated from final state if not already captured
    if not st.session_state.research_data and state_values.get("research_data"):
        st.session_state.research_data = state_values["research_data"]

    st.rerun()

# ── Persistent stage cards ────────────────────────────────────────────────────
with stage_placeholder.container():
    if st.session_state.completed_nodes:
        st.markdown("### Pipeline Execution")
        _render_stage_cards(st.session_state.completed_nodes)
    else:
        st.markdown(
            """
<div class='rf-empty-state'>
  <div class='rf-empty-icon'>🔬</div>
  <p style='font-size:1.1rem;'>Enter a research query above to launch the pipeline.</p>
  <p style='font-size:0.9rem;'>Clarity → Research → Validation → Synthesis</p>
</div>
""",
            unsafe_allow_html=True,
        )

# ── Research sources ──────────────────────────────────────────────────────────
if st.session_state.research_data:
    with st.expander(
        f"📚 Research Sources ({len(st.session_state.research_data)} found)", expanded=False
    ):
        for i, item in enumerate(st.session_state.research_data, 1):
            title = html.escape(str(item.get("title", item.get("url", f"Source {i}"))))
            url = html.escape(str(item.get("url", "")))
            snippet = html.escape(str(item.get("content", item.get("snippet", ""))))[:320]
            score = item.get("score", item.get("relevance_score", ""))

            url_html = (
                f"<p class='rf-source-url'><a href='{url}' target='_blank'>{url}</a></p>"
                if url
                else ""
            )
            score_html = (
                f"<p style='color:#7E90AA; font-size:0.78rem; margin:0.2rem 0 0 0;'>"
                f"Relevance: {html.escape(str(score))}</p>"
                if score
                else ""
            )
            body_html = (
                f"<p class='rf-source-body'>{snippet}{'…' if len(snippet) >= 320 else ''}</p>"
                if snippet
                else ""
            )

            st.markdown(
                f"""
<div class='rf-source-card'>
  <p class='rf-source-title'>{i}. {title}</p>
  {url_html}{body_html}{score_html}
</div>
""",
                unsafe_allow_html=True,
            )

# ── Final report ──────────────────────────────────────────────────────────────
if st.session_state.final_report:
    state = st.session_state.last_pipeline_state

    if state.get("degraded_mode"):
        st.error(
            f"Pipeline ran in degraded mode: {html.escape(str(state['degraded_mode']))}",
            icon="⚠️",
        )

    safe_report = html.escape(st.session_state.final_report)
    st.markdown(
        f"""
<div class='rf-report-wrapper'>
  <p class='rf-report-title'>📋 Research Report</p>
  <hr style='border-color:#1E3A5F; margin:0.5rem 0 1rem 0;'>
  <p class='rf-report-body'>{safe_report}</p>
</div>
""",
        unsafe_allow_html=True,
    )

    # Metrics row
    attempts = state.get("attempts", 0)
    conf_score = state.get("confidence_score", 0)
    conf_label, conf_emoji = get_confidence_label(conf_score)
    val_result = state.get("validation_result") or "—"
    sources_count = len(st.session_state.research_data)

    m1, m2, m3, m4 = st.columns(4)
    with m1:
        st.metric("Research Attempts", attempts)
    with m2:
        st.metric("Confidence Score", f"{conf_score}/10 {conf_emoji}")
    with m3:
        st.metric("Validation", val_result)
    with m4:
        st.metric("Sources Found", sources_count)
