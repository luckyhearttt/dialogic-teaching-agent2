import streamlit as st
import requests
import json
import time

# ==========================================
# 1. 基础配置
# ==========================================

st.set_page_config(
    page_title="AI Teaching Assistant", 
    page_icon="🎓", 
    layout="centered",
    initial_sidebar_state="expanded"
)

hide_st_style = """
            <style>
            #MainMenu {visibility: hidden;}
            footer {visibility: hidden;}
            .stDeployButton {display: none;}
            </style>
            """
st.markdown(hide_st_style, unsafe_allow_html=True)

try:
    COZE_API_TOKEN = st.secrets["coze"]["api_token"]
    BOT_ID = st.secrets["coze"]["bot_id"]
    CLASS_PASSWORD = st.secrets["auth"]["class_password"]
    SURVEY_1_LINK = st.secrets["links"]["survey_1"]
    SURVEY_2_LINK = st.secrets["links"]["survey_2"]
    MOODLE_LINK = st.secrets["links"]["moodle"]
except:
    st.error("⚠️ Secrets not configured. Please contact your instructor.")
    st.stop()

# ✏️【删除】不再需要 SHEET_NAME、Google Sheet 相关的 import 和配置

WELCOME_MESSAGE = "Hi! I'm your AI assistant. You can ask me about anything, or let me help you brainstorm and refine your plan. Let's get started!"

# ==========================================
# 2. 数据库逻辑
# ==========================================

# ✏️【全部删除】不再需要 get_google_sheet、save_to_sheet、load_history_from_sheet
#   - 聊天记录存在 st.session_state 里（刷新会清空，但 Coze 后台有完整日志）
#   - 删掉后每轮对话少了 1-2 秒延迟 + 两次可能失败的网络请求

# ==========================================
# 3. AI 核心逻辑
# ==========================================

def stream_coze_response(query, user_name):
    """
    流式生成器：每收到一小块文字就立刻 yield 出去，
    让 st.write_stream() 实时显示打字机效果。
    """
    url = "https://api.coze.cn/v3/chat"
    headers = {"Authorization": f"Bearer {COZE_API_TOKEN}", "Content-Type": "application/json"}
    safe_user_id = f"stu_{user_name}".replace(" ", "_")
    
    context_messages = []
    if "messages" in st.session_state:
        recent = st.session_state.messages[-14:]  # 最近7轮对话作为上下文
        for msg in recent:
            context_messages.append({
                "role": msg["role"],
                "content": msg["content"],
                "content_type": "text"
            })
    
    context_messages.append({
        "role": "user",
        "content": query,
        "content_type": "text"
    })
    
    data = {
        "bot_id": BOT_ID, 
        "user_id": safe_user_id, 
        "stream": True,
        "auto_save_history": True,  # ✏️【改回 True】现在 Coze 后台是唯一的数据记录源，必须开启
        "additional_messages": context_messages
    }
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = requests.post(url, headers=headers, json=data, stream=True, timeout=90)
            
            if response.status_code == 429:
                wait_time = (attempt + 1) * 3
                time.sleep(wait_time)
                continue
            
            current_event = None
            has_content = False
            
            for line in response.iter_lines():
                if not line: continue
                decoded_line = line.decode('utf-8')
                
                if decoded_line.startswith("event:"):
                    current_event = decoded_line[6:].strip()
                    continue
                
                if decoded_line.startswith("data:"):
                    json_str = decoded_line[5:].strip()
                    if json_str == "[DONE]": continue
                    
                    if current_event == "conversation.message.delta":
                        try:
                            chunk = json.loads(json_str)
                            if chunk.get('type') == 'answer':
                                text_piece = chunk.get('content', '')
                                if text_piece:
                                    has_content = True
                                    yield text_piece
                        except:
                            pass
                    
                    current_event = None
            
            if not has_content:
                yield "AI is thinking but didn't return a response. Please try again."
            return
            
        except requests.exceptions.Timeout:
            if attempt < max_retries - 1:
                time.sleep(2)
                continue
            yield "⏳ Response timed out. Please try sending your message again."
            return
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(2)
                continue
            yield f"Connection error. Please try again. ({str(e)})"
            return
    
    yield "⏳ AI is currently busy. Please wait a moment and try again."

