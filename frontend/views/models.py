import streamlit as st
import ui

me = ui.guard("admin")
ui.hero("Models and RAG", "Local Ollama status, connection tests and the document search index. Nothing here is required: without a model the app uses rules, templates and keyword search.")
llm, rag = ui.call("GET", "/admin/llm/status") or {}, ui.call("GET", "/admin/rag/status") or {}
c = st.columns(4)
ui.kpi(c[0], "Chat model", llm.get("chat_model") or "none", f"provider: {llm.get('llm_provider', '?')}", ui.VIOLET)
ui.kpi(c[1], "Embedding model", llm.get("embed_model") if llm.get("embed_provider") == "ollama" else "off", f"provider: {llm.get('embed_provider', '?')}", ui.TEAL)
reach = llm.get("ollama_reachable")
ui.kpi(c[2], "Ollama", "reachable" if reach else ("not reachable" if reach is False else "not used"), llm.get("ollama_url", ""), "#34D399" if reach else "#FB923C")
ui.kpi(c[3], "Document search", "hybrid" if "hybrid" in rag.get("mode", "") else "keyword", f"{rag.get('vectors', 0)} of {rag.get('chunks', 0)} chunks embedded", ui.VIOLET)
st.write("")
if llm.get("error"): st.warning(f"Ollama check failed: {llm['error']}")
if llm.get("ollama_reachable"):
    st.caption("Installed models: " + (", ".join(llm["installed_models"]) or "none"))
    for k, label in (("chat_model_installed", "chat model"), ("embed_model_installed", "embedding model")):
        if llm.get(k) is False: st.warning(f"The configured {label} is not installed. Run the matching `ollama pull` command below.")
a, b = st.columns(2)
if a.button("Test chat and embeddings", width="stretch"):
    with st.spinner("Calling the models..."): r = ui.call("POST", "/admin/llm/test", timeout=120)
    if r:
        ch, em = r["chat"], r["embeddings"]
        ui.box("ok" if ch["ok"] else "warn", "Chat: " + (f"ok in {ch.get('latency_s')}s, {ch.get('tokens')} tokens ({ch['provider']})" if ch["ok"] else f"not available. {ch['error']}"))
        ui.box("ok" if em["ok"] else "warn", "Embeddings: " + (f"ok, {em['dims']} dimensions ({em['model']})" if em["ok"] else f"not available. {em['error']}"))
if b.button("Rebuild search index", width="stretch"):
    with st.spinner("Embedding runbooks and past incidents..."): r = ui.call("POST", "/admin/rag/reindex", timeout=300)
    if r: ui.flash("ok", f"Indexed {r['embedded_now']} new chunks of {r['chunks']} with {r['model']}."); st.rerun()
if rag.get("last_embedding_error"): st.caption(f"Last embedding error: {rag['last_embedding_error']}")
with st.expander("How to turn on local Ollama (PowerShell)"):
    st.code('''ollama pull llama3.1
ollama pull nomic-embed-text
$env:LLM_PROVIDER = "ollama"
$env:OLLAMA_MODEL = "llama3.1"
$env:EMBED_PROVIDER = "ollama"
$env:EMBED_MODEL = "nomic-embed-text"
# restart the API (uvicorn) in the same window, then use the buttons above''', language="powershell")
    st.caption("A smaller chat model such as llama3.2 works on weaker laptops. If Ollama stops, the app falls back to templates and keyword search and says so.")
