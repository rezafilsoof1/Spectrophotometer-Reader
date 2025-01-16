import streamlit as st
from odf.opendocument import load
from odf.text import P
import pandas as pd
import matplotlib.pyplot as plt
from io import BytesIO
import os

# Default number-to-symbol mapping
default_symbol_map = {
    "0": "°",
    "1": "1",
    "2": "2",
    "3": "³",
    "4": "4",
    "5": "µ",
    "6": "¶",
    "7": "7",
    "8": "8",
    "9": "¹",
    ".": "®"  # Represents a period
}

def convert_digits_to_symbols(text, symbol_map):
    """
    Converts digits to their corresponding symbols and ensures the resulting
    text is numeric by replacing symbols back to digits.
    """
    # Replace numbers with symbols
    replaced_text = ''.join(symbol_map.get(char, char) for char in text)
    # Replace symbols back to digits
    reversed_map = {v: k for k, v in symbol_map.items()}  # Reverse mapping
    return ''.join(reversed_map.get(char, char) for char in replaced_text)


def process_odt_file(uploaded_file, symbol_map):
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
            # Convert digits to symbols and then back to numbers
            converted_text = convert_digits_to_symbols(text, symbol_map)
            # Split into columns and ensure exactly two columns (Wavelength and Percentage)
            split_text = converted_text.split()
            if len(split_text) == 2:
                try:
                    # Convert both columns to numbers
                    range_val = float(split_text[0])
                    percentage_val = float(split_text[1])
                    rows.append([range_val, percentage_val])
                except ValueError:
                    st.warning(f"Skipping non-numeric row: {converted_text}")
            else:
                st.warning(f"Skipping malformed row: {converted_text}")

    # Convert to DataFrame
    if not rows:
        raise ValueError("No valid data found in the file.")
    df = pd.DataFrame(rows, columns=["Wavelength", "Percentage"])
    return df

def save_to_excel(dataframes, file_names):
    """Saves multiple DataFrames to a single Excel file with each file as a sheet."""
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        for df, name in zip(dataframes, file_names):
            df.to_excel(writer, sheet_name=name, index=False)
    output.seek(0)
    return output

# Streamlit UI
st.title("Spectrophotometer Data Plotter")
st.write("Upload multiple `.odt` files to plot data and export as Excel.")

# Symbol map editor
st.sidebar.header("Customize Symbol Mapping")
symbol_map = st.sidebar.text_area(
    "Number-to-Symbol Map (JSON format)",
    value=str(default_symbol_map),
    help="Enter the mapping in JSON format. Keys should be numbers (e.g., '1'), and values should be symbols."
)

try:
    # Convert user-provided JSON string into a dictionary
    symbol_map = eval(symbol_map)
    if not isinstance(symbol_map, dict):
        raise ValueError
except Exception:
    st.sidebar.error("Invalid dictionary format. Please provide a valid JSON-like dictionary.")
    symbol_map = default_symbol_map

st.sidebar.write("Current Symbol Map:")
st.sidebar.json(symbol_map)

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
        try:
            df = process_odt_file(uploaded_file, symbol_map)
            all_dataframes.append(df)

            # Update overall min and max range
            overall_min_range = min(overall_min_range, df["Wavelength"].min())
            overall_max_range = max(overall_max_range, df["Wavelength"].max())
        except Exception as e:
            st.error(f"Error processing file {uploaded_file.name}: {e}")

    # Ensure valid defaults for range inputs
    if overall_min_range == float('inf'):
        overall_min_range = 0.0  # Default minimum range if no data is available
    if overall_max_range == float('-inf'):
        overall_max_range = 100.0  # Default maximum range if no data is available

    # Default range inputs based on data
    min_range = st.number_input("Enter minimum range for the plot:", value=overall_min_range, step=1.0)
    max_range = st.number_input("Enter maximum range for the plot:", value=overall_max_range, step=1.0)

    # Plot the data
    fig, ax = plt.subplots()

    for df, file_label in zip(all_dataframes, file_labels):
        ax.plot(df["Wavelength"], df["Percentage"], label=file_label)

    # Customize plot
    ax.set_xlim(min_range, max_range)
    ax.set_xlabel("Wavelength")
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
