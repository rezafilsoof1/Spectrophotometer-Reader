import streamlit as st
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

def process_txt_file(uploaded_file, symbol_map):
    """Processes a .txt file and converts its content."""
    try:
        # Attempt to read the .txt file with flexible encoding
        df = pd.read_csv(uploaded_file, delim_whitespace=True, header=None, encoding="latin1")

        # Check the number of columns in the file
        num_columns = df.shape[1]
        if num_columns == 1:
            # Single-column file
            df.columns = ["Column1"]
            df["Column1"] = df["Column1"].apply(
                lambda x: convert_digits_to_symbols(str(x), symbol_map)
            )
        elif num_columns == 2:
            # Two-column file
            df.columns = ["Column1", "Column2"]
            df["Column1"] = df["Column1"].apply(
                lambda x: convert_digits_to_symbols(str(x), symbol_map)
            )
            df["Column2"] = df["Column2"].apply(
                lambda x: convert_digits_to_symbols(str(x), symbol_map)
            )
        else:
            raise ValueError("Unsupported number of columns. Expected 1 or 2 columns.")

        # Convert mapped values to floats where appropriate, filtering invalid rows
        df["Column1"] = pd.to_numeric(df["Column1"], errors="coerce")
        if "Column2" in df:
            df["Column2"] = pd.to_numeric(df["Column2"], errors="coerce")

        # Drop rows with invalid numeric data
        df = df.dropna().reset_index(drop=True)

        return df
    except UnicodeDecodeError as e:
        raise ValueError(
            f"Encoding issue: {e}. Ensure the file encoding is compatible or try converting it to UTF-8."
        )
    except Exception as e:
        raise ValueError(f"Error processing .txt file: {e}")


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
st.write("Upload `.odt` files or files without extensions to plot data and export as Excel.")

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
uploaded_files = st.file_uploader("Upload your files (.odt or without extensions)", type=None, accept_multiple_files=True)

if uploaded_files:
    all_dataframes = []
    file_labels = []
    overall_min_range = float('inf')
    overall_max_range = float('-inf')

    for uploaded_file in uploaded_files:
        # Handle files with no extensions by assigning a .txt extension
        if not os.path.splitext(uploaded_file.name)[1]:  # No extension
            uploaded_file.name += ".txt"
        else:
            # Change .odt extensions to .txt
            uploaded_file.name = os.path.splitext(uploaded_file.name)[0] + ".txt"

        file_name = os.path.splitext(uploaded_file.name)[0]  # File name without extension
        file_labels.append(file_name)

        try:
            # Process each file as a .txt file
            df = process_txt_file(uploaded_file, symbol_map)
            if not df.empty:  # Check if the DataFrame is not empty
                all_dataframes.append(df)

                # Update overall min and max range
                overall_min_range = min(overall_min_range, df["Column1"].min())
                if "Column2" in df:
                    overall_max_range = max(overall_max_range, df["Column2"].max())
        except Exception as e:
            st.error(f"Error processing file '{uploaded_file.name}': {e}")

    # # Ensure valid defaults for range inputs
    # if overall_min_range == float('inf'):
    #     overall_min_range = 0.0  # Default minimum range if no data is available
    # if overall_max_range == float('-inf'):
    #     overall_max_range = 100.0  # Default maximum range if no data is available

    overall_min_range = 190.0
    overall_max_range = 1100.0

    if all_dataframes:  # Ensure there is valid data for plotting
        # Default range inputs based on data
        min_range = st.number_input("Enter minimum range for the plot:", value=overall_min_range, step=1.0)
        max_range = st.number_input("Enter maximum range for the plot:", value=overall_max_range, step=1.0)

        # Plot the data
        fig, ax = plt.subplots()

        for df, file_label in zip(all_dataframes, file_labels):
            ax.plot(df["Column1"], df["Column2"], label=file_label)

        # Customize plot
        ax.set_xlim(min_range, max_range)
        ax.set_xlabel("Wavelength")
        ax.set_ylabel("Percentage")
        ax.legend()
        ax.grid(True)

        # Display the plot
        st.pyplot(fig)
    else:
        st.warning("No valid data to plot.")

    # Save all dataframes to Excel
    excel_data = save_to_excel(all_dataframes, file_labels)

    # Download button for Excel file
    st.download_button(
        label="Download Excel File",
        data=excel_data,
        file_name="processed_data.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
