import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from io import BytesIO
import os

# todo: fix max range updater
# todo: fix .odt file processing with custom symbols

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
    replaced_text = ''.join(symbol_map.get(char, char) for char in text)
    reversed_map = {v: k for k, v in symbol_map.items()}  # Reverse mapping
    return ''.join(reversed_map.get(char, char) for char in replaced_text)

def process_txt_file(uploaded_file, symbol_map, encoding):
    try:
        if encoding == "Customized Mapping":
            content = uploaded_file.read().decode("latin1")
            lines = content.splitlines()
            rows = [line.split() for line in lines if line.strip()]
            df = pd.DataFrame(rows)
        else:
            df = pd.read_csv(uploaded_file, delim_whitespace=True, header=None, encoding=encoding)

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

        df["Wavelength"] = pd.to_numeric(df["Wavelength"], errors="coerce")
        if "Percentage" in df:
            df["Percentage"] = pd.to_numeric(df["Percentage"], errors="coerce")

        df = df.dropna().reset_index(drop=True)
        return df
    except Exception as e:
        raise ValueError(f"Error processing .txt file: {e}")

def save_to_excel(dataframes, file_names):
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        for df, name in zip(dataframes, file_names):
            df.to_excel(writer, sheet_name=name, index=False)
    output.seek(0)
    return output

# Streamlit UI
st.title("Spectrophotometer Data Plotter")

# Symbol map editor
symbol_map = st.sidebar.text_area(
    "Number-to-Symbol Map (JSON format)",
    value=str(default_symbol_map),
    help="Enter the mapping in JSON format. Keys should be numbers (e.g., '1'), and values should be symbols."
)

try:
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

# Initialize session state for file processing
if "all_dataframes" not in st.session_state:
    st.session_state.all_dataframes = []
    st.session_state.file_labels = []
    st.session_state.min_range = 190.0
    st.session_state.max_range = 1100.0

if st.button("Process Files") and uploaded_files:
    st.session_state.all_dataframes = []
    st.session_state.file_labels = []
    overall_min_range = float('inf')
    overall_max_range = float('-inf')

    for uploaded_file in uploaded_files:
        file_extension = os.path.splitext(uploaded_file.name)[1]
        file_name = os.path.splitext(uploaded_file.name)[0]

        if not file_extension:  # No extension
            uploaded_file.name += ".txt"
        elif file_extension == ".odt":
            pass
        else:
            uploaded_file.name = file_name + ".txt"

        st.session_state.file_labels.append(file_name)

        try:
            if file_extension == ".odt":
                from odf.opendocument import load
                from odf.text import P

                doc = load(uploaded_file)
                paragraphs = doc.getElementsByType(P)

                rows = []
                for paragraph in paragraphs:
                    text_elements = paragraph.childNodes
                    text = "".join([node.data for node in text_elements if node.nodeType == 3]).strip()
                    if text:
                        rows.append(text.split())

                df = pd.DataFrame(rows)
                if df.shape[1] == 1:
                    df.columns = ["Wavelength"]
                elif df.shape[1] == 2:
                    df.columns = ["Wavelength", "Percentage"]
                else:
                    raise ValueError("Unsupported number of columns in ODT file.")

                df["Wavelength"] = df["Wavelength"].apply(lambda x: convert_digits_to_symbols(str(x), symbol_map))
                if "Percentage" in df:
                    df["Percentage"] = df["Percentage"].apply(lambda x: convert_digits_to_symbols(str(x), symbol_map))
            else:
                df = process_txt_file(uploaded_file, symbol_map, encoding)

            if not df.empty:
                st.session_state.all_dataframes.append(df)

                # Update overall min range using "Wavelength"
                overall_min_range = min(overall_min_range, df["Wavelength"].min())

                # Update overall max range using "Percentage" if available, otherwise "Wavelength"
                if "Percentage" in df:
                    overall_max_range = max(overall_max_range, df["Percentage"].max())
                else:
                    overall_max_range = max(overall_max_range, df["Wavelength"].max())

        except Exception as e:
            st.error(f"Error processing file '{uploaded_file.name}': {e}")

    if overall_min_range != float('inf'):
        st.session_state.min_range = overall_min_range
    if overall_max_range != float('-inf'):
        st.session_state.max_range = overall_max_range

if st.session_state.all_dataframes:
    min_range = st.number_input("Enter minimum range for the plot:", value=st.session_state.min_range, step=1.0)
    max_range = st.number_input("Enter maximum range for the plot:", value=st.session_state.max_range, step=1.0)

    fig, ax = plt.subplots(figsize=(10, 6))

    for df, file_label in zip(st.session_state.all_dataframes, st.session_state.file_labels):
        ax.plot(df["Wavelength"], df["Percentage"], label=file_label)

    ax.set_xlim(min_range, max_range)
    ax.set_xlabel("Wavelength")
    ax.set_ylabel("Percentage")
    ax.grid(True)
    ax.legend(loc="upper left", bbox_to_anchor=(1, 1), title="Files")
    st.pyplot(fig)

    plot_data = BytesIO()
    fig.savefig(plot_data, format="png", bbox_inches="tight")
    plot_data.seek(0)

    st.download_button(
        label="Download Plot",
        data=plot_data,
        file_name="plot.png",
        mime="image/png",
    )

    excel_data = save_to_excel(st.session_state.all_dataframes, st.session_state.file_labels)
    st.download_button(
        label="Download Excel File",
        data=excel_data,
        file_name="processed_data.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
