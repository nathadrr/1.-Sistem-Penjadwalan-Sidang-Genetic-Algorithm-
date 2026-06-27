import streamlit as st
import pandas as pd
import random

def preprocessing_availability(df):

    availability = {}

    for dosen in df.columns[1:]:
        dosen = dosen.strip()

        slot_tersedia = set()

        for _, row in df.iterrows():

            if row[dosen] == 1:
                slot_tersedia.add(int(row["id_slot"]))

        availability[dosen] = slot_tersedia

    return availability

def preprocessing_mahasiswa(df):

    mahasiswa = {}

    for _, row in df.iterrows():

        dosen = set()

        for kolom in [
            "dosbing1",
            "dosbing2",
            "dosenpenguji1",
            "dosenpenguji2"
        ]:

            if pd.notna(row[kolom]):      # hanya jika tidak kosong
                dosen.add(str(row[kolom]).strip())

        mahasiswa[int(row["id_mhs"])] = {
            "dosen": dosen
        }

    return mahasiswa

def check_availability(id_mhs, slot, mahasiswa, availability):

    dosen = mahasiswa[id_mhs]["dosen"]

    for d in dosen:

        if slot not in availability[d]:
            return False

    return True

def check_conflict(chromosome, slot, id_mhs, mahasiswa):

    dosen_baru = mahasiswa[id_mhs]["dosen"]

    for mhs in chromosome[slot]:

        if mhs == 0:
            continue

        dosen_lama = mahasiswa[mhs]["dosen"]

        if dosen_baru & dosen_lama:
            return False

    return True

def get_empty_room(chromosome, slot):

    for r in range(4):

        if chromosome[slot][r] == 0:
            return r

    return None

def generate_initial_population(population_size, mahasiswa, availability):

    population = []

    jumlah_slot = 45
    jumlah_ruangan = 4

    daftar_mahasiswa = list(mahasiswa.keys())

    for _ in range(population_size):

        chromosome = [[0 for _ in range(jumlah_ruangan)]
                      for _ in range(jumlah_slot)]

        random.shuffle(daftar_mahasiswa)

        for id_mhs in daftar_mahasiswa:

            slot_list = list(range(1, jumlah_slot + 1))
            random.shuffle(slot_list)

            ditempatkan = False

            for slot in slot_list:

                if not check_availability(
                    id_mhs,
                    slot,
                    mahasiswa,
                    availability
                ):
                    continue

                room = get_empty_room(
                    chromosome,
                    slot - 1
                )

                if room is None:
                    continue

                if not check_conflict(
                    chromosome,
                    slot - 1,
                    id_mhs,
                    mahasiswa
                ):
                    continue

                chromosome[slot - 1][room] = id_mhs
                ditempatkan = True
                break

            if not ditempatkan:
                print(f"Mahasiswa {id_mhs} gagal ditempatkan.")

        population.append(chromosome)

    return population

st.title("Sistem Penjadwalan Sidang Menggunakan Genetic Algorithm")

uploaded_availability = st.file_uploader(
    "Upload Ketersediaan Dosen",
    type=["xlsx"]
)

uploaded_mahasiswa = st.file_uploader(
    "Upload Data Mahasiswa",
    type=["xlsx"]
)

if uploaded_availability and uploaded_mahasiswa:

    df_availability = pd.read_excel(uploaded_availability)
    df_mahasiswa = pd.read_excel(uploaded_mahasiswa)

    availability = preprocessing_availability(df_availability)
    mahasiswa = preprocessing_mahasiswa(df_mahasiswa)

population_size = st.number_input(
    "Jumlah Populasi",
    min_value=1,
    value=10,
    step=1
)

if st.button("Generate Populasi Awal"):

    population = generate_initial_population(
        population_size,
        mahasiswa,
        availability
    )

    st.success("Populasi berhasil dibuat!")

    for i, chromosome in enumerate(population, start=1):

        st.subheader(f"Populasi {i}")

        for slot, ruang in enumerate(chromosome, start=1):
            st.text(f"Slot {slot:2d} : {ruang}")

        st.divider()

    