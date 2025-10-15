import streamlit as st
import shutil
from PIL import Image
import datetime
import json
import requests
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import re
import os
import subprocess

# === NEW: OpenAI client ===
from openai import OpenAI

# === NEW: EasyOCR (replaces Tesseract) ===
# Install at runtime if missing (best-effort)
try:
    import easyocr  # type: ignore
except ImportError:
    try:
        subprocess.run(
            ["pip", "install", "--quiet", "easyocr"],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        import easyocr  # type: ignore
    except Exception as _e:
        st.error("❌ Could not install EasyOCR in this environment.")
        easyocr = None

import numpy as np

# === CONFIGURATION ===
# Replace Together with OpenAI
openai_api_key = st.secrets.get("OPENAI_API_KEY", None)
if not openai_api_key:
    st.stop()  # Fail early with a clear error
client = OpenAI(api_key=openai_api_key)

cred_path = "credentials.json"
cred_url = "https://drive.google.com/uc?id=1toCPjw-HfrsY4ZIci3ah44sNENtNmFWm&export=download"
sheet_url = "https://docs.google.com/spreadsheets/d/1eqwvQTWila3Ax2RZt6Ld7qVg1DM5la60VmBvXedMRtk/edit#gid=1457412940"
sheet_gid = 1457412940

column_order = [
    "Expense date", "Effective month", "who",
    "amount", "what", "category", "Currency"
]

currency_options = {
    "EUR - Euro": "EUR",
    "USD - US Dollar": "USD",
    "GBP - British Pound": "GBP",
    "CAD - Canadian Dollar": "CAD",
    "CHF - Swiss Franc": "CHF",
    "JPY - Japanese Yen": "JPY",
    "AUD - Australian Dollar": "AUD",
    "CNY - Chinese Yuan": "CNY"
}

# === OpenAI receipt interpreter (replaces Together/OpenRouter) ===
def interpret_details_with_openai(parsed_text: str) -> dict:
    """
    Sends the OCR'd receipt text to OpenAI to extract structured data.
    Forces JSON output so we can parse reliably.
    """
    system = (
        "You extract structured data from receipts. "
        "Return a strict JSON object with keys: "
        "store_name (string), address (string), "
        "items (object mapping arbitrary keys to {name: string, price: string}), "
        "total (string or number), currency (string like 'USD','EUR','CAD'). "
        "Do NOT invent items or totals; if unknown, use an empty string or empty object. "
        "Do NOT wrap the JSON in markdown fences."
    )

    user = (
        "Read the receipt text below and extract fields. "
        "If multiple numeric totals appear, set 'total' to the largest plausible final charge. "
        "Keep prices as strings or plain numbers without currency symbols.\n\n"
        f"Receipt text:\n{parsed_text}"
    )

    try:
        # Use a small, fast model; change to 'gpt-4o' if you prefer
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0.2,
            # Force valid JSON
            response_format={"type": "json_object"}
        )
        content = resp.choices[0].message.content
        return json.loads(content)
    except Exception as e:
        # Bubble up a safe default so the UI doesn't crash
        st.error(f"❌ OpenAI API error: {e}")
        return {"store_name": "", "address": "", "items": {}, "total": "", "currency": ""}

def download_creds_file(url, output_path):
    try:
        response = requests.get(url, stream=True)
        if response.status_code == 200:
            with open(output_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=1024):
                    f.write(chunk)
            return output_path
        else:
            st.error("❌ Failed to download credentials.")
            return None
    except Exception as e:
        st.error(f"❌ Error downloading credentials: {e}")
        return None

def next_available_row(worksheet, start_row=18):
    column = worksheet.col_values(1)
    sub_col = column[start_row - 1:]
    row_offset = len(list(filter(None, sub_col)))
    return start_row + row_offset

def insert_expense_data(cred_path, sheet_url, sheet_gid, data, order):
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    credentials = ServiceAccountCredentials.from_json_keyfile_name(cred_path, scope)
    client_gs = gspread.authorize(credentials)
    spreadsheet = client_gs.open_by_url(sheet_url)
    worksheet = spreadsheet.get_worksheet_by_id(sheet_gid)
    row = next_available_row(worksheet)
    row_data = [data.get(col, "") for col in order]
    worksheet.insert_row(row_data, row)
    return row

