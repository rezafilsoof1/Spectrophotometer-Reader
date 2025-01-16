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
    """Converts digits to their corresponding symbols and ensures the resulting text is numeric."""
    # Replace numbers with symbols
    replaced_text = ''.join(symbol_map.get(char, char) for char in text)
    # Replace symbols back to digits
    reversed_map = {v: k for k, v in symbol_map.items()}  # Reverse mapping
    return ''.join(reversed_map.get(char, char) for char in replaced_text)

def process_txt_file(uploaded_file, symbol_map, encoding):
    """Processes a .txt file and converts its content."""
    try:
        # Handle customized mapping without encoding
        if encoding == "Customized Mapping":
            content = uploaded_file.read().decode("latin1")  # Read as string
            lines = content.splitlines()
            rows = [line.split() for line in lines if line.strip()]
            df = pd.DataFrame(rows)
        else:
            # Read the .txt file with the selected encoding
            df = pd.read_csv(uploaded_file, delim_whitespace=True, header=None, encoding=encoding)

        # Check the number of columns in the file
        num_columns = df.shape[1]
        if num_columns == 1:
            df.columns = ["Wavelength"]
            df["Wavelength"] = df["Wavelength"].apply(lambda x: convert_digits_to_symbols(str(x), symbol_map))
        elif num_columns == 2:
            df.columns = ["Wavelength", "Percentage"]
            df["Wavelength"] = df["Wavelength"].apply(lambda x: convert_digits_to_symbols(str(x), symbol_map))
            df["Percentage"] = df["Percentage"].apply(lambda x: convert_digits_to_symbols(str(x), symbol_map))
        else:
            raise ValueError("Unsupported number of columns. Expected 1 or 2 columns.")

        # Convert to numeric, filtering invalid rows
        df["Wavelength"] = pd.to_numeric(df["Wavelength"], errors="coerce")
        if "Percentage" in df:
            df["Percentage"] = pd.to_numeric(df["Percentage"], errors="coerce")

        # Drop rows with invalid numeric data
        df = df.dropna().reset_index(drop=True)
        return df
    except UnicodeDecodeError as e:
        raise ValueError(f"Encoding issue: {e}. Try converting the file to UTF-8.")
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
    st.sidebar.error("Invalid dictionary format. Using default mapping.")
    symbol_map = default_symbol_map

st.sidebar.write("Current Symbol Map:")
st.sidebar.json(symbol_map)

# Dropdown to select encoding
encoding = st.sidebar.selectbox("Select Encoding", options=["latin1", "utf-8", "Customized Mapping"])

# File uploader for multiple files
uploaded_files = st.file_uploader("Upload your files (.odt or without extensions)", type=None, accept_multiple_files=True)

# Button to reprocess files
if st.button("Process Files"):
    if uploaded_files:
        all_dataframes = []
        file_labels = []
        overall_min_range = float('inf')
        overall_max_range = float('-inf')

        for uploaded_file in uploaded_files:
            file_extension = os.path.splitext(uploaded_file.name)[1]  # Get the file extension
            file_name = os.path.splitext(uploaded_file.name)[0]  # File name without extension

            # Handle files with no extensions by assigning a .txt extension
            if not file_extension:  # No extension
                uploaded_file.name += ".txt"
            elif file_extension == ".odt":
                # Keep `.odt` files as they are and process them differently
                pass
            else:
                # Change other extensions to `.txt` (e.g., `.csv` to `.txt`)
                uploaded_file.name = file_name + ".txt"

            file_labels.append(file_name)

            try:
                # Handle `.odt` files separately
                if file_extension == ".odt":
                    from odf.opendocument import load
                    from odf.text import P

                    # Load the ODT document
                    doc = load(uploaded_file)
                    paragraphs = doc.getElementsByType(P)

                    # Process the ODT content
                    rows = []
                    for paragraph in paragraphs:
                        text_elements = paragraph.childNodes
                        text = "".join([node.data for node in text_elements if node.nodeType == 3]).strip()
                        if text:
                            rows.append(text.split())

                    # Convert rows to DataFrame
                    df = pd.DataFrame(rows)
                    if df.shape[1] == 1:
                        df.columns = ["Wavelength"]
                    elif df.shape[1] == 2:
                        df.columns = ["Wavelength", "Percentage"]
                    else:
                        raise ValueError("Unsupported number of columns in ODT file.")

                    # Apply symbol mapping
                    df["Wavelength"] = df["Wavelength"].apply(lambda x: convert_digits_to_symbols(str(x), symbol_map))
                    if "Percentage" in df:
                        df["Percentage"] = df["Percentage"].apply(lambda x: convert_digits_to_symbols(str(x), symbol_map))

                else:  # Handle `.txt` or renamed `.txt` files
                    df = process_txt_file(uploaded_file, symbol_map, encoding)

                if not df.empty:  # Check if the DataFrame is not empty
                    all_dataframes.append(df)

                    # Update overall min and max range
                    overall_min_range = min(overall_min_range, df["Wavelength"].min())
                    if "Percentage" in df:
                        overall_max_range = max(overall_max_range, df["Percentage"].max())

            except Exception as e:
                st.error(f"Error processing file '{uploaded_file.name}': {e}")

        # Set default ranges if no valid data
        if overall_min_range == float('inf'):
            overall_min_range = 0.0
        if overall_max_range == float('-inf'):
            overall_max_range = 100.0

        if all_dataframes:  # Ensure there is valid data for plotting
            # Default range inputs based on data
            min_range = st.number_input("Enter minimum range for the plot:", value=190.0, step=1.0)
            max_range = st.number_input("Enter maximum range for the plot:", value=1100.0, step=1.0)

            # Plot the data
            fig, ax = plt.subplots(figsize=(10, 6))  # Adjust figure size for better spacing

            for df, file_label in zip(all_dataframes, file_labels):
                ax.plot(df["Wavelength"], df["Percentage"], label=file_label)

            # Customize plot
            ax.set_xlim(min_range, max_range)
            ax.set_xlabel("Wavelength")
            ax.set_ylabel("Percentage")
            ax.grid(True)

            # Position the legend outside the plot
            ax.legend(loc="upper left", bbox_to_anchor=(1, 1), title="Files")  # Adjust position

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
    else:
        st.warning("Please upload files to process.")