# ==========================================
# 4. 知识库内容（不动）
# ==========================================

def render_knowledge_base():
    st.markdown("## 📖 Accountable Talk & Dialogic Teaching Strategies")
    st.markdown("Use this as a reference while designing your lesson plan.")
    st.divider()

    st.markdown("### 1. APT: Four Goals & Eight Talk Moves")

    with st.expander("🎯 Goal 1: Help individual students share, expand, and clarify their thinking (Elaborating)", expanded=False):
        st.markdown("""
**Move 1 — "Say More"**  
Ask students to elaborate on a brief, vague, or unclear statement.

> *"Can you say more about that?"*  
> *"What do you mean by that?"*  
> *"Can you give an example?"*

---

**Move 2 — "Revoice"**  
The teacher restates a student's reasoning and gives them a chance to confirm or correct.

> *"So let me see if I understand — you're saying … Is that right?"*  
> *"In other words, you're suggesting …?"*
""")

    with st.expander("🎯 Goal 2: Help students deepen their reasoning (Reasoning)", expanded=False):
        st.markdown("""
**Move 3 — "Press for Reasoning"**  
Ask students to explain the thinking behind their answer.

> *"Why do you think that?"*  
> *"What's your evidence?"*  
> *"How did you arrive at that answer?"*

---

**Move 4 — "Challenge"**  
Offer a counter-example or alternative perspective to test and deepen reasoning.

> *"Is that always the case?"*  
> *"What if the denominator were 0?"*  
> *"Can you think of a case where that wouldn't work?"*  
> *"What would someone who disagrees say?"*
""")

    with st.expander("🎯 Goal 3: Help students listen carefully to one another (Listening)", expanded=False):
        st.markdown("""
**Move 5 — "Restate"**  
Prompt students to repeat or paraphrase what someone else said.

> *"Who can repeat what Javon just said, in your own words?"*  
> *"What did your partner say?"*
""")

    with st.expander("🎯 Goal 4: Help students think with others (Thinking with Others)", expanded=False):
        st.markdown("""
**Move 6 — "Agree / Disagree"**  
Ask students to take a position on someone else's idea and explain why.

> *"Do you agree or disagree? Why?"*  
> *"What do you think about what she just said?"*  
> *"Thumbs up if you agree, thumbs down if you disagree."*

---

**Move 7 — "Add On"**  
Invite students to build on or extend a classmate's idea.

> *"Who can add on to what Jamal said?"*  
> *"Can anyone take that idea a step further?"*

---

**Move 8 — "Explain Other"**  
Ask a student to explain another student's reasoning.

> *"Who can explain what Aisha meant?"*  
> *"Why do you think he said that?"*  
> *"Can you explain her reasoning in your own words?"*
""")

    st.divider()

    st.markdown("### 2. Accountable Talk: Three Dimensions of Accountability")
    st.info("""
**Accountable Talk** is a core practice framework developed by the Institute for Learning at the University of Pittsburgh. It requires classroom talk to be accountable in three dimensions:
""")

    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown("""
**🤝 To the Community**
- Listen carefully, not just wait to speak
- Paraphrase & build on each other's ideas
- Challenge ideas, not people
""")
    with col2:
        st.markdown("""
**📚 To Accurate Knowledge**
- Be specific and accurate
- Expect & answer challenging questions
- Use verifiable sources
""")
    with col3:
        st.markdown("""
**🧠 To Rigorous Thinking**
- Push for quality of claims & arguments
- Evidence must be sufficient, credible, relevant
- Use data, examples, analogies
""")

    st.divider()

    st.markdown("### 3. Talk Moves as Tools, Not Scripts: Five Principles")

    principles = [
        ("🔧 Tools are designed to solve problems",
         "A tool only makes sense in light of a specific problem or purpose, and in relation to other tools in the toolkit."),
        ("🎯 Understanding a tool requires knowing its purpose",
         "No tool — not even a hammer — is transparent in its use. Learning to use a tool means learning the materials it acts upon."),
        ("📈 Some tools are easier to pick up than others",
         "For example, *Wait Time* is one of the most researched talk moves, yet it is notoriously difficult to master."),
        ("🔗 Tools must be used in strategic sequence",
         "This takes practice, attention to the materials, and understanding of the larger purpose."),
        ("🪪 Tools belong to an identity",
         "Asking teachers to adopt new tools is, in a sense, asking them to take on a new identity — one that embodies particular values and beliefs.")
    ]

    for i, (title, desc) in enumerate(principles, 1):
        st.markdown(f"**{i}. {title}**")
        st.markdown(f"   {desc}")
        if i < len(principles):
            st.markdown("")

