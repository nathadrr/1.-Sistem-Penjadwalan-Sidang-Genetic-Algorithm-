import importlib
import subprocess
import sys


def install_and_import(packages):
    for pkg in packages:
        try:
            importlib.import_module(pkg)
        except ImportError:
            print(f"Package '{pkg}' not found; installing...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", pkg])

install_and_import(["streamlit", "pandas", "openpyxl"])

import streamlit as st
import pandas as pd
import random
import os
import itertools


try:
    from streamlit.runtime.scriptrunner import get_script_run_ctx
except Exception:
    def get_script_run_ctx():
        return None

if __name__ == "__main__":
    if get_script_run_ctx() is None:
        script_path = os.path.abspath(__file__)
        print("This app should be run with 'streamlit run'.")
        print(f"Run: streamlit run {script_path}")
        sys.exit(0)


# --- Genetic algorithm utilities moved from geneticAlgorythm.py ---
SLOT_COUNT = 45
LOCKED_START = 9
LOCKED_END = 27
DEFAULT_GENE_COUNT = 4


class Chromosome:
    def __init__(self, genes=None, gene_count=DEFAULT_GENE_COUNT):
        if genes is None:
            self.genes = [0 for _ in range(gene_count)]
        else:
            self.genes = [int(g) for g in genes]

    def __str__(self):
        return f"[{', '.join(str(g) for g in self.genes)}]"

    def __repr__(self):
        return self.__str__()


class Individual:
    def __init__(self, chromosomes=None, gene_count=DEFAULT_GENE_COUNT):
        self.gene_count = gene_count
        if chromosomes is None:
            self.chromosomes = [Chromosome(gene_count=gene_count) for _ in range(SLOT_COUNT)]
        else:
            if len(chromosomes) != SLOT_COUNT:
                raise ValueError(f"Individual must have exactly {SLOT_COUNT} chromosomes")
            self.chromosomes = chromosomes

    def to_array(self):
        return [chromosome.genes.copy() for chromosome in self.chromosomes]

    def __str__(self):
        return f"Individual with {len(self.chromosomes)} chromosomes"


def create_empty_individual(gene_count=DEFAULT_GENE_COUNT):
    return Individual([Chromosome([0 for _ in range(gene_count)]) for _ in range(SLOT_COUNT)], gene_count=gene_count)


def build_parent_from_array(parent_array):
    """Convert a nested array of 45 chromosomes into an Individual."""
    if len(parent_array) != SLOT_COUNT:
        raise ValueError(f"Parent must contain exactly {SLOT_COUNT} chromosomes")

    chromosomes = []
    for genes in parent_array:
        gene_list = [int(g) for g in genes]
        chromosomes.append(Chromosome(gene_list, gene_count=len(gene_list)))

    return Individual(chromosomes=chromosomes, gene_count=len(chromosomes[0].genes))


def normalize_parents(parents):
    """Accept either Individual objects or nested arrays and return a list of Individuals."""
    normalized = []
    for parent in parents:
        if isinstance(parent, Individual):
            normalized.append(parent)
        elif isinstance(parent, list):
            normalized.append(build_parent_from_array(parent))
        else:
            raise TypeError("Each parent must be an Individual or a nested list")
    return normalized


def parse_numbers_from_line(line):
    cleaned = line.replace('\t', ' ').replace(',', ' ').replace('[', ' ').replace(']', ' ')
    return [int(part) for part in cleaned.split() if part.lstrip('-').isdigit()]


def load_parents_from_file(filename="parents.txt"):
    """Load parents from the text file. Supports both 3-value and 4-value chromosome formats."""
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            content = f.read()
    except FileNotFoundError:
        print(f"Error: File '{filename}' not found.")
        return []
    except Exception as exc:
        print(f"Error loading parents from file: {exc}")
        return []

    parent_blocks = {}
    current_parent = None
    current_numbers = []

    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith('P') and '=' in line:
            if current_parent is not None:
                parent_blocks[current_parent] = current_numbers
            current_parent = line.split('=')[0].strip()
            current_numbers = []
            line = line.split('[', 1)[1] if '[' in line else ''
        elif line == ']':
            if current_parent is not None:
                parent_blocks[current_parent] = current_numbers
                current_parent = None
                current_numbers = []
            continue

        if current_parent is not None:
            current_numbers.extend(parse_numbers_from_line(line))

    if current_parent is not None:
        parent_blocks[current_parent] = current_numbers

    if not parent_blocks:
        return []

    parents = []
    for parent_name in sorted(parent_blocks, key=lambda name: int(name[1:])):
        numbers = parent_blocks[parent_name]
        if not numbers:
            continue
        gene_count = len(numbers) // SLOT_COUNT if len(numbers) % SLOT_COUNT == 0 else DEFAULT_GENE_COUNT
        chromosomes = []
        for slot_idx in range(SLOT_COUNT):
            start = slot_idx * gene_count
            end = start + gene_count
            genes = numbers[start:end]
            if len(genes) < gene_count:
                genes = genes + [0] * (gene_count - len(genes))
            chromosomes.append(Chromosome(genes, gene_count=gene_count))
        parents.append(Individual(chromosomes=chromosomes, gene_count=gene_count))

    return parents