def validate_submission_data(submission_data, match_amount: int):
    # Check if all required fields are filled
    missing_fields = [field for field, value in submission_data.items() if not value]
    if missing_fields:
        for field in missing_fields:
            st.error(f"❌ Please fill in '{field}'")
        return False

    # Ensure itemised total matches provided total if itemisation is shown
    if match_amount != 1:
        st.error("❌ Amounts do not match! Please ensure itemisation total equals the provided total.")
        return False

    return True

# ------------------------------
# EasyOCR helpers
# ------------------------------
@st.cache_resource(show_spinner=False)
def get_easyocr_reader():
    """
    Cache the EasyOCR Reader so we don't re-load models each rerun.
    """
    if easyocr is None:
        return None
    try:
        # Add other languages if you need them, e.g. ['en','fr','de']
        return easyocr.Reader(['en'], gpu=False)
    except Exception as e:
        st.error(f"❌ EasyOCR initialization failed: {e}")
        return None

def ocr_image_with_easyocr(pil_img: Image.Image) -> str:
    """
    Run EasyOCR on a PIL image and return a single text blob.
    """
    reader = get_easyocr_reader()
    if reader is None:
        return ""
    try:
        np_img = np.array(pil_img.convert("RGB"))
        results = reader.readtext(np_img, detail=1, paragraph=False)
        # results is a list of (bbox, text, confidence)
        lines = [r[1] for r in results if isinstance(r, (list, tuple)) and len(r) >= 2]
        return "\n".join(lines).strip()
    except Exception as e:
        st.error(f"❌ EasyOCR error: {e}")
        return ""

# ------------------------------
# Streamlit App
# ------------------------------
st.set_page_config(page_title="Receipt Parser", page_icon="📸", layout="centered")
st.title("📸 Receipt Parser and Logger (OpenAI)")

# (Removed Tesseract apt-get install block)

mode = "AI-assisted"
parsed_text = ""
data = {"items": {}, "total": 0.0}

input_method = st.radio("Provide the receipt via", ["Upload a file", "Use camera", "Manual Entry"])
uploaded_file = captured_image = None

if input_method != "Manual Entry":
    with st.expander("📂 File Upload", expanded=True):
        if input_method == "Upload a file":
            uploaded_file = st.file_uploader("Upload receipt image", type=["png", "jpg", "jpeg"])
        elif input_method == "Use camera":
            captured_image = st.camera_input("Take a picture")

        if uploaded_file or captured_image:
            image_file = uploaded_file if uploaded_file else captured_image
            image = Image.open(image_file)
            st.image(image, caption="Receipt", use_container_width=True)

            # Only OCR + extract once per session to avoid re-billing
            fresh_parse = "parsed_text" not in st.session_state
            if fresh_parse:
                with st.spinner("🔎 Extracting text with OCR (EasyOCR)..."):
                    parsed_text = ocr_image_with_easyocr(image)
                    st.session_state["parsed_text"] = parsed_text

                with st.spinner("🧠 Structuring with OpenAI..."):
                    extracted = interpret_details_with_openai(parsed_text)
                    st.session_state["data"] = extracted if isinstance(extracted, dict) else {"items": {}, "total": 0.0}
                    st.session_state["model_output"] = json.dumps(st.session_state["data"], indent=2)

                st.success("✅ Receipt data extracted successfully!")
            else:
                parsed_text = st.session_state["parsed_text"]
                st.success("✅ Receipt data extracted successfully!")
                data = st.session_state.get("data", {"items": {}, "total": 0.0})