# ==========================================
# 4b. 任务步骤页面（不动）
# ==========================================

def render_task_page():
    st.markdown("## 📝 Your Task: Step by Step")
    st.markdown("Follow these three steps to complete today's activity.")
    st.divider()

    with st.expander("**Step 1: Pre-Survey** (Complete this first!)", expanded=True):
        st.markdown("""
Before starting the task, please complete a short survey about your AI usage and dialogic teaching knowledge.

⏱️ Estimated time: **5-7 minutes**
""")
        st.markdown(f"""
<a href="{SURVEY_1_LINK}" target="_blank">
    <button style="
        width: 100%;
        background-color: #4CAF50;
        color: white;
        border: none;
        padding: 12px;
        border-radius: 5px;
        cursor: pointer;
        font-weight: bold;
        font-size: 16px;
    ">
    📋 Open Pre-Survey
    </button>
</a>
""", unsafe_allow_html=True)

    st.markdown("")

    with st.expander("**Step 2: Design Task with AI** (Main activity — 40 min)", expanded=True):
        st.markdown("""
Design a **5–10 minute lesson plan** for a classroom activity you may teach in the future. Please use **dialogic teaching** in your design.

You may design and include the following:

1. 📋 **Lesson plan** — What will you teach? What learning objectives would you like to achieve?
2. 📝 **Conduct plan** — How do you plan to conduct the lesson to achieve these objectives?
3. 💬 **A simulated teacher-student dialogue** — Show what your dialogic teaching might look like

---

💡 Consider real classroom complexity — students may be silent, give partial answers, or surprise you.

💡 Use AI however you like — brainstorm, get feedback, generate content, discuss ideas, etc.

⏱️ **Time: 40 minutes.**

---

When you're done, click the button below to submit your work on the Moodle Discussion Forum.
""")
        st.markdown(f"""
<a href="{MOODLE_LINK}" target="_blank">
    <button style="
        width: 100%;
        background-color: #ff4b4b;
        color: white;
        border: none;
        padding: 12px;
        border-radius: 5px;
        cursor: pointer;
        font-weight: bold;
        font-size: 16px;
    ">
    📤 Submit to Moodle Discussion Forum
    </button>
</a>
""", unsafe_allow_html=True)

    st.markdown("")

    with st.expander("**Step 3: Post-Survey & Reflection** (After finishing the task)", expanded=True):
        st.markdown("""
After completing your design task, please take a few minutes to reflect on your AI experience and fill in a short survey.

⏱️ Estimated time: **5-7 minutes**
""")
        st.markdown(f"""
<a href="{SURVEY_2_LINK}" target="_blank">
    <button style="
        width: 100%;
        background-color: #2196F3;
        color: white;
        border: none;
        padding: 12px;
        border-radius: 5px;
        cursor: pointer;
        font-weight: bold;
        font-size: 16px;
    ">
    📝 Open Post-Survey
    </button>
</a>
""", unsafe_allow_html=True)