def crossover_and_fill(parent1, parent2, locked_start=LOCKED_START, locked_end=LOCKED_END):
    """Create two children from two parents using a locked middle section."""
    child1 = create_empty_individual(gene_count=parent1.gene_count)
    child2 = create_empty_individual(gene_count=parent2.gene_count)
    locked_indices = list(range(locked_start, locked_end))

    for idx in locked_indices:
        child1.chromosomes[idx] = Chromosome(parent1.chromosomes[idx].genes.copy(), gene_count=parent1.gene_count)
        child2.chromosomes[idx] = Chromosome(parent2.chromosomes[idx].genes.copy(), gene_count=parent2.gene_count)

    unlocked_indices = [i for i in range(SLOT_COUNT) if i not in set(locked_indices)]
    for slot_idx in unlocked_indices:
        child1.chromosomes[slot_idx] = Chromosome(parent2.chromosomes[slot_idx].genes.copy(), gene_count=parent2.gene_count)
        child2.chromosomes[slot_idx] = Chromosome(parent1.chromosomes[slot_idx].genes.copy(), gene_count=parent1.gene_count)

    return child1, child2


def generate_all_children(parents):
    """Generate all non-repeating parent-pair children and return them as a nested array."""
    normalized_parents = normalize_parents(parents)
    if len(normalized_parents) < 2:
        raise ValueError("At least 2 parents are required to generate children")

    all_children = []
    for i, j in itertools.combinations(range(len(normalized_parents)), 2):
        parent1 = normalized_parents[i]
        parent2 = normalized_parents[j]
        child1, child2 = crossover_and_fill(parent1, parent2)
        all_children.append(child1.to_array())
        all_children.append(child2.to_array())
    return all_children

# --- End moved GA utilities ---

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

# Default population size (removed interactive input for sharing/runners)
population_size = 15
st.write(f"Jumlah Populasi: {population_size}")

if st.button("Generate Populasi Awal"):

    population = generate_initial_population(
        population_size,
        mahasiswa,
        availability
    )

    # Store the generated population as the GA "parents" array and keep it in session state
    parents = population  # nested-array format: [parent][slot][room]
    st.session_state['parents'] = parents
    st.write(f"Stored {len(parents)} parents in session (available as `st.session_state['parents']`).")
    

    st.success("Populasi berhasil dibuat!")

    for i, chromosome in enumerate(population, start=1):

        st.subheader(f"Populasi {i}")

        for slot, ruang in enumerate(chromosome, start=1):
            st.text(f"Slot {slot:2d} : {ruang}")

        st.divider()


# Display first 10 children if available in session state
if 'children' in st.session_state:
    children = st.session_state['children']
    st.header('First 10 Children')
    count = min(10, len(children))
    for i in range(count):
        with st.expander(f'Child {i+1} (slots: {len(children[i])})'):
            st.write(children[i])
            st.write('Preview - first 3 chromosomes:', children[i][:3])
else:
    st.info("No children generated yet. Click 'Generate All Children (All pair crossovers)' after creating parents.")


# Top-level button to generate all children from stored parents
if 'parents' in st.session_state and 'children' not in st.session_state:
    if st.button("Generate All Children (All pair crossovers)"):
        try:
            parents_for_ga = st.session_state['parents']
            children = generate_all_children(parents_for_ga)
            st.session_state['children'] = children
            st.success(f"Generated {len(children)} children and stored in session as 'children'.")
            if len(children) > 0:
                st.write("Example first child (first slot):", children[0][0])
                st.write("First 3 chromosomes of the first child:", children[0][:3])
        except Exception as e:
            st.error(f"Failed to generate children: {e}")

    