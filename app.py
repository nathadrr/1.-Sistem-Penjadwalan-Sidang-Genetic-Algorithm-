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


# --- Genetic algorithm utilities ---
SLOT_COUNT = 90
LOCKED_RANGES = [(9, 27), (54, 72)]  # 0-based indices for 1-based slots 10-27 and 55-72
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
    if len(parent_array) != SLOT_COUNT:
        raise ValueError(f"Parent must contain exactly {SLOT_COUNT} chromosomes")
    chromosomes = []
    for genes in parent_array:
        gene_list = [int(g) for g in genes]
        chromosomes.append(Chromosome(gene_list, gene_count=len(gene_list)))
    return Individual(chromosomes=chromosomes, gene_count=len(chromosomes[0].genes))


def normalize_parents(parents):
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


def build_student_queue(parent, locked_student_ids):
    queue = []
    seen = set()
    for chromosome in parent.chromosomes:
        for student_id in chromosome.genes:
            if student_id == 0:
                continue
            if student_id in seen:
                continue
            if student_id in locked_student_ids:
                continue
            seen.add(student_id)
            queue.append(int(student_id))
    return queue


def crossover_and_fill(parent1, parent2, locked_ranges=None, mahasiswa=None, availability=None, debug_list=None):
    child1 = create_empty_individual(gene_count=parent1.gene_count)
    child2 = create_empty_individual(gene_count=parent2.gene_count)

    if locked_ranges is None:
        locked_ranges = LOCKED_RANGES

    locked_indices = set()
    for start, end in locked_ranges:
        locked_indices.update(range(start, end))

    for idx in sorted(locked_indices):
        child1.chromosomes[idx] = Chromosome(parent1.chromosomes[idx].genes.copy(), gene_count=parent1.gene_count)
        child2.chromosomes[idx] = Chromosome(parent2.chromosomes[idx].genes.copy(), gene_count=parent2.gene_count)

    locked_student_ids = {
        int(student_id)
        for idx in sorted(locked_indices)
        for student_id in child1.chromosomes[idx].genes
        if student_id != 0
    }

    child1_schedule = [chromosome.genes.copy() for chromosome in child1.chromosomes]
    child2_schedule = [chromosome.genes.copy() for chromosome in child2.chromosomes]

    child1_queue = build_student_queue(parent2, locked_student_ids)
    child2_queue = build_student_queue(parent1, {
        int(student_id)
        for idx in sorted(locked_indices)
        for student_id in child2.chromosomes[idx].genes
        if student_id != 0
    })

    child1_failure = None
    for student_id in child1_queue:
        placed = False
        for slot_number in range(1, SLOT_COUNT + 1):
            slot_idx = slot_number - 1
            if slot_idx in locked_indices:
                if debug_list is not None:
                    debug_list.append(f"child1: student {student_id} skipped slot {slot_number} (locked)")
                continue
            if mahasiswa is not None and availability is not None:
                if not check_availability(student_id, slot_number, mahasiswa, availability):
                    if debug_list is not None:
                        debug_list.append(f"child1: student {student_id} skipped slot {slot_number} (availability)")
                    continue
            room = get_empty_room(child1_schedule, slot_idx)
            if room is None:
                if debug_list is not None:
                    debug_list.append(f"child1: student {student_id} skipped slot {slot_number} (no empty room)")
                continue
            if mahasiswa is not None and availability is not None and not check_conflict(child1_schedule, slot_idx, student_id, mahasiswa):
                if debug_list is not None:
                    debug_list.append(f"child1: student {student_id} skipped slot {slot_number} (conflict)")
                continue
            child1_schedule[slot_idx][room] = student_id
            child1.chromosomes[slot_idx] = Chromosome(child1_schedule[slot_idx].copy(), gene_count=parent1.gene_count)
            if debug_list is not None:
                debug_list.append(f"child1: student {student_id} placed slot {slot_number} room {room}")
            placed = True
            break
        if not placed:
            child1_failure = f"Student {student_id} could not be placed"
            if debug_list is not None:
                debug_list.append(f"child1: {child1_failure}")
            break

    child2_failure = None
    for student_id in child2_queue:
        placed = False
        for slot_number in range(1, SLOT_COUNT + 1):
            slot_idx = slot_number - 1
            if slot_idx in locked_indices:
                if debug_list is not None:
                    debug_list.append(f"child2: student {student_id} skipped slot {slot_number} (locked)")
                continue
            if mahasiswa is not None and availability is not None:
                if not check_availability(student_id, slot_number, mahasiswa, availability):
                    if debug_list is not None:
                        debug_list.append(f"child2: student {student_id} skipped slot {slot_number} (availability)")
                    continue
            room = get_empty_room(child2_schedule, slot_idx)
            if room is None:
                if debug_list is not None:
                    debug_list.append(f"child2: student {student_id} skipped slot {slot_number} (no empty room)")
                continue
            if mahasiswa is not None and availability is not None and not check_conflict(child2_schedule, slot_idx, student_id, mahasiswa):
                if debug_list is not None:
                    debug_list.append(f"child2: student {student_id} skipped slot {slot_number} (conflict)")
                continue
            child2_schedule[slot_idx][room] = student_id
            child2.chromosomes[slot_idx] = Chromosome(child2_schedule[slot_idx].copy(), gene_count=parent2.gene_count)
            if debug_list is not None:
                debug_list.append(f"child2: student {student_id} placed slot {slot_number} room {room}")
            placed = True
            break
        if not placed:
            child2_failure = f"Student {student_id} could not be placed"
            if debug_list is not None:
                debug_list.append(f"child2: {child2_failure}")
            break

    return child1, child2, child1_failure, child2_failure