# ==========================================
# 5. 界面逻辑
# ==========================================

# ✏️【删除】不再需要 db_conn
if "current_page" not in st.session_state:
    st.session_state.current_page = "chat"

if "is_processing" not in st.session_state:
    st.session_state.is_processing = False

# --- 登录页 ---
if 'user_name' not in st.session_state:
    st.markdown("<br><br>", unsafe_allow_html=True)
    st.markdown("<h1 style='text-align: center;'>🎓 Connect to Your AI Assistant</h1>", unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        st.info("👋 Welcome! Enter your name and class code to begin.")
        name_input = st.text_input("Your Name:", key="login_name")
        pwd_input = st.text_input("Class Code:", type="password")
        
        if st.button("🚀 Start", use_container_width=True):
            if name_input and pwd_input == CLASS_PASSWORD:
                clean_name = name_input.strip()
                st.session_state.user_name = clean_name
                # ✏️【简化】不再从 Sheet 加载历史，直接初始化空对话
                st.session_state.messages = [{"role": "assistant", "content": WELCOME_MESSAGE}]
                st.rerun()
            elif pwd_input != CLASS_PASSWORD:
                st.error("🚫 Incorrect class code.")
            else:
                st.error("⚠️ Please enter your name.")
    st.stop()

# --- 侧边栏 ---

with st.sidebar:
    st.markdown(f"**👤 Student: {st.session_state.user_name}**")
    st.divider()

    st.markdown("**📌 Navigation**")
    
    if st.button("💬 AI Chat", use_container_width=True, 
                 type="primary" if st.session_state.current_page == "chat" else "secondary"):
        st.session_state.current_page = "chat"
        st.rerun()
    
    if st.button("📝 Task Steps & Links", use_container_width=True,
                 type="primary" if st.session_state.current_page == "task" else "secondary"):
        st.session_state.current_page = "task"
        st.rerun()
    
    if st.button("📖 Dialogic Teaching Reference", use_container_width=True,
                 type="primary" if st.session_state.current_page == "reference" else "secondary"):
        st.session_state.current_page = "reference"
        st.rerun()

    st.divider()

    st.warning("""
**💡 Tips**
1. **General AI** — This AI is not a dialogic teaching expert. Give it context when asking.
2. **Keep your name** — Use the same link & name throughout.
3. **Be patient** — AI may take a few seconds to start responding. Don't refresh repeatedly.
""")

    st.divider()
    if st.button("Log Out"):
        st.session_state.clear()
        st.rerun()

# --- 主内容区 ---

if st.session_state.current_page == "chat":
    st.markdown("## 💬 AI Chat")
    st.caption("Ask me anything — I'm here to help you with your teaching design.")
    st.divider()
    
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # ✏️【核心改动】流式输出 + 去掉 Google Sheet 写入
    if prompt := st.chat_input("Type your message here..."):
        
        if st.session_state.is_processing:
            st.toast("⏳ Please wait, AI is still thinking...")
            st.stop()
        
        st.session_state.is_processing = True
        
        # 1. 显示用户输入
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        # ✏️【删除】不再 save_to_sheet

        # 2. 流式显示AI回复（打字机效果）
        with st.chat_message("assistant"):
            response = st.write_stream(stream_coze_response(prompt, st.session_state.user_name))
        
        # 3. 保存到 session（仅内存）
        st.session_state.messages.append({"role": "assistant", "content": response})
        # ✏️【删除】不再 save_to_sheet
        
        # 4. 重置
        st.session_state.is_processing = False
        st.rerun()

elif st.session_state.current_page == "task":
    render_task_page()

elif st.session_state.current_page == "reference":
    render_knowledge_base()