# === Shared Fields ===
with st.expander("🧾 Receipt Details", expanded=True):
    selected_person = st.pills(
        "Who paid?",
        options=["Julie", "Emery", "➕ Other"],
        help="Choose the person who made the purchase",
        selection_mode="single"
    )
    if selected_person == "➕ Other":
        selected_person = st.text_input("Enter custom name")

    category_options = st.pills(
        "Category",
        options=["🍽️ Meals", "🥫 Groceries", "✈️ Vacation Travel", "🛌 Vacation Accomodation", "🖇️ Office Supplies", "🧾 Miscellaneous", "➕ Other"],
        help="Select or enter a category",
        selection_mode="single"
    )
    category = st.text_input("Enter custom category") if category_options == "➕ Other" else category_options

    # Prefer OpenAI total/currency if present
    extracted_total = 0.0
    extracted_currency = ""
    if isinstance(st.session_state.get("data"), dict):
        try:
            extracted_total = float(str(st.session_state["data"].get("total", 0) or 0).replace(",", ""))
        except Exception:
            extracted_total = 0.0
        extracted_currency = st.session_state["data"].get("currency", "")

    try:
        total = st.number_input("Total Amount", value=float(extracted_total))
    except:
        total = st.number_input("Total Amount", value=0.0)

    purchase_date = st.date_input("Date of Purchase", datetime.date.today())

    today = datetime.date.today()
    col1, col2 = st.columns([2, 1])
    with col1:
        selected_month = st.selectbox("Effective Month", [
            "January", "February", "March", "April", "May", "June",
            "July", "August", "September", "October", "November", "December"
        ], index=today.month - 1)
    with col2:
        selected_year = st.selectbox("Effective Year", list(range(today.year - 5, today.year + 6)), index=5)
    effective_month = f"{selected_month} {selected_year}"

    currency_options_map = {
        "EUR - Euro": "EUR",
        "USD - US Dollar": "USD",
        "GBP - British Pound": "GBP",
        "CAD - Canadian Dollar": "CAD",
        "CHF - Swiss Franc": "CHF",
        "JPY - Japanese Yen": "JPY",
        "AUD - Australian Dollar": "AUD",
        "CNY - Chinese Yuan": "CNY"
    }
    default_currency_key = next((k for k, v in currency_options_map.items() if v == extracted_currency), "CAD - Canadian Dollar")
    selected_currency = st.pills(
        "Currency",
        options=list(currency_options_map.keys()),
        help="Choose the currency of the purchase",
        selection_mode="single"
    ) or default_currency_key

# === Itemisation ===
if "show_itemisation" not in st.session_state:
    st.session_state["show_itemisation"] = False
if "items" not in st.session_state:
    st.session_state["items"] = []

st.markdown("---")

col1, col2 , col3 = st.columns(3)
with col1:
    if st.button("➕ Add Itemisation"):
        st.session_state["show_itemisation"] = True
with col2:
    if st.button("🗑️ Remove Itemisation"):
        st.session_state["show_itemisation"] = False
        st.session_state["items"] = []

match_amount = 1  # default

if st.session_state["show_itemisation"]:
    with st.expander("🛒 Itemised Purchases", expanded=True):
        extracted_items = {}
        if isinstance(st.session_state.get("data"), dict):
            extracted_items = st.session_state["data"].get("items", {}) or {}

        def safe_float(value):
            try:
                return float("".join(c for c in str(value) if c.isdigit() or c == "." or c == "-"))
            except:
                return 0.0

        # only populate once
        if not st.session_state["items"]:
            if isinstance(extracted_items, dict) and len(extracted_items) > 0:
                try:
                    st.session_state["items"] = [
                        ( (item.get("name") if isinstance(item, dict) else str(item)), safe_float((item.get("price") if isinstance(item, dict) else 0.0)) )
                        for item in extracted_items.values()
                    ]
                except Exception as e:
                    st.warning(f"⚠️ Could not parse extracted items: {e}")
                    st.session_state["items"] = [("Item 1", 0.0)]
            else:
                st.session_state["items"] = [("Item 1", 0.0)]

        # Add / Remove buttons
        c1, c2, c3 = st.columns([1, 1, 1])
        with c1:
            if st.button("➕ Add Item"):
                st.session_state["items"].append(("", 0.0))
        with c2:
            if st.button("➖ Remove Last Item") and st.session_state["items"]:
                st.session_state["items"].pop()

        # Editable Inputs with delete buttons
        itemised_total = 0.0
        new_items = []

        for i in range(len(st.session_state["items"])):
            item_name, item_price = st.session_state["items"][i]
            c1, c2, c3 = st.columns([3, 1, 0.5], vertical_alignment="bottom")
            new_name = c1.text_input(f"Item {i+1}", value=item_name, key=f"item_{i}")
            new_price = c2.number_input("", value=float(item_price), key=f"price_{i}", format="%.2f")
            delete = c3.button("🗑️", key=f"delete_{i}")