def generate_all_children(parents, mahasiswa=None, availability=None, error_callback=None, debug=False):
    normalized_parents = normalize_parents(parents)
    if len(normalized_parents) < 2:
        raise ValueError("At least 2 parents are required to generate children")

    all_children = []
    failed_children = []
    for i, j in itertools.combinations(range(len(normalized_parents)), 2):
        parent1 = normalized_parents[i]
        parent2 = normalized_parents[j]
        debug_list = [] if debug else None
        child1, child2, child1_failure, child2_failure = crossover_and_fill(
            parent1,
            parent2,
            mahasiswa=mahasiswa,
            availability=availability,
            debug_list=debug_list,
        )

        if child1_failure is not None:
            failed_children.append((i, j, 1, child1_failure))
            if error_callback is not None:
                error_callback(f"Child 1 from parents {i+1} and {j+1} could not be made: {child1_failure}")
        else:
            entry = {
                "parents": (i + 1, j + 1),
                "child_index": 1,
                "schedule": child1.to_array(),
            }
            if debug and debug_list is not None:
                entry["debug"] = [m for m in debug_list]
            all_children.append(entry)

        if child2_failure is not None:
            failed_children.append((i, j, 2, child2_failure))
            if error_callback is not None:
                error_callback(f"Child 2 from parents {i+1} and {j+1} could not be made: {child2_failure}")
        else:
            entry = {
                "parents": (i + 1, j + 1),
                "child_index": 2,
                "schedule": child2.to_array(),
            }
            if debug and debug_list is not None:
                entry["debug"] = [m for m in debug_list]
            all_children.append(entry)

    return all_children, failed_children


# --- Preprocessing & GA functions ---

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
        for kolom in ["dosbing1", "dosbing2", "dosenpenguji1", "dosenpenguji2"]:
            if pd.notna(row[kolom]):
                dosen.add(str(row[kolom]).strip())
        mahasiswa[int(row["id_mhs"])] = {"dosen": dosen}
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

def jumlah_slot_valid(id_mhs, mahasiswa, availability):
    dosen = mahasiswa[id_mhs]["dosen"]

    slot = None
    for d in dosen:
        if slot is None:
            slot = availability[d].copy()
        else:
            slot &= availability[d]

    return len(slot)

