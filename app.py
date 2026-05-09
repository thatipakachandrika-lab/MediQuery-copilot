import streamlit as st
import pandas as pd
from langchain_community.llms import Ollama

# -----------------------
# Load Data
# -----------------------
data = pd.read_csv("healthcare_dataset.csv")
data = data.drop_duplicates().reset_index(drop=True)
data['Name'] = data['Name'].str.lower().str.title()

# Feature Engineering
data["Date of Admission"] = pd.to_datetime(data["Date of Admission"])
data["Discharge Date"] = pd.to_datetime(data["Discharge Date"])
data["Length of Stay"] = (data["Discharge Date"] - data["Date of Admission"]).dt.days

# -----------------------
# LLM
# -----------------------
llm = Ollama(model="phi3")

st.set_page_config(
    page_title="Healthcare Data AI Assistant",
    page_icon="🏥",
    layout="wide"
)
st.markdown("""
<style>

/* Background */
[data-testid="stAppViewContainer"] {
    background-color: #ffffff;
}

/* Sidebar */
section[data-testid="stSidebar"] {
    background-color: #ffffff;
    border-right: 1px solid #e5e7eb;
}

/* Main container */
.block-container {
    padding-top: 2rem;
    padding-bottom: 2rem;
    max-width: 900px;
}

/* Chat bubbles */
.stChatMessage {
    background-color: #fafafa;
    padding: 14px;
    border-radius: 14px;
    margin-bottom: 12px;
    box-shadow: 0 4px 12px rgba(0,0,0,0.08);
}

/* User message highlight */
[data-testid="stChatMessageContent"] p {
    font-size: 16px;
}

/* Input box */
textarea {
    border-radius: 12px !important;
    border: 1px solid #d1d5db !important;
}

/* Tables */
.stDataFrame {
    border-radius: 12px;
    overflow: hidden;
}

/* Titles */
h1 {
    font-weight: 700;
}

</style>
""", unsafe_allow_html=True)

st.title("🏥 MediQuery Copilot")
st.caption("Ask questions and get insights.")

with st.sidebar:
    st.header("About")
    st.write(
        "This app uses a local LLM with pandas to answer questions about healthcare data."
    )

    st.header("Example Questions")
    st.write("""
    - average billing amount
    - who stayed longest
    - top 5 hospitals by billing
    - billing by insurance provider
    - how admission type varies with medical condition
    """)

    st.header("Dataset")
    st.write(f"Rows: {data.shape[0]}")
    st.write(f"Columns: {data.shape[1]}")

# -----------------------
# Generate Code (FIXED)
# -----------------------
def generate_code(question):
    columns = list(data.columns)

    prompt = f"""
You are a system that converts questions into VALID pandas code.

DataFrame name: df

Columns:
{columns}

CRITICAL RULES:
- Output ONLY ONE LINE of Python code
- NO explanation
- NO markdown
- MUST start with df
- MUST be executable
- NEVER return text

PATTERNS YOU MUST FOLLOW:

1. Average:
df['column'].mean()

2. Max:
df['column'].max()

3. Min:
df['column'].min()

4. Count / most:
df['column'].value_counts()

5. Group by:
df.groupby('column')['target'].mean()
df.groupby('column').size()

6. Top N:
df.groupby('column')['target'].sum().sort_values(ascending=False).head(5)

7. Row with max:
df.loc[df['column'].idxmax()]

8. Row with min:
df.loc[df['column'].idxmin()]

IMPORTANT MAPPINGS:

- top 5 hospitals by billing
→ df.groupby('Hospital')['Billing Amount'].sum().sort_values(ascending=False).head(5)

- who stayed more days
→ df.loc[df['Length of Stay'].idxmax()]

- who has lowest billing amount
→ df.loc[df['Billing Amount'].idxmin()]

- patient with longest stay
→ df.loc[df['Length of Stay'].idxmax()]

- how X varies with Y
→ df.groupby(['X','Y']).size()

- billing by insurance provider
→ df.groupby('Insurance Provider')['Billing Amount'].mean()

Question: {question}
"""
    return llm.invoke(prompt)

# -----------------------
# Validate Generated Code
# -----------------------
def validate_generated_code(code, df):
    try:
        code = code.replace("```python", "").replace("```", "").strip()
        lines = code.split("\n")

        df_lines = [line.strip() for line in lines if line.strip().startswith("df")]

        if not df_lines:
            return False, "Sorry, I couldn't understand that query. Try rephrasing."

        clean_code = df_lines[-1]

        blocked_terms = ["import", "open(", "exec(", "eval(", "os.", "sys.", "subprocess", "__"]

        for term in blocked_terms:
            if term in clean_code:
                return False, "Unsafe query blocked."

        column_used = any(col in clean_code for col in df.columns)

        if not column_used:
            return False, "I couldn't match the question to a valid dataset column."

        return True, clean_code

    except Exception:
        return False, "Validation failed. Try rephrasing."

# -----------------------
# Safe Execution
# -----------------------
def safe_execute(code, df):
    try:
        # Clean code
        code = code.replace("```python", "").replace("```", "").strip()

        # If multi-line, keep full code (not just last line)
        lines = code.split("\n")

        # Try to find a line that starts with df
        df_lines = [l.strip() for l in lines if l.strip().startswith("df")]

        if not df_lines:
            return "Invalid query"

        # Take the LAST valid df line
        code = df_lines[-1]

        # Execute safely
        local_vars = {"df": df}
        result = eval(code, {"__builtins__": {}}, local_vars)

        return result

    except Exception as e:
        return f"Execution error: {e}"

# -----------------------
# Chat Memory
# -----------------------
if "messages" not in st.session_state:
    st.session_state.messages = []

# Display chat history
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):

        if msg["role"] == "user":
            st.write(msg["content"])

        else:
            result = msg["result"]

            if isinstance(result, (pd.Series, pd.DataFrame)):
                st.dataframe(result)

                if len(result) <= 15:
                    try:
                        st.bar_chart(result)
                    except:
                        pass
                else:
                    st.write("Too many categories to plot.")
            else:
                st.write(result)

# -----------------------
# Input Section (Centered)
# -----------------------
st.markdown("---")
query = st.chat_input("Ask your question...")

# -----------------------
# Handle Query
# -----------------------
if query:
    st.session_state.messages.append({"role": "user", "content": query})

    with st.chat_message("user"):
        st.write(query)

    df = data.copy()

    try:
        code = generate_code(query)

        is_valid, validated_code_or_message = validate_generated_code(code, df)

        if is_valid:
            result = safe_execute(validated_code_or_message, df)
        else:
            result = validated_code_or_message

        st.session_state.messages.append({
            "role": "assistant",
            "result": result
        })

        with st.chat_message("assistant"):
            if isinstance(result, (pd.Series, pd.DataFrame)):
                st.dataframe(result)

                if len(result) <= 15:
                    try:
                        st.bar_chart(result)
                    except:
                        pass
                else:
                    st.write("Too many categories to plot.")
            else:
                st.write(result)

    except Exception as e:
        with st.chat_message("assistant"):
            st.write(f"Something went wrong: {e}")