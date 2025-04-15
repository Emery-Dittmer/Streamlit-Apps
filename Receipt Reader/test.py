import streamlit as st

# Initialize session state for items if not already done
if "items" not in st.session_state:
    st.session_state["items"] = [("Laptop", 1200.0), ("Keyboard", 50.0)]  # Prepopulate with dummy data

# Add or remove items based on button clicks
if st.button("➕ Add Item"):
    st.session_state["items"].append(("", 0.0))

if st.button("➖ Remove Last Item") and st.session_state["items"]:
    st.session_state["items"].pop()

# Display and edit each item
st.subheader("Your Items")
for i in range(len(st.session_state["items"])):
    item_name, item_price = st.session_state["items"][i]
    col1, col2 = st.columns([3, 1])
    new_name = col1.text_input(f"Item {i+1}", value=item_name, key=f"item_{i}")
    new_price = col2.number_input("€", value=float(item_price), key=f"price_{i}", format="%.2f")

    # Update in-place
    st.session_state["items"][i] = (new_name, new_price)

# Display the updated list below
st.markdown("---")
st.subheader("Current List:")
for i, (item, price) in enumerate(st.session_state["items"], start=1):
    st.write(f"{i}. {item} — €{price:.2f}")
