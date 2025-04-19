import streamlit as st
from PIL import Image
import pytesseract
import datetime
#from io import BytesIO
#from openai import OpenAI
#import os
import json
import requests
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import ast
import re

# Set up Tesseract path (adjust this to your system)
#pytesseract.pytesseract.tesseract_cmd = r'C:\Users\USER\AppData\Local\Tesseract-OCR\tesseract.exe'

# === CONFIGURATION ===
together_api_key = st.secrets["TOGETHER_API_KEY"]

cred_path = "credentials.json"
cred_url = "https://drive.google.com/uc?id=1toCPjw-HfrsY4ZIci3ah44sNENtNmFWm&export=download"
sheet_url = "https://docs.google.com/spreadsheets/d/1eqwvQTWila3Ax2RZt6Ld7qVg1DM5la60VmBvXedMRtk/edit#gid=1457412940"
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

# === FUNCTIONS ===
def interpret_details(parsed_text):
    prompt = (
        "You are an expert on reading receipts. "
        "Please classify the following receipt text into a JSON-style dictionary with these fields:\n"
        "1. 'store_name'\n"
        "2. 'address'\n"
        "3. 'items': dictionary of items and prices\n"
        "4. 'total': total amount\n\n"
        f"Receipt text:\n{parsed_text}"
    )

    client = OpenAI(api_key=openai_api_key)

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "You are an assistant that extracts structured data from receipts."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.2
    )

    return response.choices[0].message.content

def interpret_details_with_openrouter(parsed_text):


    url = "https://api.together.xyz/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {together_api_key}"
    }

    prompt = (
        "You are an expert at reading receipts. DO NOT perform any calculations. The input may be incomplete.\n\n"
        "Please extract the following information from the receipt text and return it as a JSON-style dictionary:\n"
        "1. 'store_name': Name of the store\n"
        "2. 'address': Store address\n"
        "3. 'items': A dictionary of item entries and their prices. Use the following format:\n"
        '   "items": {\n'
        '       "item1": { "name": "Sub Total", "price": "25.23" },\n'
        '       "item2": { "name": "USD$ 29.01", "price": "29.01" }\n'
        '   }\n'
        "4. 'total': The highest value from the item prices\n"
        "5. 'currency': The currency used in the receipt (e.g., USD, EUR, etc.)\n\n"
        f"Receipt text:\n{parsed_text}"
    )

    payload = {
        "model": "mistralai/Mistral-7B-Instruct-v0.1",  # You can switch to mistralai/Mistral-7B-Instruct or other free model
        "messages": [
            {"role": "system", "content": "You are an assistant that extracts structured data from receipts."},
            {"role": "user", "content": prompt}
        ]
    }

    try:
        response = requests.post(url, headers=headers, json=payload)
        result = response.json()
        model_output=result["choices"][0]["message"]["content"]
        # Remove code fences if present (like ```json ... ```)
        return re.sub(r"```(?:json)?", "", model_output).strip("` \n")
    except Exception as e:
        st.error(f"❌ API request failed or response error: {e}")
        return "{}"

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
    client = gspread.authorize(credentials)
    spreadsheet = client.open_by_url(sheet_url)
    worksheet = spreadsheet.get_worksheet_by_id(sheet_gid)
    row = next_available_row(worksheet)
    row_data = [data[col] for col in order]
    worksheet.insert_row(row_data, row)
    return row
def validate_submission_data(submission_data):
    # Check if all required fields are filled
    missing_fields = [field for field, value in submission_data.items() if not value]

    if missing_fields:
        for field in missing_fields:
            st.error(f"❌ Please fill in '{field}'")
        return False

    # Check if match_amount is 1 (this assumes match_amount is a variable or value available in your code)
    if match_amount != 1:
        st.error("❌ Amounts do not match! Please ensure match_amount is 1.")
        return False

    return True

