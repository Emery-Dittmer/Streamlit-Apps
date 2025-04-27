import streamlit as st
from PIL import Image
import pytesseract
import datetime
from io import BytesIO
from openai import OpenAI
import os

# Setup OpenAI (make sure to set your API key securely)
openai_api_key = os.getenv("OPENAI_API_KEY")

# Function to extract receipt data using GPT

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
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are an assistant that extracts structured data from receipts."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.2
    )

    return response.choices[0].message.content

# Streamlit UI
st.title("📸 Receipt Parser and Logger")

uploaded_file = st.file_uploader("Upload a receipt image", type=["png", "jpg", "jpeg"])
captured_image = st.camera_input("Or take a picture")

if uploaded_file or captured_image:
    image_file = uploaded_file if uploaded_file else captured_image
    image = Image.open(image_file)
    st.image(image, caption="Uploaded Receipt", use_column_width=True)

    with st.spinner("Extracting text..."):
        parsed_text = pytesseract.image_to_string(image)
        try:
            model_output = interpret_details(parsed_text)
            st.success("Receipt data extracted successfully!")
        except Exception as e:
            st.error(f"Failed to call model: {e}")
            st.stop()

    st.subheader("🧾 Receipt Details")

    person = st.text_input("Person (label)")
    category = st.selectbox("Category of Purchase", ["Travel", "Meals", "Office Supplies", "Miscellaneous"])

    # Try parsing the output
    import json
    try:
        data = json.loads(model_output)
        total = st.number_input("Total Amount", value=float(data.get("total", 0.0)))
    except:
        st.warning("Could not parse structured receipt data. You can enter manually.")
        data = {"items": {}, "total": 0.0}
        total = st.number_input("Total Amount", value=0.0)

    purchase_date = st.date_input("Date of Purchase", datetime.date.today())
    effective_date = st.date_input("Effective Date", datetime.date.today())

    st.markdown("---")
    st.subheader("🛒 Itemisation")

    # Create a session state to track items
    if "items" not in st.session_state:
        st.session_state.items = list(data.get("items", {}).items())

    # Buttons to add or remove items
    if st.button("➕ Add Item"):
        st.session_state.items.append(("", 0.0))

    if st.button("➖ Remove Last Item") and st.session_state.items:
        st.session_state.items.pop()

    updated_items = []
    for i, (item, price) in enumerate(st.session_state.items):
        col1, col2 = st.columns([3, 1])
        item_name = col1.text_input(f"Item {i+1}", value=item, key=f"item_{i}")
        item_price = col2.number_input("$", value=float(price), key=f"price_{i}")
        updated_items.append((item_name, item_price))

    st.session_state.items = updated_items

    st.markdown("---")

    if st.button("✅ Submit"):
        submission_data = {
            "person": person,
            "category": category,
            "total": total,
            "purchase_date": str(purchase_date),
            "effective_date": str(effective_date),
            "items": dict(updated_items)
        }

        st.success("Submission Successful!")
        st.json(submission_data)
        # TODO: send to backend/database as needed