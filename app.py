import streamlit as st
from odf.opendocument import load
from odf.text import P
import pandas as pd
import matplotlib.pyplot as plt
from io import BytesIO
import os

# Symbol-to-digit mapping
symbol_map = {
    "°": "0",
    "¹": "9",
    "³": "3",
    "µ": "5",
    "¶": "6",
    "®": ".",  # Represents a period
    "1": "1",
    "2": "2",
    "4": "4",
    "7": "7",
    "8": "8"
}


def convert_symbols_to_digits(text):
    """Converts special symbols to digits based on the mapping."""
    return ''.join(symbol_map.get(char, char) for char in text)

def process_odt_file(uploaded_file):
    """Processes the uploaded .odt file and converts its content."""
    doc = load(uploaded_file)
    paragraphs = doc.getElementsByType(P)

    # Extract and process text
    rows = []
    for paragraph in paragraphs:
        # Get the text content from the paragraph
        text_elements = paragraph.childNodes
        text = "".join([node.data for node in text_elements if node.nodeType == 3])  # Extract text nodes only
        if text.strip():  # Ignore empty lines
            converted_text = convert_symbols_to_digits(text)
            # Split into columns, and ensure exactly two columns (Range and Percentage)
            split_text = converted_text.split()
            if len(split_text) == 2:  # Only accept rows with exactly two elements
                rows.append(split_text)
            else:
                # Log or handle rows with unexpected number of columns (optional)
                st.warning(f"Skipping malformed row: {converted_text}")

    # Convert to DataFrame
    if not rows:
        raise ValueError("No valid data found in the file.")
    df = pd.DataFrame(rows, columns=["Range", "Percentage"])
    df["Range"] = pd.to_numeric(df["Range"], errors="coerce")  # Ensure numeric types
    df["Percentage"] = pd.to_numeric(df["Percentage"], errors="coerce")
    return df.dropna()  # Drop rows with NaN

def save_to_excel(dataframes, file_names):
    """Saves multiple DataFrames to a single Excel file with each file as a sheet."""
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        for df, name in zip(dataframes, file_names):
            df.to_excel(writer, sheet_name=name, index=False)
    output.seek(0)
    return output

# Streamlit UI
st.title("ODT File Plotter and Exporter")
st.write("Upload multiple `.odt` files to plot data and export as Excel.")

# File uploader for multiple files
uploaded_files = st.file_uploader("Upload your `.odt` files", type=["odt"], accept_multiple_files=True)

if uploaded_files:
    all_dataframes = []
    file_labels = []
    overall_min_range = float('inf')
    overall_max_range = float('-inf')

    for uploaded_file in uploaded_files:
        # Process each file
        file_name = os.path.splitext(uploaded_file.name)[0]  # Get file name without extension
        file_labels.append(file_name)
        df = process_odt_file(uploaded_file)
        all_dataframes.append(df)

        # Update overall min and max range
        overall_min_range = min(overall_min_range, df["Range"].min())
        overall_max_range = max(overall_max_range, df["Range"].max())

    # Default range inputs based on data
    min_range = st.number_input("Enter minimum range for the plot:", value=overall_min_range, step=1.0)
    max_range = st.number_input("Enter maximum range for the plot:", value=overall_max_range, step=1.0)

    # Plot the data
    fig, ax = plt.subplots()

    for df, file_label in zip(all_dataframes, file_labels):
        ax.plot(df["Range"], df["Percentage"], label=file_label)

    # Customize plot
    ax.set_xlim(min_range, max_range)
    ax.set_xlabel("Range")
    ax.set_ylabel("Percentage")
    ax.legend()
    ax.grid(True)

    # Display the plot
    st.pyplot(fig)

    # Save all dataframes to Excel
    excel_data = save_to_excel(all_dataframes, file_labels)

    # Download button for Excel file
    st.download_button(
        label="Download Excel File",
        data=excel_data,
        file_name="processed_data.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