def generate_initial_population(population_size, mahasiswa, availability, max_retries=500):
    population = []
    jumlah_slot = SLOT_COUNT
    jumlah_ruangan = 4
    daftar_mahasiswa = sorted(
        mahasiswa.keys(),
        key=lambda m: jumlah_slot_valid(m, mahasiswa, availability)
    )

    progress_bar = st.progress(0, text="Memulai generate populasi...")
    status_log = st.empty()

    individu_ke = 0
    while len(population) < population_size:
        individu_ke += 1
        
        if individu_ke > max_retries:
            st.error(
                f"Gagal generate populasi setelah {max_retries} percobaan. "
                f"Hanya berhasil {len(population)}/{population_size} individu. "
                f"Coba naikkan nilai maks percobaan atau periksa data ketersediaan dosen."
            )
            break

        chromosome = [[0] * jumlah_ruangan for _ in range(jumlah_slot)]
        random.shuffle(daftar_mahasiswa)

        gagal = 0
        for id_mhs in daftar_mahasiswa:
            slot_valid = None

            for d in mahasiswa[id_mhs]["dosen"]:
                if slot_valid is None:
                    slot_valid = availability[d].copy()
                else:
                    slot_valid &= availability[d]

            slot_list = list(slot_valid)

            random.shuffle(slot_list)
            ditempatkan = False

            for slot in slot_list:
                if not check_availability(id_mhs, slot, mahasiswa, availability):
                    continue
                room = get_empty_room(chromosome, slot - 1)
                if room is None:
                    continue
                if not check_conflict(chromosome, slot - 1, id_mhs, mahasiswa):
                    continue
                chromosome[slot - 1][room] = id_mhs
                ditempatkan = True
                break

            if not ditempatkan:
                gagal += 1

        if gagal == 0:
            population.append(chromosome)
            pct = len(population) / population_size
            progress_bar.progress(pct, text=f"Individu {len(population)}/{population_size} berhasil (percobaan ke-{individu_ke})")
            status_log.text(f"Percobaan ke-{individu_ke} → berhasil ({len(population)}/{population_size})")
        else:
            status_log.text(f"Percobaan ke-{individu_ke} → dibuang ({gagal} mhs gagal ditempatkan)")

    if len(population) == population_size:
        progress_bar.progress(1.0, text=f"Selesai! {population_size} individu berhasil digenerate.")

    return population


def format_schedule_for_display(schedule):
    if hasattr(schedule, "to_array"):
        schedule = schedule.to_array()

    if isinstance(schedule, list):
        formatted = []
        for idx, slot in enumerate(schedule, start=1):
            if isinstance(slot, (list, tuple)):
                formatted.append(f"{idx}: [{', '.join(str(int(value)) for value in slot)}]")
            else:
                formatted.append(f"{idx}: [{int(slot)}]")
        return formatted

    return schedule


# ==========================================
# === [BAGIAN MUTASI ANDA: FUNGSI LOGIKA] ===
# ==========================================

# Theo (Mutasi) Tukar - VERSI PERBAIKAN BUG LOGIKA DEEP COPY & LOG DISPLAY
def swap_mutation(chromosome_schedule, locked_ranges=LOCKED_RANGES, debug=False):
    """
    Fungsi Mutasi Tukar (Swap Mutation) tugas bagian saya.
    Memilih 2 slot secara acak yang TIDAK dikunci (di luar locked_ranges),
    lalu melakukan tukar posisi (swap) isi dari kedua slot tersebut.
    """
    debug_logs = []
    
    # 1. Cari semua indeks slot yang boleh dimutasi (tidak masuk dalam locked_ranges)
    valid_indices = []
    for idx in range(SLOT_COUNT):
        is_locked = False
        for start, end in locked_ranges:
            if start <= idx <= end:
                is_locked = True
                break
        if not is_locked:
            valid_indices.append(idx)
            
    if len(valid_indices) < 2:
        if debug:
            debug_logs.append("Gagal Mutasi: Slot valid kurang dari 2.")
        return chromosome_schedule, debug_logs

    # 2. Pilih secara acak 2 slot berbeda dari daftar slot yang valid
    idx1, idx2 = random.sample(valid_indices, 2)
    
    # 3. Lakukan Swap dengan menyalin sub-list (deep-copy tingkat 1) agar tidak merusak data awal
    mutated_schedule = [slot.copy() for slot in chromosome_schedule]
    val1 = mutated_schedule[idx1]
    val2 = mutated_schedule[idx2]
    
    mutated_schedule[idx1] = val2
    mutated_schedule[idx2] = val1
    
    if debug:
        # Menghapus angka 0 dari logs agar log fokus pada ID Mahasiswa yang aktif/terjadwal
        mhs1_clean = [m for m in val1 if m != 0]
        mhs2_clean = [m for m in val2 if m != 0]
        
        info_slot1 = f"Mhs ID: {mhs1_clean}" if mhs1_clean else "Slot Kosong"
        info_slot2 = f"Mhs ID: {mhs2_clean}" if mhs2_clean else "Slot Kosong"
        
        debug_logs.append(
            f"🧬 **MUTASI BERHASIL:** Menukar **Slot {idx1+1}** ({info_slot1}) "
            f"dengan **Slot {idx2+1}** ({info_slot2})"
        )
        
    return mutated_schedule, debug_logs