# ------------------------------
# Streamlit App
# ------------------------------
st.set_page_config(page_title="Receipt Parser", page_icon="📸", layout="centered")
st.title("📸 Receipt Parser and Logger")

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
            if "parsed_text" not in st.session_state:
                image_file = uploaded_file if uploaded_file else captured_image
                image = Image.open(image_file)
                st.image(image, caption="Receipt", use_container_width=True)

                with st.spinner("Extracting text..."):
                    parsed_text = pytesseract.image_to_string(image, lang='eng+fra')
                    st.session_state["parsed_text"] = parsed_text

                    try:
                        model_output = interpret_details_with_openrouter(parsed_text)
                        st.session_state["model_output"] = model_output

                        try:
                            st.session_state["data"] = json.loads(model_output)
                        except json.JSONDecodeError:
                            st.session_state["data"] = ast.literal_eval(model_output)

                        st.success("✅ Receipt data extracted successfully!")
                    except Exception as e:
                        st.warning("Could not interpret receipt. You can enter data manually.")
                        st.error(f"❌ Error: {e}")
                        st.session_state["data"] = {"items": {}, "total": 0.0}
            else:
                st.image(Image.open(uploaded_file if uploaded_file else captured_image), caption="Receipt", use_container_width=True)
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

    try:
        total = st.number_input("Total Amount", value=float(data.get("total", 0.0)))
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
    #st.caption(f"📅 Effective Month: **{effective_month}**")
    
    selected_currency = st.pills(
        "Currency",
        options=list(currency_options.keys()),
        help="Choose the is the currency of the purchase",
        selection_mode="single"
    )

# === Itemisation ===
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

if st.session_state["show_itemisation"]:
    with st.expander("🛒 Itemised Purchases", expanded=True):  
        extracted_items = data.get("items", {})

        def safe_float(value):
            try:
                return float("".join(c for c in str(value) if c.isdigit() or c == "." or c == "-"))
            except:
                return 0.0

        # Only populate default values once if the item list is empty
        if not st.session_state["items"]:
            if isinstance(extracted_items, dict) and len(extracted_items) > 0:
                try:
                    st.session_state["items"] = [
                        (item.get("name", f"Item {i+1}"), safe_float(item.get("price", 0.0)))
                        for i, item in enumerate(extracted_items.values())
                    ]
                except Exception as e:
                    st.warning(f"⚠️ Could not parse extracted items: {e}")
                    st.session_state["items"] = [("Laptop", 1200.0), ("Keyboard", 50.0)]
            else:
                st.session_state["items"] = [("Laptop", 1200.0), ("Keyboard", 50.0)]

        # Add / Remove buttons
        col1, col2, col3 = st.columns([1, 1, 1])
        with col1:
            if st.button("➕ Add Item"):
                st.session_state["items"].append(("", 0.0))
        with col2:
            if st.button("➖ Remove Last Item") and st.session_state["items"]:
                st.session_state["items"].pop()

        # Editable Inputs with delete buttons
        itemised_total = 0.0
        new_items = []

        for i in range(len(st.session_state["items"])):
            item_name, item_price = st.session_state["items"][i]
            col1, col2, col3 = st.columns([3, 1, 0.5],vertical_alignment="bottom")
            new_name = col1.text_input(f"Item {i+1}", value=item_name, key=f"item_{i}")
            new_price = col2.number_input("", value=item_price, key=f"price_{i}", format="%.2f")
            delete = col3.button("🗑️", key=f"delete_{i}")

            if not delete:
                new_items.append((new_name, new_price))
                itemised_total += new_price

        # Update item list after processing deletes
        st.session_state["items"] = new_items

        # Total check
        if st.session_state["show_itemisation"]:
            if itemised_total != total:
                st.error(f"❌ The total amount from the itemisation ({itemised_total:.2f}) does not match the provided total ({total:.2f}).")
                match_amount = 0
            else:
                st.success(f"✅ The itemisation total matches the provided total: {itemised_total:.2f}")
                match_amount = 1
        else:
            match_amount = 1


# === Submission ===
st.markdown("---")
if st.button("✅ Submit"):

    
        what_text = ", ".join([f"{k} ({v}€)" for k, v in st.session_state["items"]])
        expense_data = {
            "Expense date": str(purchase_date),
            "Effective month": effective_month,
            "who": selected_person,
            "amount": str(total),
            "what": what_text,
            "category": category,
            "Currency": selected_currency
        }
        
        submission_data = {
            "person": selected_person,
            "category": category,
            "total": total,
            "purchase_date": str(purchase_date),
            "effective_date": str(effective_month),
        }
        
        if not st.session_state["show_itemisation"]:
            match_amount = 1
        
        if validate_submission_data(submission_data):
        
            # Only include 'items' if itemisation was done
            if st.session_state.get("show_itemisation", False):
                submission_data["items"] = dict(st.session_state["items"])
                

            # Upload to Google Sheets
            with st.spinner("📤 Uploading to Google Sheets..."):
                if download_creds_file(cred_url, cred_path):
                    try:
                        row_num = insert_expense_data(cred_path, sheet_url, sheet_gid, expense_data, column_order)
                        st.success(f"✅ Uploaded to Google Sheets at row {row_num}.")
                    except Exception as e:
                        st.error(f"❌ Error uploading to Google Sheets: {e}")

                st.json(submission_data)
        else:
            st.warning("Please fill in all required fields and ensure itemisation matches")
