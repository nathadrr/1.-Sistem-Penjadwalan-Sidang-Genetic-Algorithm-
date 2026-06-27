import streamlit as st
import pandas as pd

st.title('Sistem Penjadwalan Sidang Menggunakan Genetic Algorithm')

#File upload menggunakan format .xlsx (excel)
uploaded_file = st.file_uploader(
    "Upload file Excel",
    type=["xlsx"]
)

if uploaded_file is not None:
    df = pd.read_excel(uploaded_file)
    st.dataframe(df)

#preprocessing untuk file ketersediaan dosen
availability = {}

for dosen in df.columns[1:]:

    slot_tersedia = set()

    for _, row in df.iterrows():
        if row[dosen] == 1:
            slot_tersedia.add(int(row["id_slot"]))

    availability[dosen] = slot_tersedia

#Pengecekan hasil availability dalam format .json
#st.subheader("Hasil Availability")
#st.write(availability)

#memastikan benar dalam format array
#st.write(availability["D001"])