def mutate_all_children(children_list, mutation_rate=0.2, debug=False):
    """
    Mengiterasi semua children hasil crossover untuk dicek apakah terkena probabilitas mutasi.
    Sudah disesuaikan agar membaca format dictionary dari output crossover.
    """
    mutated_children = []
    mutation_count = 0
    all_debug_logs = {}
    
    for i, child_obj in enumerate(children_list):
        # Ambil list schedule asli dari dalam objek dictionary teman
        if isinstance(child_obj, dict):
            schedule_to_mutate = child_obj.get("schedule", [])
            parent_info = child_obj.get("parents", ("unknown", "unknown"))
            child_idx_info = child_obj.get("child_index", 0)
        else:
            schedule_to_mutate = child_obj
            parent_info = ("unknown", "unknown")
            child_idx_info = 0

        # Cek berdasarkan Mutation Rate apakah anak ini terkena mutasi
        if random.random() < mutation_rate:
            new_schedule, logs = swap_mutation(schedule_to_mutate, debug=debug)
            mutation_count += 1
            
            # Kembalikan hasilnya ke dalam struktur dictionary yang sama agar UI di bawah tidak error
            if isinstance(child_obj, dict):
                mutated_children.append({
                    "parents": parent_info,
                    "child_index": child_idx_info,
                    "schedule": new_schedule
                })
            else:
                mutated_children.append(new_schedule)
                
            if debug and logs:
                all_debug_logs[i] = logs
        else:
            # Jika tidak mutasi, masukkan objek asli tanpa perubahan
            mutated_children.append(child_obj) 
            
    return mutated_children, mutation_count, all_debug_logs

# === [AKHIR LOGIKA MUTASI] ===


# --- Streamlit UI ---

st.title("Sistem Penjadwalan Sidang Menggunakan Genetic Algorithm")

uploaded_availability = st.file_uploader(
    "Upload Availability",
    type=["xlsx"]
)

uploaded_mahasiswa = st.file_uploader(
    "Upload Data Mahasiswa",
    type=["xlsx"]
)

availability = {}
mahasiswa = {}

if uploaded_availability is not None and uploaded_mahasiswa is not None:
    df_availability = pd.read_excel(uploaded_availability)
    df_mahasiswa = pd.read_excel(uploaded_mahasiswa)

    availability = preprocessing_availability(df_availability)
    mahasiswa = preprocessing_mahasiswa(df_mahasiswa)

col1, col2 = st.columns(2)

with col1:
    population_size = st.number_input(
    "Jumlah Populasi",
    min_value=2,
    max_value=500,
    value=15,
    step=1
)

with col2:
    max_retries = st.number_input(
    "Maks Percobaan",
    min_value=10,
    max_value=5000,
    value=500,
    step=10
)

if st.button("Generate Populasi Awal"):
    if not mahasiswa or not availability:
        st.error("Upload kedua file terlebih dahulu.")
    else:
        population = generate_initial_population(
            population_size,
            mahasiswa,
            availability,
            max_retries=int(max_retries)
        )

    st.session_state['parents'] = population
    st.success(f"Populasi berhasil dibuat! ({len(population)} individu)")

    for i, chromosome in enumerate(population, start=1):
        st.subheader(f"Populasi {i}")
        st.code(str(format_schedule_for_display(chromosome)))
        st.divider()


# Display parents and children
if 'parents' in st.session_state:
    st.header('Initial Parents')
    parents = st.session_state['parents']
    for i, parent in enumerate(parents, start=1):
        with st.expander(f'Parent {i}'):
            st.code("\n".join(format_schedule_for_display(parent)))

if 'children' in st.session_state:
    children = st.session_state['children']
    st.header('First 10 Children')
    count = min(10, len(children))
    for i in range(count):
        child = children[i]
        # Support both dict-style child objects (new format) and legacy list-style schedules
        if isinstance(child, dict):
            parent_pair = child.get("parents", ("unknown", "unknown"))
            child_index = child.get("child_index", 0)
            schedule = child.get("schedule", [])
        else:
            parent_pair = ("unknown", "unknown")
            child_index = 0
            schedule = child

        with st.expander(f'Child {i+1} from parents {parent_pair[0]} & {parent_pair[1]} (child {child_index}, slots: {len(schedule)})'):
            st.code("\n".join(format_schedule_for_display(schedule)))
            if isinstance(child, dict) and child.get("debug"):
                st.text("Debug logs:")
                st.code("\n".join(child.get("debug")))
else:
    st.info("No children generated yet. Click 'Generate All Children (All pair crossovers)' after creating parents.")


if 'parents' in st.session_state and 'children' not in st.session_state:
    debug_crossover = st.checkbox("Enable crossover debug logs", value=False)
    if st.button("Generate All Children (All pair crossovers)"):
        try:
            parents_for_ga = st.session_state['parents']
            children, failed_children = generate_all_children(
                parents_for_ga,
                mahasiswa=mahasiswa,
                availability=availability,
                error_callback=st.error,
                debug=debug_crossover,
            )
            st.session_state['children'] = children
            st.session_state['failed_children'] = failed_children
            st.success(f"Generated {len(children)} children and stored in session as 'children'.")
            if failed_children:
                st.warning(f"{len(failed_children)} child pair(s) could not be made.")
        except Exception as e:
            st.error(f"Failed to generate children: {e}")


# ============================================
# === [BAGIAN MUTASI ANDA: STREAMLIT UI] ===
# ============================================

st.markdown("---")
st.subheader("🧬 Tahap Akhir GA: Proses Mutasi (Tugas Saya)")

if 'children' in st.session_state:
    children_for_mutation = st.session_state['children']
    st.info(f"Ada {len(children_for_mutation)} data anak (children) siap diproses untuk Mutasi.")
    
    # Input parameter Mutation Rate (Probabilitas Mutasi)
    mutation_rate = st.slider("Tentukan Mutation Rate (Probabilitas)", min_value=0.0, max_value=1.0, value=0.2, step=0.05)
    debug_mutation = st.checkbox("Aktifkan Log Debug Mutasi", value=True)
    
    if st.button("Jalankan Swap Mutation (Proses Mutasi) 🚀"):
        mutated_pop, count, logs = mutate_all_children(
            children_for_mutation, 
            mutation_rate=mutation_rate, 
            debug=debug_mutation
        )
        
        # Simpan hasil mutasi ke session state agar bisa digunakan tahap evaluasi selanjutnya
        st.session_state['mutated_children'] = mutated_pop
        
        st.success(f"Proses mutasi selesai! Sebanyak {count} anak berhasil mengalami Swap Mutation.")
        
        # Tampilkan Expander untuk melihat anak yang mengalami mutasi beserta lognya
        if debug_mutation and logs:
            st.write("### 📝 Log Perubahan Mutasi:")
            for child_idx, log_list in logs.items():
                child_item = mutated_pop[child_idx]
                p_info = child_item.get("parents", ("?", "?"))
                c_idx = child_item.get("child_index", "?")
                
                with st.expander(f"Detail Mutasi pada Anak ke-{child_idx + 1} (Parents {p_info[0]} & {p_info[1]}, C-{c_idx})"):
                    for l in log_list:
                        st.info(l)
                    st.text("Jadwal setelah mutasi:")
                    # Mengakses key ["schedule"] karena mutated_pop berisi objek dictionary
                    st.code("\n".join(format_schedule_for_display(child_item["schedule"])))
                        
else:
    st.warning("⚠️ Silakan lakukan proses 'Generate All Children' (Crossover teman) terlebih dahulu di atas sebelum melakukan langkah mutasi ini.")

# === [AKHIR STREAMLIT UI MUTASI] ===